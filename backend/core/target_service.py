"""
Target Service:
- SSRF Boundary Validation & IP range enforcement
- Sealed 48-Hour pusher_guard.py generation with SHA-256 integrity checksums
- Live challenge-response verification (/__pusher_verify?nonce=...) and Kill revocation
"""

from contextvars import ContextVar
import base64
import difflib
import hashlib
import hmac
import json
import re
import secrets
import time
import zlib
import httpx
from backend.core.request_owner import request_owner
from backend.core.dry_run_control import cancel_guard_dry_runs
from backend.core.target_policy import (
    DestinationError, bound_target, origin, parse_target, resolve_addresses, sandbox_target, target_client,
)

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
    cancel_guard_dry_runs(guard_id, expired=reason == "EXPIRED_48H")
    target_store = active_target()
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

    def __init__(self, owner_id="default_test_user"):
        self.owner_id = owner_id
        self.creator_device_id: str = "DEV-LOCAL-CREATOR"
        self.creator_device_hash: str = hash_device_id("DEV-LOCAL-CREATOR")
        self._guard_id: str | None = None
        self.target_url: str | None = None
        self.requires_target_query = False
        self.is_sandbox: bool = False
        self.bypass_secret: str | None = None
        self.expected_file_sha256: str | None = None
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
        state = db_get_active_target(self.owner_id)
        self.target_url = state.get("target_url") or None
        self.requires_target_query = state["requires_target_query"]
        self.is_sandbox = bool(state.get("is_sandbox", False))
        self._guard_id = state.get("guard_id")
        self.bypass_secret = state.get("handshake_secret")
        self.expected_file_sha256 = state.get("expected_file_sha256")
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
            "requires_target_query": self.requires_target_query,
            "is_sandbox": getattr(self, "is_sandbox", False),
            "guard_id": self._guard_id,
            "handshake_secret": self.bypass_secret,
            "expected_file_sha256": self.expected_file_sha256,
            "creator_device_hash": self.creator_device_hash,
            "bound_host_hash": self.bound_host_hash,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "active_guard_active": self.active_guard_active,
            "is_verified": self.is_verified,
            "last_burn_reason": self.last_burn_reason,
        }, self.owner_id)

    def get_daily_generations_used(self) -> int:
        cutoff = time.time() - self.RATE_LIMIT_WINDOW_SECONDS
        return db_get_daily_generations_count(self.creator_device_hash, cutoff, self.owner_id)

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
        db_record_guard_generation(guard_id, self.creator_device_hash, now, self.owner_id)
        self.issued_guard_ids.add(guard_id)

    def set_target(
        self,
        target_url: str,
        guard_id: str,
        bypass_secret: str | None,
        issued_at: int,
        expires_at: int,
        creator_device_id: str | None = None,
        is_sandbox: bool = False,
        expected_file_sha256: str | None = None,
    ):
        self.set_target_template(parse_target(target_url))
        self.is_sandbox = is_sandbox
        self._guard_id = guard_id
        self.bypass_secret = bypass_secret
        self.expected_file_sha256 = expected_file_sha256
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

    def set_target_template(self, url: httpx.URL):
        self.target_url = str(url.copy_with(query=None))
        self.requires_target_query = bool(url.query)

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
            self._guard_id = None
            self.bypass_secret = None
            self.expected_file_sha256 = None
            self.is_verified = False
            self.is_sandbox = False
            self.active_guard_active = False
            self.expires_at = 0
            self.last_burn_reason = "DEVICE_MISMATCH_VIOLATION"
            self._save_to_db()
            return False, f"DEVICE SECURITY VIOLATION: Guard ID {current_guard} is locked to its creator device. Cross-device access detected — Guard ID has been permanently killed, the 48h timer stopped, and this ID can never be used again."

        # Trigger 3: Manual User Revocation from Creator
        burn_guard_id(current_guard, "MANUAL_USER_KILL", self.creator_device_hash)
        self._guard_id = None
        self.bypass_secret = None
        self.expected_file_sha256 = None
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
target_scope: ContextVar[ActiveTargetStore | None] = ContextVar("target_scope", default=None)


def active_target() -> ActiveTargetStore:
    owner = request_owner.get()
    if owner == "default_test_user":
        return target_store
    current = target_scope.get()
    if current is None:
        current = ActiveTargetStore(owner)
        target_scope.set(current)
    return current

COMMON_DOMAINS = [
    "github.com",
    "gitlab.com",
    "vercel.app",
    "netlify.app",
    "onrender.com",
    "railway.app",
    "fly.dev",
    "herokuapp.com",
    "cloudflare.com",
    "google.com",
    "example.com",
]


class ValidationResult(dict):
    """
    Structured URL & SSRF Validation result.
    Behaves as a dict for JSON serialization while supporting 3-tuple unpacking
    `(valid, message, resolved_ip)` for backwards compatibility.
    """
    def __iter__(self):
        yield self.get("valid", False)
        yield self.get("message", "")
        yield self.get("resolved_ip", None)

    @property
    def valid(self) -> bool:
        return self.get("valid", False)

    @property
    def reachable(self) -> bool:
        return self.get("reachable", False)

    @property
    def message(self) -> str:
        return self.get("message", "")


async def validate_target_url(target_url: str, is_sandbox: bool = False) -> ValidationResult:
    """Check syntax and DNS readiness without contacting an unverified web server."""
    try:
        url = sandbox_target(target_url.strip()) if is_sandbox else parse_target(target_url.strip())
    except DestinationError as exc:
        return ValidationResult(valid=False, ready=False, reachable=False, status="INVALID_URL",
                                message=str(exc), suggestions=[])
    try:
        addresses = await resolve_addresses(*origin(url)[1:], is_sandbox)
    except DestinationError as exc:
        matches = difflib.get_close_matches(url.host, COMMON_DOMAINS, n=2, cutoff=0.5)
        return ValidationResult(valid=False, ready=False, reachable=False, status="DNS_REJECTED",
                                message=str(exc), suggestions=[f"https://{item}" for item in matches])
    return ValidationResult(
        valid=True, ready=True, reachable=False, status="SANDBOX_READY" if is_sandbox else "DNS_READY",
        message="Sandbox destination is configured." if is_sandbox else "DNS checked. Verify ownership with your Guard.",
        resolved_ip=addresses[0], suggestions=[],
    )


def verified_destination(value: str, is_sandbox: bool) -> httpx.URL:
    target_store = active_target()
    if (
        not target_store.target_url
        or not target_store.guard_id
        or bool(target_store.is_sandbox) != is_sandbox
        or target_store.get_remaining_seconds() <= 0
        or is_guard_burned(target_store.guard_id)
    ):
        raise DestinationError("Verify the target before using it.")
    if not is_sandbox and not target_store.expected_file_sha256:
        raise DestinationError("Replace the old Guard and verify the target before using it.")
    base = sandbox_target(target_store.target_url) if is_sandbox else parse_target(target_store.target_url)
    return bound_target(value, base, is_sandbox)


def generate_pusher_guard_file(target_url: str, is_sandbox: bool = False, device_id: str | None = None) -> dict:
    target_store = active_target()
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

    authority = str(parse_target(target_url).copy_with(path="/", query=None)).rstrip("/")

    # Vault payload
    vault_payload = {
        "guard_id": guard_id,
        "authority": authority,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "bypass_secret": bypass_secret,
        "creator_device_hash": creator_device_hash,
    }
    raw_json = json.dumps(vault_payload).encode("utf-8")
    compressed = zlib.compress(raw_json, level=9)
    sealed_b85 = base64.b85encode(compressed).decode("ascii")

    body_template = f'''# pusher_guard.py — Pusher target ownership verification
import base64
import hashlib
import hmac
import json
from pathlib import Path
import platform
import re
import time
import uuid
import zlib

_SEALED_VAULT = "{sealed_b85}"
_VAULT = json.loads(zlib.decompress(base64.b85decode(_SEALED_VAULT)).decode("utf-8"))
GUARD_ID = _VAULT["guard_id"]
EXPIRES_AT = _VAULT["expires_at"]


def _verify_self_integrity():
    raw = Path(__file__).read_bytes()
    lines = raw.decode("utf-8").replace("\\r\\n", "\\n").split("\\n")
    body = "\\n".join(line for line in lines if not line.startswith(("_SEAL = ", "# SHA-256 Checksum:")))
    if hashlib.sha256(body.encode("utf-8")).hexdigest() != _SEAL:
        raise RuntimeError("PUSHER GUARD LOCKED: Unauthorized modification to pusher_guard.py detected.")
    return hashlib.sha256(raw).hexdigest()


_FILE_SHA256 = _verify_self_integrity()


def is_active():
    return time.time() < EXPIRES_AT


def _verify(nonce):
    if not is_active():
        return {{"status": "EXPIRED"}}, 403
    if not re.fullmatch(r"[0-9a-f]{{32}}", nonce):
        return {{"status": "INVALID_CHALLENGE"}}, 400
    key = _VAULT["bypass_secret"].encode("utf-8")
    machine = f"{{uuid.getnode()}}:{{platform.node()}}".encode("utf-8")
    host_tag = hmac.new(key, b"pusher-host-v2:" + machine, hashlib.sha256).hexdigest()
    message = json.dumps(
        ["pusher-ownership-v2", _VAULT["authority"], GUARD_ID, nonce, _FILE_SHA256, host_tag],
        separators=(",", ":"),
    ).encode("utf-8")
    proof = hmac.new(key, message, hashlib.sha256).hexdigest()
    return {{
        "status": "ACTIVE", "guard_id": GUARD_ID, "proof": proof,
        "file_sha256": _FILE_SHA256, "host_fingerprint": host_tag,
    }}, 200


def setup_pusher_guard(app):
    _verify_self_integrity()
    if hasattr(app, "add_route"):
        from starlette.responses import JSONResponse

        async def verify_target(request):
            body, status = _verify(request.query_params.get("nonce", ""))
            return JSONResponse(body, status_code=status)

        app.add_route("/__pusher_verify", verify_target, methods=["GET"], include_in_schema=False)
    elif hasattr(app, "add_url_rule"):
        from flask import jsonify, request

        def verify_target():
            body, status = _verify(request.args.get("nonce", ""))
            return jsonify(body), status

        app.add_url_rule("/__pusher_verify", "pusher_verify", verify_target, methods=["GET"])
    else:
        raise TypeError("Pusher Guard supports FastAPI, Starlette, and Flask applications.")
'''

    # SHA-256 Anti-Tamper Checksum
    body_normalized = body_template.replace("\r\n", "\n")
    checksum = hashlib.sha256(body_normalized.encode("utf-8")).hexdigest()
    final_code = f'_SEAL = "{checksum}"\n# SHA-256 Checksum: {checksum}\n' + body_normalized

    file_sha256 = hashlib.sha256(final_code.encode("utf-8")).hexdigest()
    target_store.set_target(
        target_url=target_url, guard_id=guard_id, bypass_secret=bypass_secret,
        issued_at=issued_at, expires_at=expires_at, creator_device_id=creator_device_id,
        is_sandbox=is_sandbox, expected_file_sha256=file_sha256,
    )
    target_store.record_generation(guard_id)

    return {
        "guard_id": guard_id,
        "target_url": target_store.target_url,
        "requires_target_query": target_store.requires_target_query,
        "creator_device_id": creator_device_id,
        "creator_device_hash": creator_device_hash,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "remaining_seconds": 172800,
        "checksum_sha256": file_sha256,
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
    target_store = active_target()
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
                if load_engine.is_running and load_engine.owner_id == request_owner.get():
                    load_engine.request_stop("STOPPED (GUARD_REVOKED)")
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

    try:
        if is_sandbox:
            target = sandbox_target(target_url)
            if target_store.active_guard_active and not target_store.is_sandbox:
                return False, "Revoke the active Guard before verifying a sandbox target.", 0
            active_id = guard_id or f"PG-SNDB-{secrets.token_hex(8).upper()}-48H"
            target_store.set_target(
                target_url=str(target), guard_id=active_id, bypass_secret=None,
                issued_at=int(time.time()), expires_at=int(time.time()) + 172800,
                creator_device_id=device_id, is_sandbox=True,
            )
            target_store.mark_verified()
            return True, "Sandbox demo target verified successfully.", 172800

        if not target_store.guard_id or target_store.guard_id != guard_id or target_store.is_sandbox:
            return False, "Guard ID mismatch or guard file not generated for this session.", 0
        if not target_store.bypass_secret or not target_store.target_url:
            return False, "Generate a Guard for the target before verification.", 0
        if not target_store.expected_file_sha256:
            return False, "Replace the old Guard before verification.", 0
        target = bound_target(target_url, parse_target(target_store.target_url), False)
    except DestinationError as exc:
        return False, str(exc), 0

    # Cryptographic challenge-response handshake
    secret = target_store.bypass_secret
    expected_digest = target_store.expected_file_sha256
    nonce = secrets.token_hex(16)
    authority = str(target.copy_with(path="/", query=None)).rstrip("/")

    endpoint = target.copy_with(path="/__pusher_verify", params={"nonce": nonce})

    try:
        async with target_client(target) as client, client.stream("GET", endpoint) as response:
            if response.status_code != 200:
                return False, f"Target returned HTTP {response.status_code}. Check that Pusher Guard is mounted.", 0
            body = bytearray()
            async for chunk in response.aiter_bytes(chunk_size=4096):
                body.extend(chunk)
                if len(body) > 8192:
                    return False, "Guard verification response exceeded 8 KiB.", 0
            data = json.loads(body)
            if not isinstance(data, dict):
                return False, "Invalid Guard verification response.", 0
            returned_proof = data.get("proof")
            returned_guard = data.get("guard_id")
            returned_host = data.get("host_fingerprint")

            if returned_guard != guard_id:
                return False, "Guard ID mismatch.", 0
            if data.get("status") != "ACTIVE" or data.get("file_sha256") != expected_digest:
                return False, "The installed Guard does not match the issued artifact.", 0
            if not isinstance(returned_host, str) or not re.fullmatch(r"[0-9a-f]{64}", returned_host):
                return False, "Invalid Guard host tag.", 0
            message = json.dumps(
                ["pusher-ownership-v2", authority, guard_id, nonce, expected_digest, returned_host],
                separators=(",", ":"),
            ).encode("utf-8")
            expected_proof = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()

            if (not isinstance(returned_proof, str)
                or not re.fullmatch(r"[0-9a-f]{64}", returned_proof)
                or not hmac.compare_digest(returned_proof, expected_proof)):
                return False, "Cryptographic challenge proof verification failed.", 0

            if (
                (request_owner.get() != "default_test_user"
                 and db_get_active_target(request_owner.get()).get("guard_id") != guard_id)
                or target_store.guard_id != guard_id
                or target_store.bypass_secret != secret
                or target_store.expected_file_sha256 != expected_digest
                or not target_store.active_guard_active or target_store.expires_at <= time.time()
                or is_guard_burned(guard_id)
            ):
                return False, "The Guard expired or changed during verification.", 0

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
            target_store.set_target_template(target)
            target_store.mark_verified()
            remaining = target_store.get_remaining_seconds()
            return True, "Target verified successfully. 48-Hour load-testing window unlocked.", remaining

    except (httpx.RequestError, ValueError) as exc:
        return False, f"Verification failed: {exc}", 0


async def probe_edge(target_url: str, is_sandbox: bool = False) -> dict:
    target = verified_destination(target_url, is_sandbox)
    endpoint = target.copy_with(query=None)
    if is_sandbox:
        return {
            "simulated": True,
            "status_code": None,
            "edge_hint": None,
            "latency_ms": None,
            "recommendation": "Sandbox simulation. No HTTP request was sent.",
            "probe_endpoint": str(endpoint),
        }

    headers = {"User-Agent": "Pusher-LoadEngine/1.0"}

    t0 = time.perf_counter()
    try:
        async with target_client(target, timeout=8.0) as client, client.stream("HEAD", endpoint, headers=headers) as resp:
            latency_ms = int((time.perf_counter() - t0) * 1000)

            server = resp.headers.get("server", "").lower()
            edge_hint = None
            if "cloudflare" in server or "cf-ray" in resp.headers or "cf-mitigated" in resp.headers:
                edge_hint = "Cloudflare"
            elif "awselb" in server or "x-amzn-requestid" in resp.headers or "x-amz-cf-id" in resp.headers:
                edge_hint = "AWS"
            elif "vercel" in server or "x-vercel-id" in resp.headers:
                edge_hint = "Vercel"
            elif "nginx" in server:
                edge_hint = "NGINX"

            code = resp.status_code
            recommendation = {
                403: "The request was refused. Check the app and edge logs for the reason.",
                429: "The request was rate limited. Check the app and edge logs to identify the limiter.",
                405: "This endpoint does not support HEAD. Choose an endpoint that supports it.",
                501: "HEAD is not implemented for this route. Choose an endpoint that supports it.",
            }.get(code, f"The endpoint returned HTTP {code} to one HEAD request.")

            return {
                "status_code": code,
                "edge_hint": edge_hint,
                "simulated": False,
                "latency_ms": latency_ms,
                "recommendation": recommendation,
                "probe_endpoint": str(endpoint),
            }

    except httpx.RequestError:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return {
            "status_code": None,
            "edge_hint": None,
            "simulated": False,
            "latency_ms": latency_ms,
            "recommendation": "The probe failed before receiving an HTTP response. Check reachability and TLS.",
            "probe_endpoint": str(endpoint),
        }

