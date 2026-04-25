from __future__ import annotations

import os
from typing import Any


def is_live_outbound_enabled() -> bool:
    value = os.getenv("LIVE_OUTBOUND", "true").strip().casefold()
    return value in {"1", "true", "yes", "on"}


def live_outbound_config() -> dict[str, Any]:
    return {
        "live_outbound": is_live_outbound_enabled(),
        "flag": "LIVE_OUTBOUND",
        "rollback_batch_size": 50,
    }


def require_live_outbound(action: str) -> None:
    if is_live_outbound_enabled():
        return
    raise PermissionError(
        "Live outbound is paused because LIVE_OUTBOUND=false. "
        f"Blocked action: {action}. "
        "Rollback procedure: pause the campaign, review the last 50 briefs plus complaint logs, "
        "then re-enable only after manual sign-off."
    )
