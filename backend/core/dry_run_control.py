import asyncio
import math
from dataclasses import dataclass, field


@dataclass(eq=False)
class DryRunControl:
    owner_id: str
    guard_id: str | None = None
    guard_expires_at: float = math.inf
    dry_run_id: str | None = None
    reason: str | None = None
    timer: asyncio.Timeout | None = None
    done: asyncio.Event = field(default_factory=asyncio.Event)

    def cancel(self, reason: str) -> None:
        if self.reason is None:
            self.reason = reason
            if self.timer is not None and not self.timer.expired():
                self.timer.reschedule(asyncio.get_running_loop().time())


active_dry_runs: set[DryRunControl] = set()


def cancel_guard_dry_runs(guard_id: str, *, expired: bool = False) -> None:
    for run in active_dry_runs:
        if run.guard_id == guard_id:
            run.cancel("guard_expired" if expired else "guard_revoked")
