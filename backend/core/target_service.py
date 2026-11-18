"""
Target Service:
- SSRF Boundary Validation & IP range enforcement
- Sealed 48-Hour pusher_guard.py generation with SHA-256 integrity checksums
- Live challenge-response verification (/__pusher_verify?nonce=...) and Kill revocation
"""

import base64
import hashlib
import hmac
import ipaddress
import json
import os
import secrets
import socket
import sqlite3
import time
import urllib.parse
import zlib
import httpx
from backend.core.config import settings

from backend.core.database import (
    db_get_active_target,
    db_save_active_target,
    db_record_guard_generation,
    db_get_daily_generations_count,
    db_burn_guard,
    db_is_guard_burned,
    db_get_burned_guards_count,
    get_db_connection,
)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "pusher_runs.db")

def init_tombstone_db():
    """Initializes persistent SQLite tombstone registry for permanently burned guards."""
    from backend.core.database import init_all_tables
    init_all_tables()

# Auto-initialize table on module import
init_tombstone_db()

def hash_device_id(device_id: str | None) -> str:
    """Returns a deterministic SHA-256 fingerprint prefix of the incoming device ID."""
    if not device_id or not str(device_id).strip():
        device_id = "DEV-DEFAULT-CREATOR"
    return hashlib.sha256(str(device_id).strip().encode("utf-8")).hexdigest()[:16]

def burn_guard_id(
    guard_id: str,
    reason: str,
    creator_device_hash: str | None = None,
    offending_device_hash: str | None = None
) -> dict:
    """
    Permanently records a burned Guard ID in SQLite.
    Once written to burned_guards, this ID can NEVER be used, re-issued, or verified again.
    """
    if not guard_id:
        return {}
    res = db_burn_guard(
        guard_id=guard_id,
        burn_reason=reason,
        creator_device_hash=creator_device_hash,
        offending_device_hash=offending_device_hash,
    )
    target_store.revoked_guard_ids.add(guard_id)
    target_store.last_revoked_guard_id = guard_id
    target_store.last_burn_reason = reason
    return res

def is_guard_burned(guard_id: str | None) -> dict | None:
    """Checks if a Guard ID exists in the permanent SQLite tombstone registry."""
    return db_is_guard_burned(guard_id)

# In-memory target tracker (Enforcing 1-Project Active Limit)
class GuardRateLimitError(Exception):
    """Raised when daily guard generation limit (3/24h) is exceeded."""
    pass


class GuardActiveConflictError(Exception):
    """Raised when attempting to generate a guard while an active unrevoked guard already exists (Kill-First rule)."""
    pass


class PersistentGenerationsList:
    def __init__(self, store):
        self.store = store

    def _get_items(self) -> list[float]:
        conn = get_db_connection()
        try:
            cutoff = time.time() - self.store.RATE_LIMIT_WINDOW_SECONDS
            rows = conn.execute(
                "SELECT generated_at FROM guard_generations WHERE creator_device_hash = ? AND generated_at >= ? ORDER BY generated_at ASC;",
                (self.store.creator_device_hash, cutoff),
            ).fetchall()
            return [float(r["generated_at"]) for r in rows]
        finally:
            conn.close()

    def __len__(self):
        return len(self._get_items())

    def __iter__(self):
        return iter(self._get_items())

    def clear(self):
        conn = get_db_connection()
        try:
            with conn:
                conn.execute(
                    "DELETE FROM guard_generations WHERE creator_device_hash = ?;",
                    (self.store.creator_device_hash,),
                )
        finally:
            conn.close()

    def append(self, timestamp: float):
        pass


class PersistentRevokedSet:
    def __init__(self, store):
        self.store = store

    def _get_set(self) -> set[str]:
        conn = get_db_connection()
        try:
            rows = conn.execute("SELECT guard_id FROM burned_guards;").fetchall()
            return {r["guard_id"] for r in rows}
        finally:
            conn.close()

    def __contains__(self, item):
        return item in self._get_set()

    def __len__(self):
        return len(self._get_set())

    def __iter__(self):
        return iter(self._get_set())

    def clear(self):
        conn = get_db_connection()
        try:
            with conn:
                conn.execute("DELETE FROM burned_guards;")
        finally:
            conn.close()

    def add(self, guard_id: str):
        pass


class PersistentIssuedSet:
    def __init__(self, store):
        self.store = store

    def _get_set(self) -> set[str]:
        conn = get_db_connection()
        try:
            rows = conn.execute("SELECT guard_id FROM issued_guards;").fetchall()
            return {r["guard_id"] for r in rows}
        finally:
            conn.close()

    def __contains__(self, item):
        return item in self._get_set()

    def __len__(self):
        return len(self._get_set())

    def __iter__(self):
        return iter(self._get_set())

    def clear(self):
        conn = get_db_connection()
        try:
            with conn:
                conn.execute("DELETE FROM issued_guards;")
        finally:
            conn.close()

    def add(self, guard_id: str):
        pass


class ActiveTargetStore:
    MAX_DAILY_GUARD_GENERATIONS = 3
    RATE_LIMIT_WINDOW_SECONDS = 86400.0  # 24 Hours rolling window

    def __init__(self):
        self.creator_device_id: str = "DEV-LOCAL-CREATOR"
        self.creator_device_hash: str = hash_device_id("DEV-LOCAL-CREATOR")
        self._guard_id: str | None = None
        self.target_url: str | None = None
        self.is_sandbox: bool = False
        self.bypass_secret: str | None = None
        self.bound_host_hash: str | None = None
        self.issued_at: int = 0
        self.expires_at: int = 0
        self.is_verified: bool = False
        self.active_guard_active: bool = False
        self.verified_at: int = 0
        self.last_burn_reason: str | None = None
        self.last_revoked_guard_id: str | None = None

        self.generation_timestamps = PersistentGenerationsList(self)
        self.revoked_guard_ids = PersistentRevokedSet(self)
        self.issued_guard_ids = PersistentIssuedSet(self)
        self._load_from_db()

    @property
    def guard_id(self) -> str | None:
        return self._guard_id

    @guard_id.setter
    def guard_id(self, val: str | None):
        self._guard_id = val
        self._save_to_db()

    def _load_from_db(self):
        state = db_get_active_target()
        self.target_url = state.get("target_url") or None
        self.is_sandbox = bool(state.get("is_sandbox", False))
        self._guard_id = state.get("guard_id")
        self.bypass_secret = state.get("handshake_secret")
        if state.get("creator_device_hash"):
            self.creator_device_hash = state["creator_device_hash"]
        self.bound_host_hash = state.get("bound_host_hash")
        self.issued_at = int(state.get("issued_at") or 0)
        self.expires_at = int(state.get("expires_at") or 0)
        self.is_verified = bool(state.get("is_verified", False))
        self.active_guard_active = bool(state.get("active_guard_active", False))
        self.verified_at = self.issued_at
        self.last_burn_reason = state.get("last_burn_reason")

    def _save_to_db(self):
        db_save_active_target({
            "target_url": self.target_url or "",
            "is_sandbox": getattr(self, "is_sandbox", False),
            "guard_id": self._guard_id,
            "handshake_secret": self.bypass_secret,
            "expected_file_sha256": None,
            "creator_device_hash": self.creator_device_hash,
            "bound_host_hash": self.bound_host_hash,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "active_guard_active": self.active_guard_active,
            "is_verified": self.is_verified,
            "last_burn_reason": self.last_burn_reason,
        })

    def get_daily_generations_used(self) -> int:
        cutoff = time.time() - self.RATE_LIMIT_WINDOW_SECONDS
        return db_get_daily_generations_count(self.creator_device_hash, cutoff)

    def get_daily_generations_remaining(self) -> int:
        return max(0, self.MAX_DAILY_GUARD_GENERATIONS - self.get_daily_generations_used())

    def check_generation_quota(self):
        """
        Validates rate limit quota BEFORE any active token modification or revoking.
        """
        if self.get_daily_generations_used() >= self.MAX_DAILY_GUARD_GENERATIONS:
            raise GuardRateLimitError(
                "Daily Guard generation limit reached (3 per 24 hours). Rate limit resets 24 hours after the earliest download."
            )

    def record_generation(self, guard_id: str):
        now = time.time()
        db_record_guard_generation(guard_id, self.creator_device_hash, now)
        self.issued_guard_ids.add(guard_id)

    def set_target(
        self,
        target_url: str,
        guard_id: str,
        bypass_secret: str,
        issued_at: int,
        expires_at: int,
        creator_device_id: str | None = None,
        is_sandbox: bool = False,
    ):
        self.target_url = target_url
        self.is_sandbox = is_sandbox
        self.guard_id = guard_id
        self.bypass_secret = bypass_secret
        self.creator_device_id = creator_device_id or "DEV-LOCAL-CREATOR"
        self.creator_device_hash = hash_device_id(self.creator_device_id)
        self.bound_host_hash = None
        self.issued_at = issued_at
        self.expires_at = expires_at
        self.is_verified = False
        self.active_guard_active = True
        self.verified_at = 0
        self.last_burn_reason = None
        self._save_to_db()

    def mark_verified(self):
        self.is_verified = True
        self.active_guard_active = True
        self.verified_at = int(time.time())
        self._save_to_db()

    def kill(self, device_id: str | None = None) -> tuple[bool, str]:
        """
        Kills the active Guard ID.
        If device_id is provided and does not match creator_device_hash, triggers Trigger 1 (DEVICE_MISMATCH_VIOLATION).
        Otherwise triggers Trigger 3 (MANUAL_USER_KILL).
        """
        if not self.guard_id:
            return True, "No active Guard ID to kill."

        current_guard = self.guard_id
        incoming_hash = hash_device_id(device_id)

        # Trigger 1: Cross-Device Kill Attempt Violation
        if device_id and incoming_hash != self.creator_device_hash:
            burn_guard_id(current_guard, "DEVICE_MISMATCH_VIOLATION", self.creator_device_hash, incoming_hash)
            self.guard_id = None
            self.is_verified = False
            self.is_sandbox = False
            self.active_guard_active = False
            self.expires_at = 0
            self.last_burn_reason = "DEVICE_MISMATCH_VIOLATION"
            self._save_to_db()
            return False, f"DEVICE SECURITY VIOLATION: Guard ID {current_guard} is locked to its creator device. Cross-device access detected — Guard ID has been permanently killed, the 48h timer stopped, and this ID can never be used again."

        # Trigger 3: Manual User Revocation from Creator
        burn_guard_id(current_guard, "MANUAL_USER_KILL", self.creator_device_hash)
        self.guard_id = None
        self.is_verified = False
        self.is_sandbox = False
        self.active_guard_active = False
        self.expires_at = 0
        self.last_burn_reason = "MANUAL_USER_KILL"
        self._save_to_db()
        return True, "Active Guard ID revoked and permanently burned. Load testing locked until re-verified."

    def get_remaining_seconds(self) -> int:
        if not self.is_verified or not self.active_guard_active or self.expires_at == 0:
            return 0
        now = int(time.time())
        rem = self.expires_at - now
        if rem <= 0:
            # Trigger 2: Automatic 48-Hour Expiry Kill
            if self.guard_id and not is_guard_burned(self.guard_id):
                burn_guard_id(self.guard_id, "EXPIRED_48H", self.creator_device_hash)
            self.is_verified = False
            self.active_guard_active = False
            self.last_burn_reason = "EXPIRED_48H"
            self._save_to_db()
            return 0
        return rem

target_store = ActiveTargetStore()

# SSRF Validation Function
def validate_target_url(target_url: str, is_sandbox: bool = False) -> tuple[bool, str, str | None]:
    if not target_url or not target_url.strip():
        return False, "Target URL cannot be empty.", None

    url = target_url.strip()
    parsed = urllib.parse.urlparse(url)

    if parsed.scheme.lower() not in ("http", "https"):
        return False, f"Invalid scheme '{parsed.scheme}'. Only HTTP and HTTPS are permitted.", None

    hostname = parsed.hostname
    if not hostname:
        return False, "Unable to extract valid hostname from target URL.", None

    sandbox_hosts = {"api.myproject.dev", "sandbox.pusher.local"}

    # Sandbox Demo Mode allows sandbox.pusher.local, localhost, or api.myproject.dev sandbox targets
    if is_sandbox:
        return True, "Sandbox demo target permitted.", "127.0.0.1"

    if hostname.lower() in sandbox_hosts or "sandbox" in hostname.lower():
        return True, "Sandbox demo target permitted.", "127.0.0.1"

    # Explicit loopback string names
    if hostname.lower() in ("localhost", "0.0.0.0", "127.0.0.1", "::1"):
        return False, "Loopback addresses (localhost/127.0.0.1) are forbidden for production tests.", None

    # DNS Resolution & IP Range Check
    try:
        addr_info = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as e:
        return False, f"DNS resolution failed for '{hostname}': {str(e)}", None

    resolved_ips = {item[4][0] for item in addr_info}
    for ip_str in resolved_ips:
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return False, f"Resolved invalid IP address: '{ip_str}'", None

        if ip.is_loopback:
            return False, f"SSRF Blocked: Target resolves to loopback IP '{ip_str}'.", ip_str
        if ip.is_private:
            return False, f"SSRF Blocked: Target resolves to private network IP '{ip_str}'.", ip_str
        if ip.is_link_local:
            return False, f"SSRF Blocked: Target resolves to link-local/cloud metadata IP '{ip_str}'.", ip_str
        if ip.is_multicast or ip.is_reserved:
            return False, f"SSRF Blocked: Target resolves to reserved/multicast IP '{ip_str}'.", ip_str

        # Link-local cloud metadata check (169.254.169.254)
        if ip_str == "169.254.169.254":
            return False, "SSRF Blocked: Link-local cloud instance metadata is strictly forbidden.", ip_str

    first_ip = next(iter(resolved_ips), None)
    return True, "Target URL passed SSRF security checks.", first_ip


# Generate Sealed 48h pusher_guard.py
def generate_pusher_guard_file(target_url: str, is_sandbox: bool = False, device_id: str | None = None) -> dict:
    # 1. Kill-First Rule: If an active unrevoked guard already exists, require killing it first
    if target_store.guard_id is not None:
        raise GuardActiveConflictError(
            f"An active Guard ({target_store.guard_id}) already exists. You must kill it first (POST /api/target/kill) before generating a new pusher_guard.py."
        )

    # 2. Rate Limiting Check: Enforce 3 generations per rolling 24-hour window
    # Check quota BEFORE touching active token so rejection preserves state
    target_store.check_generation_quota()

    issued_at = int(time.time())
    expires_at = issued_at + 172800  # Exactly 48 hours (172,800s)

    # 3. Collision-free Guard ID generation (checked against issued, revoked, and burned)
    while True:
        guard_id = f"PG-{secrets.token_hex(2).upper()}-48H"
        if (
            guard_id not in target_store.issued_guard_ids
            and guard_id not in target_store.revoked_guard_ids
            and is_guard_burned(guard_id) is None
        ):
            break

    bypass_secret = f"psh_sec_{secrets.token_hex(16)}"
    creator_device_id = device_id or "DEV-LOCAL-CREATOR"
    creator_device_hash = hash_device_id(creator_device_id)

    # Set as active target in store (Enforces 1-project active limit)
    target_store.set_target(
        target_url=target_url,
        guard_id=guard_id,
        bypass_secret=bypass_secret,
        issued_at=issued_at,
        expires_at=expires_at,
        creator_device_id=creator_device_id,
        is_sandbox=is_sandbox,
    )
    target_store.record_generation(guard_id)

    # Vault payload
    vault_payload = {
        "guard_id": guard_id,
        "target_url": target_url,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "bypass_secret": bypass_secret,
        "creator_device_hash": creator_device_hash,
    }
    raw_json = json.dumps(vault_payload).encode("utf-8")
    compressed = zlib.compress(raw_json, level=9)
    sealed_b85 = base64.b85encode(compressed).decode("ascii")

    # Generate Python middleware template body
    body_template = f'''# pusher_guard.py — Sealed 48-Hour Verification & Rate Limit Bypass Middleware
# Generated by Pusher Load Testing Engine
# Guard ID: {guard_id}
# Target: {target_url}
# Expiry: {expires_at} (48 Hours from generation)

import base64
import hashlib
import hmac
import json
import os
import platform
import sys
import time
import uuid
import zlib
from typing import Any

# SEALED LOCKBOX VAULT
_GUARD_ID = "{guard_id}"
_SEALED_VAULT = "{sealed_b85}"

def _load_vault() -> dict:
    try:
        decompressed = zlib.decompress(base64.b85decode(_SEALED_VAULT.encode("ascii")))
        data = json.loads(decompressed.decode("utf-8"))
        if data.get("guard_id") != _GUARD_ID:
            raise RuntimeError("PUSHER GUARD LOCKED: Unauthorized modification to pusher_guard.py detected.")
        return data
    except Exception as exc:
        raise RuntimeError("PUSHER GUARD LOCKED: Unauthorized modification to pusher_guard.py detected.") from exc

_VAULT = _load_vault()
GUARD_ID = _VAULT["guard_id"]
EXPIRES_AT = _VAULT["expires_at"]
BYPASS_SECRET = _VAULT["bypass_secret"]
CREATOR_DEVICE_HASH = _VAULT.get("creator_device_hash", "")

_BOUND_HOST = None

def _get_host_fingerprint() -> str:
    global _BOUND_HOST
    if _BOUND_HOST is None:
        try:
            node = str(uuid.getnode())
            pnode = str(platform.node())
            _BOUND_HOST = hashlib.sha256(f"{{node}}:{{pnode}}".encode("utf-8")).hexdigest()[:16]
        except Exception:
            _BOUND_HOST = "host_fallback_hw"
    return _BOUND_HOST

def _verify_self_integrity():
    """Verifies byte-level integrity against unauthorized tamper modifications."""
    mod_file = getattr(sys.modules.get(__name__), "__file__", None) or globals().get("__file__")
    if mod_file and os.path.isfile(mod_file):
        try:
            with open(mod_file, "r", encoding="utf-8") as f:
                content = f.read().replace("\\r\\n", "\\n")
            lines = content.split("\\n")
            body_lines = [l for l in lines if not l.startswith("_SEAL = ") and not l.startswith("# SHA-256 Checksum:")]
            body_text = "\\n".join(body_lines)
            calc_sha = hashlib.sha256(body_text.encode("utf-8")).hexdigest()
            if calc_sha != _SEAL:
                raise RuntimeError("PUSHER GUARD LOCKED: Unauthorized modification to pusher_guard.py detected.")
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError("PUSHER GUARD LOCKED: Unauthorized modification to pusher_guard.py detected.") from exc

_verify_self_integrity()

def is_active() -> bool:
    """Returns True if within the 48-hour valid lifetime."""
    return time.time() < EXPIRES_AT

def calculate_challenge_proof(nonce: str) -> str:
    """Calculates cryptographic HMAC challenge response for Pusher verifier."""
    return hmac.new(BYPASS_SECRET.encode("utf-8"), nonce.encode("utf-8"), hashlib.sha256).hexdigest()

def pusher_guard_bypass_dep(request: Any = None) -> bool:
    """FastAPI/Starlette dependency helper to check if request was verified and signed by Pusher."""
    if request is None:
        return False
    state = getattr(request, "state", None)
    return bool(getattr(state, "pusher_bypass", False))

def setup_pusher_guard(app: Any):
    """
    Mounts /__pusher_verify endpoint and signed rate-limit & auth bypass middleware for FastAPI / Starlette / Flask.
    """
    _verify_self_integrity()

    # 1. FastAPI / Starlette Integration
    if hasattr(app, "add_api_route") and hasattr(app, "middleware"):
        from fastapi import Request
        from fastapi.responses import JSONResponse

        @app.get("/__pusher_verify")
        async def pusher_verify_handler(nonce: str = ""):
            if not is_active():
                return JSONResponse(status_code=403, content={{"status": "EXPIRED", "detail": "Pusher Guard token expired"}})
            proof = calculate_challenge_proof(nonce)
            file_hash = _SEAL
            try:
                mod_file = getattr(sys.modules.get(__name__), "__file__", None) or globals().get("__file__")
                if mod_file and os.path.isfile(mod_file):
                    with open(mod_file, "rb") as f:
                        file_hash = hashlib.sha256(f.read()).hexdigest()
            except Exception:
                pass
            return JSONResponse(content={{
                "status": "ACTIVE",
                "guard_id": GUARD_ID,
                "proof": proof,
                "expires_at": EXPIRES_AT,
                "file_sha256": file_hash,
                "host_fingerprint": _get_host_fingerprint(),
                "auth_bypass_ready": True
            }})

        @app.middleware("http")
        async def pusher_bypass_middleware(request: Request, call_next):
            x_guard_id = request.headers.get("X-Pusher-Guard-ID", "")
            x_ts = request.headers.get("X-Pusher-Timestamp", "")
            x_sig = request.headers.get("X-Pusher-Signature", "")

            is_signed = False
            if is_active() and x_guard_id == GUARD_ID and x_ts and x_sig:
                try:
                    curr_min = int(time.time() // 60)
                    req_min = int(x_ts)
                    # Clock skew tolerance: current_unix_minute ± 1
                    if abs(curr_min - req_min) <= 1:
                        expected_sig = hmac.new(
                            BYPASS_SECRET.encode("utf-8"),
                            f"{{GUARD_ID}}:{{x_ts}}".encode("utf-8"),
                            hashlib.sha256
                        ).hexdigest()
                        if hmac.compare_digest(x_sig, expected_sig):
                            is_signed = True
                except Exception:
                    is_signed = False

            if is_signed:
                # 1. Bypass App Rate Limiters & IP Throttling
                request.scope["pusher_verified"] = True
                request.state.pusher_bypass = True
                rand_ip_suffix = (int(time.time() * 1000) % 250) + 1
                request.scope["client"] = (f"198.51.100.{{rand_ip_suffix}}", 12345)

                # 2. Bypass App Authentication / CSRF Checks
                raw_headers = list(request.scope.get("headers", []))
                header_names = [h[0].lower() for h in raw_headers]
                if b"authorization" not in header_names:
                    synth_auth = f"Bearer pusher_bypass_{{GUARD_ID}}".encode("latin-1")
                    raw_headers.append((b"authorization", synth_auth))
                    request.scope["headers"] = raw_headers

                request.scope["user"] = {{
                    "id": "pusher_load_test_vu",
                    "role": "load_tester",
                    "bypass_auth": True
                }}
            else:
                request.state.pusher_bypass = False

            return await call_next(request)

    # 2. Flask Integration
    elif hasattr(app, "route") and hasattr(app, "before_request"):
        from flask import request, jsonify, g

        @app.route("/__pusher_verify", methods=["GET"])
        def pusher_verify_flask():
            if not is_active():
                return jsonify({{"status": "EXPIRED", "detail": "Pusher Guard token expired"}}), 403
            nonce = request.args.get("nonce", "")
            proof = calculate_challenge_proof(nonce)
            return jsonify({{
                "status": "ACTIVE",
                "guard_id": GUARD_ID,
                "proof": proof,
                "expires_at": EXPIRES_AT,
                "file_sha256": _SEAL,
                "host_fingerprint": _get_host_fingerprint(),
                "auth_bypass_ready": True
            }})

        @app.before_request
        def pusher_bypass_flask():
            x_guard_id = request.headers.get("X-Pusher-Guard-ID", "")
            x_ts = request.headers.get("X-Pusher-Timestamp", "")
            x_sig = request.headers.get("X-Pusher-Signature", "")

            is_signed = False
            if is_active() and x_guard_id == GUARD_ID and x_ts and x_sig:
                try:
                    curr_min = int(time.time() // 60)
                    if abs(curr_min - int(x_ts)) <= 1:
                        expected_sig = hmac.new(
                            BYPASS_SECRET.encode("utf-8"),
                            f"{{GUARD_ID}}:{{x_ts}}".encode("utf-8"),
                            hashlib.sha256
                        ).hexdigest()
                        if hmac.compare_digest(x_sig, expected_sig):
                            is_signed = True
                except Exception:
                    is_signed = False

            if is_signed:
                g.pusher_bypass = True
                setattr(request, "is_pusher_test", True)
            else:
                g.pusher_bypass = False
                setattr(request, "is_pusher_test", False)
'''

    # SHA-256 Anti-Tamper Checksum
    body_normalized = body_template.replace("\r\n", "\n")
    checksum = hashlib.sha256(body_normalized.encode("utf-8")).hexdigest()
    final_code = f'_SEAL = "{checksum}"\n# SHA-256 Checksum: {checksum}\n' + body_normalized

    return {
        "guard_id": guard_id,
        "target_url": target_url,
        "creator_device_id": creator_device_id,
        "creator_device_hash": creator_device_hash,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "remaining_seconds": 172800,
        "checksum_sha256": checksum,
        "filename": "pusher_guard.py",
        "content": final_code,
        "daily_generations_used": target_store.get_daily_generations_used(),
        "daily_generations_max": target_store.MAX_DAILY_GUARD_GENERATIONS,
        "daily_generations_remaining": target_store.get_daily_generations_remaining(),
        "superseded_guard_id": None,
        "revoked_count": len(target_store.revoked_guard_ids),
        "last_revoked_guard_id": target_store.last_revoked_guard_id,
    }


# Live Target Verification Handler
async def verify_target_handshake(
    target_url: str,
    guard_id: str,
    is_sandbox: bool = False,
    device_id: str | None = None
) -> tuple[bool, str, int]:
    # Permanent Burn Check: Check SQLite burned_guards table
    burned_record = is_guard_burned(guard_id)
    if burned_record:
        burn_reason = burned_record.get("burn_reason", "REVOKED")
        return False, f"HTTP 403 Forbidden: Guard ID {guard_id} has been permanently burned ({burn_reason}) and can never be used again.", 0

    if guard_id in target_store.revoked_guard_ids:
        return False, f"HTTP 403 Forbidden: Guard ID {guard_id} has been permanently revoked and burned.", 0

    # Trigger 1: Cross-Device Usage Violation Check
    incoming_device_hash = hash_device_id(device_id)
    if target_store.guard_id and guard_id == target_store.guard_id:
        if device_id and incoming_device_hash != target_store.creator_device_hash:
            burn_guard_id(guard_id, "DEVICE_MISMATCH_VIOLATION", target_store.creator_device_hash, incoming_device_hash)
            target_store.expires_at = int(time.time())
            target_store.is_verified = False
            target_store.active_guard_active = False
            target_store.last_burn_reason = "DEVICE_MISMATCH_VIOLATION"
            try:
                from backend.core.load_engine import load_engine
                if load_engine.is_running:
                    import asyncio
                    asyncio.create_task(load_engine.stop())
            except Exception:
                pass
            return False, f"HTTP 403 Forbidden: DEVICE SECURITY VIOLATION: Guard ID {guard_id} is locked to its creator device. Cross-device access detected — Guard ID has been permanently killed, the 48h timer stopped, and this ID can never be used again.", 0

    # Trigger 2: Automatic 48-Hour Expiry Check
    if target_store.guard_id == guard_id and target_store.expires_at > 0 and int(time.time()) >= target_store.expires_at:
        burn_guard_id(guard_id, "EXPIRED_48H", target_store.creator_device_hash)
        target_store.expires_at = 0
        target_store.is_verified = False
        target_store.active_guard_active = False
        target_store.last_burn_reason = "EXPIRED_48H"
        return False, f"HTTP 403 Forbidden: 48-Hour verification window expired. Guard ID {guard_id} has been permanently killed for all users.", 0

    parsed = urllib.parse.urlparse(target_url)
    hostname = (parsed.hostname or "").lower()
    sandbox_hosts = {"api.myproject.dev", "sandbox.pusher.local", "localhost", "127.0.0.1", "0.0.0.0"}

    # Sandbox demo verification passes immediately in memory without external DNS / HTTP calls
    is_sandbox_mode = (
        is_sandbox
        or getattr(target_store, "is_sandbox", False)
        or "sandbox" in target_url.lower()
        or hostname in sandbox_hosts
    )

    if is_sandbox_mode:
        active_id = guard_id or target_store.guard_id or f"PG-SNDB-{secrets.token_hex(2).upper()}-48H"
        target_store.set_target(
            target_url=target_url,
            guard_id=active_id,
            bypass_secret=target_store.bypass_secret or "sandbox_secret",
            issued_at=int(time.time()),
            expires_at=int(time.time()) + 172800,
            creator_device_id=device_id or target_store.creator_device_id,
            is_sandbox=True,
        )
        target_store.mark_verified()
        return True, "Sandbox demo target verified successfully.", 172800

    if not target_store.guard_id or target_store.guard_id != guard_id:
        return False, "Guard ID mismatch or guard file not generated for this session.", 0

    # Cryptographic challenge-response handshake
    nonce = secrets.token_hex(16)
    expected_proof = hmac.new(
        target_store.bypass_secret.encode("utf-8"),
        nonce.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    endpoint = f"{parsed.scheme}://{parsed.netloc}/__pusher_verify?nonce={nonce}"

    try:
        async with httpx.AsyncClient(timeout=5.0, verify=False) as client:
            resp = await client.get(endpoint)
            if resp.status_code != 200:
                return False, f"Target server returned HTTP {resp.status_code} at {endpoint}. Ensure setup_pusher_guard(app) is mounted.", 0

            data = resp.json()
            returned_proof = data.get("proof")
            returned_guard = data.get("guard_id")
            returned_host = data.get("host_fingerprint")

            if returned_guard != guard_id:
                return False, f"Guard ID mismatch: expected {guard_id}, received {returned_guard}", 0

            if not hmac.compare_digest(returned_proof or "", expected_proof):
                return False, "Cryptographic challenge proof verification failed.", 0

            # Host machine lock verification
            if returned_host:
                if target_store.bound_host_hash is None:
                    target_store.bound_host_hash = returned_host
                elif target_store.bound_host_hash != returned_host:
                    # Host machine mismatch -> Trigger 1: DEVICE_MISMATCH_VIOLATION
                    burn_guard_id(guard_id, "DEVICE_MISMATCH_VIOLATION", target_store.creator_device_hash, f"HOST-{returned_host}")
                    target_store.expires_at = 0
                    target_store.is_verified = False
                    target_store.active_guard_active = False
                    target_store.last_burn_reason = "DEVICE_MISMATCH_VIOLATION"
                    return False, f"HTTP 403 Forbidden: HOST MACHINE SECURITY VIOLATION: Guard ID {guard_id} was deployed on an unauthorized host machine ({returned_host} != {target_store.bound_host_hash}). Guard ID permanently killed.", 0

            # Verified successfully
            target_store.mark_verified()
            remaining = target_store.get_remaining_seconds()
            return True, "Target verified successfully. 48-Hour load-testing window unlocked.", remaining

    except httpx.RequestError as exc:
        return False, f"Connection failed to '{endpoint}': {str(exc)}", 0


# Live WAF Header Pass-Through Diagnostic Probe
async def probe_waf_bypass(target_url: str, is_sandbox: bool = False) -> dict:
    active_id = target_store.guard_id or "PG-DEMO-48H"

    parsed = urllib.parse.urlparse(target_url)
    hostname = (parsed.hostname or "").lower()
    sandbox_hosts = {"api.myproject.dev", "sandbox.pusher.local", "localhost", "127.0.0.1", "0.0.0.0"}

    # Sandbox simulation mode
    if is_sandbox or "sandbox" in target_url.lower() or hostname in sandbox_hosts:
        return {
            "status_code": 200,
            "detected_waf": "None (Sandbox Simulated)",
            "bypass_passed": True,
            "latency_ms": 14,
            "recommendation": "WAF BYPASS VERIFIED: X-Pusher-Guard-Token accepted by origin without 403/429 challenge.",
            "target_url": target_url,
            "probe_endpoint": f"{target_url.rstrip('/')}/__pusher_verify?nonce=waf_probe",
            "injected_headers": {
                "X-Pusher-Guard-Token": active_id,
                "User-Agent": "Pusher-LoadEngine/1.0"
            }
        }

    endpoint = f"{parsed.scheme}://{parsed.netloc}/__pusher_verify?nonce=waf_probe"
    headers = {
        "X-Pusher-Guard-Token": active_id,
        "User-Agent": "Pusher-LoadEngine/1.0"
    }

    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=8.0, verify=False) as client:
            resp = await client.get(endpoint, headers=headers)
            latency_ms = int((time.perf_counter() - t0) * 1000)

            server = resp.headers.get("server", "").lower()
            detected_waf = "Unknown / Direct Origin"
            if "cloudflare" in server or "cf-ray" in resp.headers or "cf-mitigated" in resp.headers:
                detected_waf = "Cloudflare WAF"
            elif "awselb" in server or "x-amzn-requestid" in resp.headers or "x-amz-cf-id" in resp.headers:
                detected_waf = "AWS WAF / CloudFront"
            elif "vercel" in server or "x-vercel-id" in resp.headers:
                detected_waf = "Vercel Firewall / Edge"
            elif "nginx" in server:
                detected_waf = "NGINX Reverse Proxy"

            code = resp.status_code
            if code == 200:
                bypass_passed = True
                recommendation = f"WAF BYPASS VERIFIED: Origin responded with HTTP 200 OK. Bypass header '{active_id}' is honored."
            elif code == 403:
                bypass_passed = False
                recommendation = f"HTTP 403 Forbidden: WAF blocked request. Verify your custom rule skips/allows 'x-pusher-guard-token' == '{active_id}'."
            elif code == 429:
                bypass_passed = False
                recommendation = "HTTP 429 Rate Limited: Edge rate limiting tripped. Ensure your WAF rate limiting rule has 'Skip rate limiting' checked for this token."
            else:
                bypass_passed = False
                recommendation = f"Received HTTP {code}. Verify your origin server has mounted pusher_guard.py and WAF allows the bypass header."

            return {
                "status_code": code,
                "detected_waf": detected_waf,
                "bypass_passed": bypass_passed,
                "latency_ms": latency_ms,
                "recommendation": recommendation,
                "target_url": target_url,
                "probe_endpoint": endpoint,
                "injected_headers": headers,
            }

    except httpx.RequestError as exc:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return {
            "status_code": 0,
            "detected_waf": "Connection Error",
            "bypass_passed": False,
            "latency_ms": latency_ms,
            "recommendation": f"Connection failed to '{endpoint}': {str(exc)}. Ensure the target domain is reachable.",
            "target_url": target_url,
            "probe_endpoint": endpoint,
            "injected_headers": headers,
        }

