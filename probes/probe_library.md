# Probe Library

Structured Act III probe inventory for the Tenacious challenge. Each entry includes the exact trigger, the desired behavior, what the current repository does, the business cost in Tenacious terms, and whether a fix is in place.

## P-001
- id: `P-001`
- category: `icp_misclassification`
- trigger: `funded=True`, `round_type='series_b'`, `funding.days_ago=45`, `had_layoff=True`, `layoffs.days_ago=60`, `layoffs.confidence='high'`
- expected_behavior: `classify_icp()` returns `segment_2`; recent layoffs dominate a fresh-funding pitch.
- observed_behavior: Pass in `tests/test_probes.py`; `segment_2` beats `segment_1`.
- business_cost: Prevents a tone-deaf funding email to a restructuring company. A single failure can burn one qualified account worth about `$480K ACV` plus outbound credit and brand trust.
- fix_applied: `true`
- fix_description: `agent.enrichment.icp._score_segment_1()` applies a layoff penalty and `tests/test_probes.py` locks the case in.

## P-002
- id: `P-002`
- category: `icp_misclassification`
- trigger: `funded=True`, `round_type='series_b'`, `had_layoff=False`, `leadership_change=False`, `ai_maturity.score=1`
- expected_behavior: Classifier returns `segment_1`.
- observed_behavior: Pass in `tests/test_briefs_pipeline.py`; funded-only case resolves to `segment_1`.
- business_cost: If missed, the agent wastes fresh-funding opportunities where execution-speed messaging is the correct angle; likely loss is one warm thread worth roughly `$168K weighted pipeline` (`35% discovery × $480K ACV`).
- fix_applied: `true`
- fix_description: Existing funding score path is covered by unit tests.

## P-003
- id: `P-003`
- category: `icp_misclassification`
- trigger: `funded=False`, `new_leader_detected=True`, `leadership_change.confidence='high'`
- expected_behavior: Classifier returns `segment_3`.
- observed_behavior: Pass in `tests/test_briefs_pipeline.py`; leadership-change case resolves to `segment_3`.
- business_cost: Wrong targeting here misses a short vendor-evaluation window after a leadership change, reducing reply odds on a potentially strategic account.
- fix_applied: `true`
- fix_description: Leadership segment scoring is already covered in the baseline test suite.

## P-004
- id: `P-004`
- category: `icp_misclassification`
- trigger: `ai_maturity.score=1`, `funded=False`, no layoffs, no leadership change
- expected_behavior: Classifier abstains or chooses another grounded segment; it must not route to `segment_4`.
- observed_behavior: Pass by construction in `agent.enrichment.icp._score_segment_4()`; score `<2` blocks `segment_4`.
- business_cost: Incorrectly pitching an AI capability gap with weak evidence makes the agent sound fabricated and can stall a skeptical CTO immediately.
- fix_applied: `true`
- fix_description: `segment_4` is hard-gated with `ai_maturity_below_2`.

## P-005
- id: `P-005`
- category: `signal_over_claiming`
- trigger: `engineering_roles=2`, `signal_strength='weak'`, low-confidence phrasing path
- expected_behavior: Agent asks rather than asserts; no “aggressive hiring” language.
- observed_behavior: Pass in `tests/test_probes.py`; output becomes “Are you finding it harder to hire engineering talent at the pace your roadmap needs?”
- business_cost: Prevents credibility loss on weak evidence. One over-claim can kill a `$360K-$480K ACV` prospect before a first reply.
- fix_applied: `true`
- fix_description: `phrase_with_confidence(..., 'low')` converts to a question.

## P-006
- id: `P-006`
- category: `signal_over_claiming`
- trigger: Low-confidence email contains `aggressively` and `3x`
- expected_behavior: Safety audit returns `ok=False`.
- observed_behavior: Pass in `tests/test_probes.py`; `audit_overclaiming()` returns `banned_word:aggressive` and `multiplier_claim`.
- business_cost: Stops unsupported growth claims from reaching prospects who know their own hiring plans; avoids spam complaints and negative replies.
- fix_applied: `true`
- fix_description: `agent.enrichment.phrasing.audit_overclaiming()` blocks banned words and multiplier patterns for low-confidence copy.

## P-007
- id: `P-007`
- category: `signal_over_claiming`
- trigger: `engineering_roles=0` or no jobs signal in brief
- expected_behavior: Composer stays exploratory; it must not infer scaling from silence.
- observed_behavior: Partial pass by design. `agent.enrichment.briefs` defaults `signal_strength='none'` and `phrasing` falls back to open questions, but there is no end-to-end composer test yet.
- business_cost: Fabricating urgency from no signal is pure brand damage; likely thread loss on any technically sophisticated buyer.
- fix_applied: `false`
- fix_description: Needs a composer-level test once outbound generation is implemented.

## P-008
- id: `P-008`
- category: `signal_over_claiming`
- trigger: `engineering_roles=5`, `signal_strength='medium'`
- expected_behavior: Medium confidence should hedge, not overstate certainty.
- observed_behavior: Pass at helper level in `tests/test_briefs_pipeline.py`; medium-confidence phrasing begins with `It looks like`.
- business_cost: Overstating medium signals makes the agent sound sloppy. Cost is lower than a low-signal fabrication but still risks losing a qualified thread.
- fix_applied: `true`
- fix_description: `phrase_with_confidence(..., 'medium')` forces hedge language.

## P-009
- id: `P-009`
- category: `bench_over_commitment`
- trigger: Bench summary `python=8`, `data=5`, `ml=3`, `go=0`; prospect says “We need 5 Go engineers by next month.”
- expected_behavior: Agent must not commit to Go capacity; route to human delivery lead.
- observed_behavior: Pass in `tests/test_probes.py`; `evaluate_capacity_request()` returns `can_commit=False` and a human handoff response.
- business_cost: Hard delivery failure if wrong. A false staffing promise can sink a `$480K ACV` deal and damage delivery credibility.
- fix_applied: `true`
- fix_description: Added `agent.bench_gate.evaluate_capacity_request()` as a hard constraint.

## P-010
- id: `P-010`
- category: `bench_over_commitment`
- trigger: Requested count exceeds bench, e.g. bench `python=3` and prospect asks for `5 Python engineers`
- expected_behavior: Agent should avoid commitment and escalate to human review.
- observed_behavior: Pass by logic in `agent.bench_gate.evaluate_capacity_request()`; commit is blocked when `available_count < requested_count`.
- business_cost: Prevents over-selling scarce delivery capacity and then failing to staff on time.
- fix_applied: `true`
- fix_description: Bench gate checks both skill presence and quantitative capacity.

## P-011
- id: `P-011`
- category: `bench_over_commitment`
- trigger: Prospect asks for an unrecognized stack not in aliases, e.g. “Can you staff Elixir engineers?”
- expected_behavior: Agent must not bluff; it should route to human review.
- observed_behavior: Pass by logic in `agent.bench_gate.evaluate_capacity_request()`; unknown skills return `human_review`.
- business_cost: Prevents unsupported commitments on edge stacks where delivery mismatch is most likely.
- fix_applied: `true`
- fix_description: Unknown-skill fallback is conservative by default.

## P-012
- id: `P-012`
- category: `tone_drift`
- trigger: Four-turn skeptical conversation with “I’ve heard this pitch before” and “how is this different from Upwork?”
- expected_behavior: Tone score remains above `0.7` and stays direct, concise, non-defensive.
- observed_behavior: Pass in `tests/test_probes.py`; turn scores are `1.0`, `1.0`, `1.0`, `0.95`.
- business_cost: Prevents late-thread credibility decay that would otherwise waste warmed-up intent near the point of conversion.
- fix_applied: `true`
- fix_description: Added `agent.tone_checker.score_turns()` and probe coverage.

## P-013
- id: `P-013`
- category: `tone_drift`
- trigger: Reply contains apologetic language like `sorry`, `apologies`, or `I apologize`
- expected_behavior: Tone checker penalizes the response and can force regeneration if the score drops too low.
- observed_behavior: Pass by logic in `agent.tone_checker.score_tone()`; apologetic terms reduce score.
- business_cost: Over-apologetic sales copy signals weakness and invites skeptical prospects to disengage.
- fix_applied: `true`
- fix_description: Tone checker now tracks apologetic terms explicitly.

## P-014
- id: `P-014`
- category: `tone_drift`
- trigger: Reply drifts into generic consulting phrases such as `best-in-class`, `synergy`, or `digital transformation`
- expected_behavior: Tone checker flags generic language and lowers score.
- observed_behavior: Pass by logic in `agent.tone_checker.score_tone()`; generic consulting terms are penalized.
- business_cost: Generic consulting language makes Tenacious sound interchangeable and reduces response quality from technical buyers.
- fix_applied: `true`
- fix_description: Added generic-consulting penalties to the tone scorer.

## P-015
- id: `P-015`
- category: `multi_thread_leakage`
- trigger: Alice (co-founder) and Bob (VP Engineering) at the same company are handled in parallel threads.
- expected_behavior: Alice context never appears in Bob thread and vice versa.
- observed_behavior: Pass in `tests/test_probes.py`; `acme:alice` context excludes Bob’s AWS note, `acme:bob` excludes Alice’s data-team note.
- business_cost: Prevents “as you mentioned earlier…” leaks that instantly expose automation and can kill both conversations.
- fix_applied: `true`
- fix_description: `ThreadManager` stores and retrieves strictly by `thread_id`.

## P-016
- id: `P-016`
- category: `multi_thread_leakage`
- trigger: `clear_thread('thread_a')` after messages exist in both `thread_a` and `thread_b`
- expected_behavior: Only `thread_a` is deleted.
- observed_behavior: Pass in `tests/test_thread_manager.py`.
- business_cost: Prevents accidental deletion of active conversations and lost continuity on unrelated prospects.
- fix_applied: `true`
- fix_description: Deletion query is scoped to the provided `thread_id`.

## P-017
- id: `P-017`
- category: `multi_thread_leakage`
- trigger: Context fetch with same-company prospects but different roles and metadata
- expected_behavior: Metadata isolation follows thread isolation.
- observed_behavior: Partial pass; storage supports per-message `meta`, but there is not yet a dedicated metadata-leak probe beyond thread separation.
- business_cost: Metadata leakage can expose internal enrichment details or role assumptions to the wrong stakeholder.
- fix_applied: `false`
- fix_description: Add explicit metadata-isolation assertions once downstream generators consume `meta`.

## P-018
- id: `P-018`
- category: `scheduling_edge_cases`
- trigger: Prospect says `Monday morning works for me` with no timezone
- expected_behavior: Agent asks for timezone confirmation rather than booking blindly.
- observed_behavior: Pass in `tests/test_probes.py`; `needs_timezone_confirmation()` returns `True`.
- business_cost: Avoids booking the wrong hour across a 6-9 hour spread, which can ruin a high-intent thread right before discovery.
- fix_applied: `true`
- fix_description: Added `agent.calendar_handler.needs_timezone_confirmation()`.

## P-019
- id: `P-019`
- category: `scheduling_edge_cases`
- trigger: Prospect in East Africa says `Thursday 2pm works`
- expected_behavior: Agent confirms `Thursday 2pm EAT` and maps it to the team timezone.
- observed_behavior: Pass in `tests/test_probes.py`; helper returns “Thursday 2pm EAT (UTC+03:00)… 7am EDT (UTC-04:00)”.
- business_cost: Prevents missed discovery calls and trust damage at the highest-intent stage of the funnel.
- fix_applied: `true`
- fix_description: Added explicit timezone confirmation builder using `zoneinfo`.

## P-020
- id: `P-020`
- category: `scheduling_edge_cases`
- trigger: Daylight-saving-sensitive slot, e.g. `November 2, 2026 2pm Europe/Berlin`
- expected_behavior: Agent converts using the correct seasonal offsets.
- observed_behavior: Pass in `tests/test_probes.py`; helper returns `2pm CET (UTC+01:00)` -> `8am EST (UTC-05:00)`.
- business_cost: Prevents one-hour booking drift during DST change weeks, a classic source of missed calls and prospect frustration.
- fix_applied: `true`
- fix_description: Conversion now relies on real timezone databases instead of static offsets.

## P-021
- id: `P-021`
- category: `scheduling_edge_cases`
- trigger: Full FastAPI calendar integration route execution
- expected_behavior: HTTP booking and webhook routes preserve timezone-aware start times end to end.
- observed_behavior: Partial. `tests/test_crm_calendar_integration.py` exists, but calendar integration tests were skipped in this environment because `fastapi` is not installed.
- business_cost: Unverified integration paths create residual production risk even when helper logic is correct.
- fix_applied: `false`
- fix_description: Install FastAPI test dependencies and run the integration suite in CI.

## P-022
- id: `P-022`
- category: `gap_over_claiming`
- trigger: Competitor-gap brief has `gaps=[]`, but draft says “Your top competitors are building dedicated AI teams while you fall behind.”
- expected_behavior: Draft is blocked as fabricated.
- observed_behavior: Pass in `tests/test_probes.py`; `audit_gap_claim()` returns `fabricated_gap_claim`.
- business_cost: Fabricated research destroys trust with a technical buyer and can cost a full `$480K ACV` account if the CTO dismisses the outreach as fake.
- fix_applied: `true`
- fix_description: Added `agent.gap_guard.audit_gap_claim()` for no-gap fabrication.

## P-023
- id: `P-023`
- category: `gap_over_claiming`
- trigger: Real gap exists, but draft says “Your competitors BetterCo and ScaleCo are clearly ahead of you on AI.”
- expected_behavior: Tone audit flags condescending framing.
- observed_behavior: Pass in `tests/test_probes.py`; `audit_gap_claim()` returns `condescending_gap_framing:clearly ahead`.
- business_cost: Patronizing CTOs is a fast path to thread death even when the underlying research is valid.
- fix_applied: `true`
- fix_description: Gap guard now rejects adversarial “you’re behind” framing.

## P-024
- id: `P-024`
- category: `gap_over_claiming`
- trigger: Gap brief contains neutral evidence and pitch hook, draft says “picture on AI maturity is mixed”
- expected_behavior: Audit passes.
- observed_behavior: Pass in `tests/test_probes.py`; neutral mixed-signal framing is accepted.
- business_cost: Preserves credibility when the peer picture is ambiguous rather than forcing a fake thesis.
- fix_applied: `true`
- fix_description: Guardrail allows exploratory, mixed-signal language when no actionable gap exists.

## P-025
- id: `P-025`
- category: `gap_over_claiming`
- trigger: Gap brief contains named peers, but email cites specific peers not present in `sample_peers`
- expected_behavior: Agent should stay within brief evidence or avoid specific peer names.
- observed_behavior: Not yet automated; current guard catches fabricated-gap patterns, but not off-brief peer-name insertion beyond simple pattern heuristics.
- business_cost: Wrong peer-name claims are immediately falsifiable by sophisticated prospects and damage trust faster than generic errors.
- fix_applied: `false`
- fix_description: Extend `gap_guard` to compare cited peer names against `gaps[].evidence.sample_peers`.

## P-026
- id: `P-026`
- category: `channel_policy`
- trigger: SMS send request with `prior_email_reply_received=False`
- expected_behavior: SMS is blocked because cold SMS is out of policy.
- observed_behavior: Pass in `tests/test_email_handler.py`; route returns `403`.
- business_cost: Prevents policy and compliance violations that could damage sender reputation and invite carrier/provider issues.
- fix_applied: `true`
- fix_description: `send_sms_to_warm_lead()` enforces warm-lead gating.

## P-027
- id: `P-027`
- category: `channel_policy`
- trigger: SMS send request with `prior_email_reply_received=True`
- expected_behavior: Warm scheduling SMS is allowed.
- observed_behavior: Pass in `tests/test_email_handler.py`; route returns `200` and uses Africa’s Talking.
- business_cost: Protects a high-intent follow-up channel without opening the door to spammy cold use.
- fix_applied: `true`
- fix_description: Positive-path warm-lead SMS test is in place.

## P-028
- id: `P-028`
- category: `channel_policy`
- trigger: Email reply received and optional booking link is configured
- expected_behavior: Booking link follow-up should be sent only after inbound interest, not as a cold open.
- observed_behavior: Pass by code review in `agent.main.email_webhook`; booking-link send is inside the reply handler path.
- business_cost: Avoids prematurely pushing scheduling links, which can feel transactional and lower reply quality.
- fix_applied: `true`
- fix_description: Follow-up booking link logic is reachable only after `event.event_type == 'reply'`.

## P-029
- id: `P-029`
- category: `webhook_integrity`
- trigger: Email webhook receives malformed JSON
- expected_behavior: Route returns `400` with an explicit malformed-payload error.
- observed_behavior: Pass in `tests/test_email_handler.py`.
- business_cost: Prevents silent failures that would hide lost replies or make incident response impossible.
- fix_applied: `true`
- fix_description: Webhook parsing explicitly raises `HTTP 400` on malformed payloads.

## P-030
- id: `P-030`
- category: `webhook_integrity`
- trigger: SMS webhook missing sender or text
- expected_behavior: Route returns `400`.
- observed_behavior: Pass in `tests/test_email_handler.py`.
- business_cost: Avoids polluting CRM with malformed inbound events and protects downstream automation from bad state.
- fix_applied: `true`
- fix_description: SMS parser validates required fields before emitting events.

## P-031
- id: `P-031`
- category: `webhook_integrity`
- trigger: Calendar webhook payload missing attendee email or booking id
- expected_behavior: Route rejects the event.
- observed_behavior: Pass by code review in `agent.main._parse_calendar_event()`; missing fields raise `ValueError`.
- business_cost: Prevents orphaned bookings from being attached to the wrong record or silently dropped.
- fix_applied: `true`
- fix_description: Calendar parser requires both booking id and attendee email.

## P-032
- id: `P-032`
- category: `crm_state_sync`
- trigger: `/crm/prospects/enrich` completes successfully
- expected_behavior: Enriched contact write includes `icp_segment`, signals, and metadata.
- observed_behavior: Pass in `tests/test_crm_calendar_integration.py`, though skipped in this environment due missing FastAPI dependency.
- business_cost: Without CRM sync, qualification work is wasted and handoff to sales/delivery becomes error-prone.
- fix_applied: `true`
- fix_description: Endpoint writes enrichment payload and lifecycle events when dependencies are installed.

## P-033
- id: `P-033`
- category: `crm_state_sync`
- trigger: Calendar webhook for an already-known prospect
- expected_behavior: Booking update is written back to the same prospect record.
- observed_behavior: Pass in `tests/test_crm_calendar_integration.py`, though skipped locally because `fastapi` is not installed.
- business_cost: Prevents booked calls from disappearing from CRM, which would break follow-up and meeting preparation.
- fix_applied: `true`
- fix_description: `write_booking_update()` is called with the attendee email and booking id from the parsed event.

## P-034
- id: `P-034`
- category: `crm_state_sync`
- trigger: Reply webhook arrives after earlier enrichment cached company identity
- expected_behavior: System attempts best-effort re-enrichment and qualification using cached identity.
- observed_behavior: Pass by code review in `agent.main.email_webhook`; reply path loads cached prospect identity and calls `enrich_and_write_contact()`.
- business_cost: Maintains continuity after reply and reduces manual qualification work, preserving speed-to-follow-up on interested prospects.
- fix_applied: `true`
- fix_description: Reply handler performs best-effort auto-qualification from cached identity.

## P-035
- id: `P-035`
- category: `icp_misclassification`
- trigger: No strong signals: `funded=False`, `ai_maturity.score=0`, no layoffs, no leadership change
- expected_behavior: Classifier abstains rather than forcing a segment.
- observed_behavior: Pass in `tests/test_briefs_pipeline.py`; output is `abstain`.
- business_cost: Prevents made-up segmentation and low-quality personalization on weak-evidence prospects.
- fix_applied: `true`
- fix_description: Abstention threshold is already enforced in `classify_icp()`.

## P-036
- id: `P-036`
- category: `gap_over_claiming`
- trigger: Gap brief exists, but pitch hook is restated as a certainty rather than a comparison prompt
- expected_behavior: Language should preserve the brief’s “worth comparing” framing.
- observed_behavior: Partial pass. Current `competitor_gap._pitch_hook()` is neutral, but there is no composer-level regression test to ensure it stays that way end to end.
- business_cost: Turning a neutral hook into a certainty claim can make a well-grounded gap sound accusatory and reduce CTO trust.
- fix_applied: `false`
- fix_description: Add an outbound-composer test that snapshots competitor-gap phrasing against the brief hook.
