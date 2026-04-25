# Act V Memo - Page 2

## Kill-Switch Clause

The Tenacious CEO should pause the system when **any** of the following measurable triggers fires:

| Trigger | Threshold | Measurement method | Pull-switch owner | Rollback steps |
| --- | --- | --- | --- | --- |
| Wrong-signal rate | `wrong_signal_rate_7d > 4%` **and** at least `3` confirmed wrong-signal complaints in the same rolling 7-day window | Numerator = complaint-log entries tagged `wrong_signal` after RevOps + CTO manual review. Denominator = research-led emails delivered to CTO / VP Engineering targets in the same 7 days from provider send logs. | CTO can pause immediately; CEO and Head of Sales are notified the same day. | Set `LIVE_OUTBOUND=false`, pause campaign in the provider, export the last `50` briefs and last `14` days of complaint logs, patch signal logic, then rerun validation before re-enable. |
| Reply-rate degradation | `research_reply_rate_14d < 3%` for `2` consecutive full weeks | Weekly reply rate = replies / delivered research-led outbound, measured from Resend or MailerSend webhook logs plus prospect activity records. | Head of Sales recommends the pause; CEO approves if the metric is breached twice. | Set `LIVE_OUTBOUND=false`, stop new sends, review the last `50` briefs plus the two bad-week cohorts, tighten targeting or signal extraction, then rerun the pipeline and spot-check before re-enable. |
| Named brand complaint | `brand_complaint_named_prospect >= 1` where the named prospect is a CTO or VP Engineering and explicitly cites a factual error or brand-damaging claim | Logged manually in the complaint tracker within 24 hours, linked to the original brief and outbound message ID. No batching; one confirmed complaint is enough. | CTO or CEO can pause unilaterally. | Set `LIVE_OUTBOUND=false`, suppress the campaign immediately, review the offending brief plus the last `50` similar briefs, issue any needed apology/reply, patch the extractor/rules, then require CTO sign-off to resume. |

**Configuration flag:** `LIVE_OUTBOUND=false` is the operational kill-switch. In this repo it blocks `/emails/send`, `/prospects/{id}/send-outreach`, booking-link sends, and `/sms/send`.

## Market Oxygen Summary

The local Crunchbase sample in [data/raw/crunchbase/crunchbase-companies-information.csv](/home/bethel/Documents/10academy/Conversion Engine for Sales Automation/data/raw/crunchbase/crunchbase-companies-information.csv) contains **1000** companies, not 1001, and the report is anchored to the dataset snapshot date **2024-07-22**. Using the lightweight `quick_ai_score()` heuristic, the readiness mix is:

- `score=0` dormant: `825` companies (`82.5%`)
- `score=1` emerging: `138` companies (`13.8%`)
- `score=2` active: `15` companies (`1.5%`)
- `score=3` leading: `22` companies (`2.2%`)

On absolute AI-ready volume (`score >= 2`), the most relevant sectors are DevTools (`13/213`), Fintech (`5/163`), and then Education / MarTech / Healthcare (each `3` companies). On AI-ready share, Education leads the local sample at `10.3%`, but on much smaller volume than DevTools.

## Top Cells

1. **DevTools, small (11-50), emerging**. `14` companies, combined score `0.447`, average bench match `59%`. These are smaller software and platform teams already showing early AI/data vocabulary. Lead with backend, data, and AI-platform staffing rather than generic staff augmentation.
2. **MarTech, micro (1-10), emerging**. `16` companies, combined score `0.437`, average bench match `49%`. These are lean revenue-tech teams with automation language but limited operating depth. Lead with campaign data quality, AI-assisted ops, and fast execution capacity.
3. **DevTools, micro (1-10), emerging**. `11` companies, combined score `0.394`, average bench match `57%`. These are founder-led product shops where Tenacious can sell velocity and platform delivery instead of enterprise process.
4. **DevTools, growth (101-250), emerging**. `3` companies, combined score `0.334`, average bench match `72%`. Smaller population, but the bench fit is strongest here. Lead with platform modernization and AI-adjacent engineering leverage.
5. **Healthcare, small (11-50), emerging**. `6` companies, combined score `0.318`, average bench match `57%`. The buy case is workflow automation and data quality, so the opening signal should be regulated data workflows and delivery capacity.
