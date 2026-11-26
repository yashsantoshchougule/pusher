"""
Journey Service for Multi-Step Sequential API Testing:
- In-memory Journey Store with pre-configured 3-step Sandbox Flow
- Same-Origin SSRF Step Validator
- 1-VU Dry-Run Validator with First-4KB Token Extraction and Interpolation
"""

import asyncio
from dataclasses import dataclass
import json
import math
import re
import time
from urllib.parse import quote
import httpx
from pydantic import BaseModel, Field, JsonValue, ValidationError, field_validator

from backend.core.dry_run_control import DryRunControl
from backend.core.request_owner import request_owner
from backend.core.target_policy import DestinationError, journey_target, parse_target, sandbox_target, target_client


class JourneyStepModel(BaseModel):
    step_id: int | str | None = None
    name: str = Field("Step", min_length=1, max_length=100)
    method: str = Field("GET", pattern=r"(?i)^(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)$")
    path: str = Field(..., min_length=1)
    headers: dict[str, str] = Field(default_factory=dict)
    body: JsonValue = None
    required_headers: list[str] = Field(default_factory=list)
    requires_body: bool = False
    requires_query: bool = False
    expected_status: int = Field(200, ge=100, le=599)
    extract_json_key: str | None = None

    @field_validator("headers")
    @classmethod
    def validate_headers(cls, headers: dict[str, str]) -> dict[str, str]:
        for name, value in headers.items():
            if not re.fullmatch(r"[!#$%&'*+.^_\x60|~0-9A-Za-z-]+", name):
                raise ValueError("Invalid HTTP header name")
            if not re.fullmatch(r"[\t -~]*", value) or value.strip(" \t") != value:
                raise ValueError("Invalid HTTP header value")
        return headers


DEFAULT_SANDBOX_STEPS = [
    {
        "step_id": 1,
        "name": "Step 1: Authenticate & Issue Token",
        "method": "POST",
        "path": "/api/sandbox/login",
        "headers": {"Content-Type": "application/json"},
        "body": '{"email": "loadtest@pusher.internal", "password": "secure_sandbox_key"}',
        "expected_status": 200,
        "extract_json_key": "token",
    },
    {
        "step_id": 2,
        "name": "Step 2: Fetch Catalog",
        "method": "GET",
        "path": "/api/sandbox/items",
        "headers": {"Authorization": "Bearer {{token}}"},
        "body": "",
        "expected_status": 200,
        "extract_json_key": None,
    },
    {
        "step_id": 3,
        "name": "Step 3: Submit High-Concurrency Checkout",
        "method": "POST",
        "path": "/api/sandbox/checkout",
        "headers": {"Authorization": "Bearer {{token}}", "Content-Type": "application/json"},
        "body": '{"item_id": "ITEM-9065", "quantity": 1}',
        "expected_status": 201,
        "extract_json_key": None,
    },
]


class JourneyInputError(ValueError):
    pass


def render_journey_value(text: str, context: dict[str, str], *, url_component: bool = False) -> str:
    def replace(match):
        key = match[1]
        if key not in context:
            raise JourneyInputError(f"Required journey variable '{key}' is unavailable.")
        value = context[key]
        return quote(value, safe="") if url_component else value

    return re.sub(r"\{\{([^{}]+)\}\}", replace, text)


def prepare_journey_request(step, context, headers):
    path = render_journey_value(step.get("path", ""), context, url_component=True)
    headers.update({name: render_journey_value(value, context) for name, value in (step.get("headers") or {}).items()})
    return path, encode_journey_body(step.get("body"), context, headers)


def append_cache_buster(url: str, vu_id: int, req_seq: int) -> str:
    nonce = f"{int(time.time() * 1000)}_{vu_id}_{req_seq}"
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}_cb={nonce}"


def journey_request_headers():
    return {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "User-Agent": "Pusher-LoadEngine/1.0",
    }


def build_journey_request(step, context, base, is_sandbox, cache_bust, vu_id, req_seq):
    headers = journey_request_headers()
    path, content = prepare_journey_request(step, context, headers)
    url = str(journey_target(path, base, is_sandbox))
    if cache_bust:
        url = append_cache_buster(url, vu_id, req_seq)
    return url, headers, content


def _has_template_vars(value) -> bool:
    if isinstance(value, str):
        return "{{" in value and "}}" in value
    if isinstance(value, list):
        return any(_has_template_vars(item) for item in value)
    if isinstance(value, dict):
        return any(_has_template_vars(k) or _has_template_vars(v) for k, v in value.items())
    return False


@dataclass(slots=True)
class CompiledJourneyStep:
    """Pre-validated, pre-encoded journey step eliminating static per-request allocations."""

    method: str
    raw_path: str
    base: httpx.URL
    is_sandbox: bool
    has_dynamic_path: bool
    static_url: str | None
    static_cb_prefix: str | None
    static_error: Exception | None
    static_headers: dict[str, str]
    dynamic_headers: tuple[tuple[str, str], ...]
    has_dynamic_body: bool
    static_body: bytes | None
    raw_body: object
    extract_key: str | None
    expected_status: int

    def build(
        self,
        context: dict[str, str],
        cache_bust: bool,
        vu_id: int,
        req_seq: int,
        run_epoch_ms: int,
    ) -> tuple[str, dict[str, str], bytes | None]:
        if self.static_error is not None:
            raise self.static_error

        if not self.has_dynamic_path and self.static_url is not None:
            url = (
                f"{self.static_cb_prefix}{run_epoch_ms}_{vu_id}_{req_seq}"
                if cache_bust and self.static_cb_prefix is not None
                else self.static_url
            )
        else:
            path = render_journey_value(self.raw_path, context, url_component=True)
            url = str(journey_target(path, self.base, self.is_sandbox))
            if cache_bust:
                sep = "&" if "?" in url else "?"
                url = f"{url}{sep}_cb={run_epoch_ms}_{vu_id}_{req_seq}"

        if not self.dynamic_headers and not self.has_dynamic_body:
            return url, self.static_headers, self.static_body

        headers = dict(self.static_headers)
        for name, template in self.dynamic_headers:
            headers[name] = render_journey_value(template, context)
        content = encode_journey_body(self.raw_body, context, headers) if self.has_dynamic_body else self.static_body
        return url, headers, content


def compile_journey_step(step: dict, base: httpx.URL, is_sandbox: bool) -> CompiledJourneyStep:
    """Compile a journey step once per run so static URLs, headers, and JSON bodies allocate zero per hit."""
    method = step.get("method", "GET").upper()
    raw_path = step.get("path", "")
    has_dynamic_path = "{{" in raw_path and "}}" in raw_path
    static_url: str | None = None
    static_cb_prefix: str | None = None
    static_error: Exception | None = None
    if not has_dynamic_path:
        try:
            static_url = str(journey_target(raw_path, base, is_sandbox))
            sep = "&" if "?" in static_url else "?"
            static_cb_prefix = f"{static_url}{sep}_cb="
        except DestinationError as exc:
            static_error = exc

    static_headers = journey_request_headers()
    dynamic_headers_list: list[tuple[str, str]] = []
    for name, value in (step.get("headers") or {}).items():
        if isinstance(value, str) and "{{" in value and "}}" in value:
            dynamic_headers_list.append((name, value))
        else:
            static_headers[name] = value

    raw_body = step.get("body")
    has_dynamic_body = _has_template_vars(raw_body)
    static_body: bytes | None = None
    if not has_dynamic_body:
        static_body = encode_journey_body(raw_body, {}, static_headers)

    return CompiledJourneyStep(
        method=method,
        raw_path=raw_path,
        base=base,
        is_sandbox=is_sandbox,
        has_dynamic_path=has_dynamic_path,
        static_url=static_url,
        static_cb_prefix=static_cb_prefix,
        static_error=static_error,
        static_headers=static_headers,
        dynamic_headers=tuple(dynamic_headers_list),
        has_dynamic_body=has_dynamic_body,
        static_body=static_body,
        raw_body=raw_body,
        extract_key=step.get("extract_json_key"),
        expected_status=int(step.get("expected_status", 200)),
    )


def extract_journey_value(key: str, preview: bytes) -> str:
    try:
        payload = json.loads(preview)
        value = payload[key]
    except (ValueError, KeyError, TypeError):
        value = None
    if (not isinstance(value, (str, bool, int, float)) or not str(value).strip()
            or (isinstance(value, float) and not math.isfinite(value))):
        raise JourneyInputError(f"Could not extract required field '{key}' from the response.")
    return str(value)


def _render_json(value, context):
    if isinstance(value, str):
        return render_journey_value(value, context)
    if isinstance(value, list):
        return [_render_json(item, context) for item in value]
    if isinstance(value, dict):
        return {render_journey_value(key, context): _render_json(item, context) for key, item in value.items()}
    return value


def encode_journey_body(body, context, headers) -> bytes | None:
    if body is None or body == "":
        return None
    if isinstance(body, str):
        text = body
        if "{{" in body:
            try:
                value = json.loads(body)
            except ValueError:
                text = render_journey_value(body, context)
            else:
                text = json.dumps(_render_json(value, context))
    else:
        text = json.dumps(_render_json(body, context))
    if not any(key.lower() == "content-type" for key in headers):
        try:
            json.loads(text)
        except ValueError:
            pass
        else:
            headers["Content-Type"] = "application/json"
    return text.encode("utf-8")


class JourneyStore:
    @property
    def steps(self) -> list[dict]:
        from backend.core.database import db_get_journey
        return db_get_journey(request_owner.get()).get("steps", [])

    @property
    def use_journey(self) -> bool:
        from backend.core.database import db_get_journey
        return db_get_journey(request_owner.get()).get("use_journey", False)

    @property
    def last_dry_run_results(self) -> list[dict]:
        from backend.core.database import db_get_journey
        return db_get_journey(request_owner.get()).get("last_dry_run") or []

    @last_dry_run_results.setter
    def last_dry_run_results(self, val: list[dict]):
        from backend.core.database import db_save_journey_dry_run
        db_save_journey_dry_run(val, request_owner.get())

    def get_journey(self) -> dict:
        from backend.core.database import db_get_journey
        data = db_get_journey(request_owner.get())
        return {
            "steps": data.get("steps", []),
            "use_journey": data.get("use_journey", False),
            "dry_run_results": data.get("last_dry_run") or [],
            "dry_run_timestamp": data.get("dry_run_timestamp"),
        }

    def save_journey(self, steps: list[dict], use_journey: bool = False) -> dict:
        from backend.core.database import db_save_journey
        return db_save_journey(use_journey=use_journey, steps=steps[:10], user_id=request_owner.get())



journey_store = JourneyStore()


def validate_journey_steps(
    steps: list[dict],
    active_target_url: str | None = None,
    is_sandbox: bool = False,
    require_runtime: bool = False,
) -> tuple[bool, str | None]:
    """
    Enforces Same-Origin SSRF protection for each step in the chain.
    - Relative paths (starting with '/') are safe and inherit the verified target's origin.
    - Full URLs must match the verified target's origin exactly.
    - External cross-origin or private network URLs are strictly rejected.
    """
    if not steps:
        return False, "Journey must contain at least 1 step."

    if len(steps) > 10:
        return False, "Journey exceeds maximum limit of 10 steps."

    try:
        parse = sandbox_target if is_sandbox else parse_target
        base = parse(active_target_url) if active_target_url else None
    except DestinationError as exc:
        return False, str(exc)
    seen_ids = set()
    for idx, step in enumerate(steps, 1):
        try:
            validated = JourneyStepModel.model_validate(step, strict=True)
        except ValidationError as exc:
            field = exc.errors()[0]["loc"]
            return False, f"Step {idx}: invalid {field[0] if field else 'step'}."
        if require_runtime:
            supplied = {name.lower() for name in validated.headers}
            if any(name.lower() not in supplied for name in validated.required_headers):
                return False, f"Step {idx}: re-enter the required headers before running."
            if validated.requires_body and validated.body in (None, ""):
                return False, f"Step {idx}: re-enter the required body before running."
            if validated.requires_query and not validated.path.partition("?")[2]:
                return False, f"Step {idx}: re-enter the required query string before running."
        if validated.step_id:
            step_id = str(validated.step_id)
            if step_id in seen_ids:
                return False, f"Step {idx}: duplicate step_id."
            seen_ids.add(step_id)
        path = validated.path
        if base is None:
            if not path.startswith("/") or path.startswith("//") or chr(92) in path:
                return False, f"Step {idx} must use a root-relative path until a target is configured."
            continue
        try:
            journey_target(path, base, is_sandbox)
        except DestinationError as exc:
            return False, f"Step {idx}: {exc}"

    return True, None


DRY_RUN_TIMEOUT_SEC = 10.0


async def execute_dry_run(
    steps: list[dict],
    base_url: str = "http://127.0.0.1:8000",
    client: httpx.AsyncClient | None = None,
    is_sandbox: bool = False,
    control: DryRunControl | None = None,
    cache_bust: bool = False,
) -> tuple[list[dict], dict[str, str]]:
    """
    1-VU Dry-Run Validator:
    Executes each step in sequence, extracting variables (like {{token}}) from the first
    4 KB chunk into a local context, asserting expected status codes, and measuring latency.
    """
    results = []
    context: dict[str, str] = {}
    control = control or DryRunControl(request_owner.get())
    loop = asyncio.get_running_loop()
    guard_remaining = control.guard_expires_at - time.time()
    deadline = loop.time() + min(DRY_RUN_TIMEOUT_SEC, guard_remaining)
    deadline_reason = "guard_expired" if guard_remaining <= DRY_RUN_TIMEOUT_SEC else "timeout"

    def interrupted() -> bool:
        if control.reason is None:
            if time.time() >= control.guard_expires_at:
                control.reason = "guard_expired"
            elif loop.time() >= deadline:
                control.reason = deadline_reason
        return control.reason is not None

    base = parse_target(base_url)
    own_client = False
    if client is None:
        client = target_client(base, is_sandbox, timeout=DRY_RUN_TIMEOUT_SEC)
        own_client = True

    try:
        async with asyncio.timeout_at(deadline) as timer:
            control.timer = timer
            for req_seq, s in enumerate(steps, 1):
                if interrupted():
                    break
                step_id = s.get("step_id", len(results) + 1)
                name = s.get("name", f"Step {step_id}")
                method = s.get("method", "GET").upper()
                raw_path = s.get("path", "")
                expected_status = s.get("expected_status", 200)
                extract_key = s.get("extract_json_key")

                t0 = time.perf_counter()
                passed = False
                status_code = 0
                error_msg = None
                extracted_val = None

                try:
                    url, headers, body_content = build_journey_request(
                        s, context, base, is_sandbox, cache_bust, 0, req_seq,
                    )
                    # 4 KB chunk discard streaming execution
                    async with client.stream(
                        method=method,
                        url=url,
                        headers=headers,
                        content=body_content,
                    ) as resp:
                        status_code = resp.status_code
                        first_chunk = b""
                        async for chunk in resp.aiter_bytes(chunk_size=4096):
                            if not first_chunk:
                                first_chunk = chunk
                            # Discard subsequent chunks immediately

                    if interrupted():
                        break
                    latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)

                    if status_code == expected_status:
                        passed = True
                    else:
                        error_msg = f"Expected status {expected_status}, received {status_code}"

                    if passed and extract_key:
                        extracted_val = extract_journey_value(extract_key, first_chunk)
                        context[extract_key] = extracted_val

                except (JourneyInputError, DestinationError) as e:
                    latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)
                    passed = False
                    error_msg = str(e)
                except (httpx.RequestError, ValueError):
                    latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)
                    passed = False
                    error_msg = "Journey request failed."

                results.append({
                    "step_id": step_id,
                    "name": name,
                    "method": method,
                    "path": raw_path.partition("?")[0],
                    "status_code": status_code,
                    "latency_ms": latency_ms,
                    "passed": passed,
                    "extracted_var": extract_key if extracted_val else None,
                    "error": error_msg,
                })

                # If a step fails in dry run, stop subsequent steps
                if not passed:
                    break

            interrupted()
    except TimeoutError:
        if not timer.expired():
            raise
        control.reason = control.reason or deadline_reason
    finally:
        control.timer = None
        if own_client:
            await client.aclose()

    journey_store.last_dry_run_results = results
    return results, context
