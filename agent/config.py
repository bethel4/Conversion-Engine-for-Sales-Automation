from __future__ import annotations

import os

from agent.outbound_policy import is_live_outbound_enabled


STAFF_SINK_EMAIL = (os.getenv("STAFF_SINK_EMAIL") or "staff-sink@example.com").strip()


def is_live_outbound() -> bool:
    return is_live_outbound_enabled()
