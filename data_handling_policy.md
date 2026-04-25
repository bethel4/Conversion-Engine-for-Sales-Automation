# Data Handling Policy

## Scope

This system stores public-research outputs, outbound activity metadata, reply events, booking events, and complaint-tracking records required to operate the kill-switch. The current market-map work is based on the local Crunchbase snapshot at [data/raw/crunchbase/crunchbase-companies-information.csv](/home/bethel/Documents/10academy/Conversion Engine for Sales Automation/data/raw/crunchbase/crunchbase-companies-information.csv).

## Data We Keep

- Public company fields used for scoring and enrichment: name, description, industries, employee band, funding metadata, and technology metadata.
- Outbound metadata: provider message ID, recipient, subject, delivery provider, send timestamp, and campaign tag.
- Inbound metadata: reply text, bounce reason, booking status, and SMS reply text where applicable.
- Complaint records: complaint type, named prospect, title, company, original brief path, message ID, reviewer, and final disposition (`wrong_signal`, `brand_risk`, `not_actionable`).

## Kill-Switch Monitoring Data

The pause triggers in [memo_page_2.md](/home/bethel/Documents/10academy/Conversion Engine for Sales Automation/memo_page_2.md) depend on three logged metrics:

1. `wrong_signal_rate_7d`
   Measurement: confirmed wrong-signal complaints in the last 7 days divided by research-led emails delivered to CTO / VP Engineering targets in the same window.
2. `research_reply_rate_14d`
   Measurement: replies divided by delivered research-led outbound, computed weekly from provider webhooks plus prospect activity.
3. `brand_complaint_named_prospect`
   Measurement: any named CTO or VP Engineering complaint that explicitly cites factual error or brand damage.

Every complaint entry must be linked to the original brief file and outbound message ID so the rollback review can reproduce the evidence path.

## Operational Policy

- `LIVE_OUTBOUND=false` is the production pause flag.
- When the flag is `false`, the backend blocks live outbound email, booking-link sends, and SMS.
- Manual processing of inbound replies can continue while outbound is paused so the team can close the loop with prospects already in flight.

## Rollback Review Packet

When the kill-switch fires, the review packet must include:

1. The last `50` generated briefs.
2. The last `14` days of complaint records.
3. The last `14` days of delivered outbound and reply-rate metrics.
4. A written disposition from CTO + Head of Sales stating whether the root cause was targeting, factual accuracy, or signal-extraction quality.

## Retention

- Keep complaint and outbound event logs for at least `180` days so trend-based triggers can be audited.
- Keep the review packet used for each pause event until the next successful re-enable decision.
