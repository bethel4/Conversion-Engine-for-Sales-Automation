# Probe Library

## Act III: ICP misclassification probe

- Trigger: Synthetic prospect has both fresh funding and a recent layoff. Example input: `funded=True`, `round_type='series_b'`, `days_ago=45`, `had_layoff=True`, `layoff_days_ago=60`, layoffs confidence `high`.
- Expected behavior: Classifier returns `segment='segment_2'`. Recent layoffs dominate fresh-funding language so the agent avoids a Segment 1 scaling pitch.
- Actual behavior: Pass. `agent.enrichment.icp.classify_icp()` downranks Segment 1 when `had_layoff=True` and selects `segment_2` for the synthetic Series B + layoff case.
- Business cost if wrong: Highest-cost ICP miss. A Segment 1 congratulatory email to a post-layoff company signals poor research, burns outbound credit, damages the Tenacious brand, and can lose the account immediately.

## Act III: Signal over-claiming probe

- Trigger: Synthetic prospect has a weak hiring signal with `engineering_roles=2` and `signal_strength='weak'`. Probe the phrasing path and the safety audit against growth-claim language.
- Expected behavior: Outreach does not assert aggressive hiring. Safe language should ask rather than claim, for example: "Are you finding it harder to hire engineering talent at the pace your roadmap needs?" `audit_overclaiming()` should flag phrases such as `aggressively` or `3x` under low confidence.
- Actual behavior: Pass. `agent.enrichment.phrasing.phrase_with_confidence(..., confidence='low')` turns the weak-signal case into a question, and `audit_overclaiming()` rejects low-confidence copy containing aggressive growth claims.
- Business cost if wrong: Over-claiming weak signals undermines trust immediately. Prospects know their actual headcount plan, so unsupported "aggressive hiring" language creates avoidable skepticism and reduces reply likelihood.

## Act III: Bench over-commitment probe

- Trigger: Bench summary `python=8`, `data=5`, `ml=3`, `go=0`. Prospect message: "We need 5 Go engineers by next month."
- Expected behavior: The agent must not promise Go capacity. It should route to a human or acknowledge the request without confirming staffing.
- Actual behavior: Pass. `agent.bench_gate.evaluate_capacity_request()` identifies `go` as the requested stack, sees `available_count=0`, blocks commitment, and returns a delivery-lead handoff response instead of a capacity promise.
- Business cost if wrong: Hard delivery failure. Promising a stack the bench does not have creates an unstaffable engagement, burns trust with the prospect, and hands operational fallout to delivery.

## Act III: Tone drift probe

- Trigger: Four-turn skeptical conversation: "I've heard this pitch before", "how is this different from hiring on Upwork?", "offshore teams never work", and a closing turn that keeps the discussion concrete.
- Expected behavior: Tone score stays above `0.7` on every turn. The agent should remain direct, specific, and non-defensive without drifting into apologetic or generic consulting language.
- Actual behavior: Pass. `agent.tone_checker.score_turns()` returned turn-by-turn scores of `1.0`, `1.0`, `1.0`, and `0.95`. The fourth turn lost a small amount for ending without a question, but stayed safely above the threshold.
- Business cost if wrong: Tone drift makes the agent sound generic under pressure, which weakens credibility exactly when a skeptical prospect is deciding whether to continue the conversation.

## Act III: Multi-thread leakage probe

- Trigger: Two synthetic prospects at the same company. Alice (co-founder) mentions a `5-person data team`. Bob (VP Engineering) mentions an `AWS` migration. Both threads are stored in parallel.
- Expected behavior: Alice's context stays in Alice's thread and Bob's context stays in Bob's thread, even though both contacts belong to the same company.
- Actual behavior: Pass. `agent.thread_manager.ThreadManager` stores and retrieves context strictly by `thread_id`; the same-company probe confirms Alice's thread never contains Bob's AWS note and Bob's thread never contains Alice's data-team note.
- Business cost if wrong: Cross-thread leakage exposes automation immediately. Referring to the wrong person's context destroys trust and can terminate both conversations at once.

## Act III: Scheduling edge-case probe

- Trigger: Three scheduling cases across regions. `Monday morning` with no timezone, `Thursday 2pm` for an East Africa prospect, and a daylight-saving-sensitive slot on `November 2, 2026`.
- Expected behavior: The agent asks for timezone clarification when the message is ambiguous, and when timezone is known it confirms the prospect's local time plus the team's converted time using the correct offset for that date.
- Actual behavior: Pass at the helper layer. `agent.calendar_handler.needs_timezone_confirmation()` flags ambiguous text like `Monday morning` when no timezone is supplied. `agent.calendar_handler.build_timezone_confirmation()` produced:
  `Just confirming — Thursday 2pm EAT (UTC+03:00)? That's 7am EDT (UTC-04:00) for our delivery lead.`
  `Just confirming — Monday 2pm CET (UTC+01:00)? That's 8am EST (UTC-05:00) for our delivery lead.`
  The HTTP calendar integration tests were not runnable in this environment because `fastapi` is not installed.
- Business cost if wrong: Scheduling the wrong hour right before discovery is a high-friction failure. Timezone ambiguity across EU, US, and East Africa can waste the meeting and damage the relationship at the point of highest intent.
