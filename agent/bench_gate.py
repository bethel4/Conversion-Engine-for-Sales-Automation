from __future__ import annotations

import re
from typing import Any

from agent.seed_assets import load_bench_counts


SKILL_ALIASES = {
    "python": ("python", "backend"),
    "data": ("data", "analytics", "data engineering"),
    "ml": ("ml", "machine learning", "ai"),
    "go": ("go", "golang"),
    "infra": ("infra", "infrastructure", "devops", "platform"),
    "frontend": ("frontend", "front end", "react", "next.js", "typescript"),
    "fullstack_nestjs": ("nestjs", "nest.js", "node", "fullstack"),
}


def evaluate_capacity_request(message: str, bench_summary: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Hard gate for bench claims. If the requested stack is absent or under capacity,
    the agent must not commit and should route to a human.
    """

    normalized = (message or "").casefold()
    bench_counts = _normalize_bench_summary(bench_summary)
    requested_count = _extract_requested_count(normalized)
    requested_skill = _extract_requested_skill(normalized)
    available_count = int(bench_counts.get(requested_skill or "", 0)) if requested_skill else 0

    if not requested_skill:
        return {
            "can_commit": False,
            "requested_count": requested_count,
            "requested_skill": None,
            "available_count": 0,
            "action": "human_review",
            "response": (
                "I want to give you an accurate picture of our current capacity, "
                "so I'll connect you with our delivery lead."
            ),
        }

    if available_count <= 0 or (requested_count is not None and available_count < requested_count):
        return {
            "can_commit": False,
            "requested_count": requested_count,
            "requested_skill": requested_skill,
            "available_count": available_count,
            "action": "human_review",
            "response": (
                f"Let me connect you with our delivery lead who can give you an accurate "
                f"picture of our current {requested_skill.title()} capacity."
            ),
        }

    return {
        "can_commit": True,
        "requested_count": requested_count,
        "requested_skill": requested_skill,
        "available_count": available_count,
        "action": "share_capacity",
        "response": (
            f"We currently show {available_count} {requested_skill.title()} engineers available to deploy. "
            "I can connect you with delivery to confirm timing and fit."
        ),
    }


def _extract_requested_count(message: str) -> int | None:
    match = re.search(r"\b(\d+)\b", message)
    if not match:
        return None
    return int(match.group(1))


def _extract_requested_skill(message: str) -> str | None:
    for canonical, aliases in SKILL_ALIASES.items():
        if any(re.search(rf"\b{re.escape(alias)}\b", message) for alias in aliases):
            return canonical
    return None


def _normalize_bench_summary(bench_summary: dict[str, Any] | None) -> dict[str, int]:
    if bench_summary is None:
        return load_bench_counts()
    if "stacks" in bench_summary:
        counts: dict[str, int] = {}
        stacks = bench_summary.get("stacks", {})
        if isinstance(stacks, dict):
            for stack, payload in stacks.items():
                if isinstance(stack, str) and isinstance(payload, dict):
                    counts[stack] = int(payload.get("available_engineers", 0) or 0)
        return counts
    return {str(k): int(v or 0) for k, v in bench_summary.items()}
