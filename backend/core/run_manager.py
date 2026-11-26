"""
Concurrent Run Registry for Pusher (SCALE-04).
Manages multiple concurrent operator LoadEngine executions keyed by run_id and owner_id,
enforces shared host FD worker capacity, and preserves legacy load_engine monkeypatch behavior.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.core.load_engine import LoadEngine


class RunManager:
    """Coordinates multiple concurrent isolated LoadEngine runs across operators."""

    def __init__(self, default_engine: LoadEngine) -> None:
        self.default_engine = default_engine
        self._runs: dict[str, LoadEngine] = {}
        self._owner_latest: dict[str, LoadEngine] = {}

    @staticmethod
    def _is_active(engine: LoadEngine | None) -> bool:
        if engine is None:
            return False
        master = getattr(engine, "_master_task", None)
        return bool(engine.is_running or (master is not None and not master.done()))

    def _prune(self) -> None:
        stale_runs = [
            rid for rid, eng in self._runs.items()
            if not self._is_active(eng) and eng is not self._owner_latest.get(eng.owner_id or "")
        ]
        for rid in stale_runs:
            self._runs.pop(rid, None)

    def reset(self) -> None:
        self._runs.clear()
        self._owner_latest.clear()

    def register_run(self, engine: LoadEngine, owner_id: str) -> None:
        self._prune()
        if engine.run_id:
            self._runs[engine.run_id] = engine
        self._owner_latest[owner_id] = engine

    def active_engines(self, primary_engine: LoadEngine | None = None) -> list[LoadEngine]:
        seen: dict[int, LoadEngine] = {}
        for eng in (primary_engine, self.default_engine, *self._runs.values(), *self._owner_latest.values()):
            if eng is not None and self._is_active(eng):
                seen[id(eng)] = eng
        return list(seen.values())

    def total_reserved_vus(
        self,
        *,
        exclude_owner: str | None = None,
        primary_engine: LoadEngine | None = None,
    ) -> int:
        total = 0
        for eng in self.active_engines(primary_engine):
            if exclude_owner is not None and eng.owner_id == exclude_owner:
                continue
            total += max(0, int(getattr(eng, "_worker_limit", 0) or eng.target_vus or 0))
        return total

    def active_engine_for_owner(
        self,
        owner_id: str,
        primary_engine: LoadEngine | None = None,
    ) -> LoadEngine | None:
        candidates = []
        if primary_engine is not None:
            candidates.append(primary_engine)
        if owner_id in self._owner_latest:
            candidates.append(self._owner_latest[owner_id])
        for eng in self._runs.values():
            candidates.append(eng)
        for eng in candidates:
            if eng is not None and eng.owner_id == owner_id and self._is_active(eng):
                return eng
        return None

    def engine_for_owner(
        self,
        owner_id: str,
        *,
        primary_engine: LoadEngine | None = None,
        run_id: str | None = None,
    ) -> LoadEngine:
        fallback = primary_engine if primary_engine is not None else self.default_engine
        if fallback is not self.default_engine:
            return fallback
        if run_id:
            by_id = self._runs.get(run_id)
            if by_id is not None:
                return by_id
            if fallback.run_id == run_id:
                return fallback
        active = self.active_engine_for_owner(owner_id, primary_engine=fallback)
        if active is not None:
            return active
        if fallback.owner_id == owner_id and fallback.run_id is not None:
            latest = self._owner_latest.get(owner_id)
            if latest is None or (fallback.start_time or 0.0) >= (latest.start_time or 0.0):
                return fallback
        latest = self._owner_latest.get(owner_id)
        if latest is not None:
            return latest
        return fallback

    def find_by_run_id(
        self,
        run_id: str,
        primary_engine: LoadEngine | None = None,
    ) -> LoadEngine | None:
        fallback = primary_engine if primary_engine is not None else self.default_engine
        if fallback.run_id == run_id:
            return fallback
        eng = self._runs.get(run_id)
        if eng is not None and eng.run_id == run_id:
            return eng
        return None

    def acquire_engine_for_start(
        self,
        owner_id: str,
        primary_engine: LoadEngine | None = None,
    ) -> LoadEngine:
        from backend.core.load_engine import LoadEngine

        fallback = primary_engine if primary_engine is not None else self.default_engine
        if not self._is_active(fallback):
            return fallback
        engine = LoadEngine()
        engine.connection_manager = fallback.connection_manager
        return engine

    async def stop_guard_runs(
        self,
        owner_id: str,
        guard_id: str | None,
        *,
        primary_engine: LoadEngine | None = None,
        reason: str = "GUARD_REVOKED",
    ) -> None:
        if not guard_id:
            return
        targets = [
            eng for eng in self.active_engines(primary_engine)
            if eng.owner_id == owner_id and eng.active_guard_id == guard_id
        ]
        if targets:
            await asyncio.gather(*(eng.stop(reason=reason) for eng in targets), return_exceptions=True)

    def request_stop_owner(self, owner_id: str, status: str, primary_engine: LoadEngine | None = None) -> None:
        for eng in self.active_engines(primary_engine):
            if eng.owner_id == owner_id:
                eng.request_stop(status)

    async def stop_all(self, reason: str = "ENGINE_SHUTDOWN") -> None:
        targets = self.active_engines(self.default_engine)
        if targets:
            await asyncio.gather(*(eng.stop(reason=reason) for eng in targets), return_exceptions=True)


from backend.core.load_engine import load_engine  # noqa: E402

run_manager = RunManager(load_engine)
