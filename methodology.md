# Market Map Methodology

## Dataset and Heuristic

The local Crunchbase file at [data/raw/crunchbase/crunchbase-companies-information.csv](/home/bethel/Documents/10academy/Conversion Engine for Sales Automation/data/raw/crunchbase/crunchbase-companies-information.csv) contains **1000** rows in this repo, not 1001. The market-map report is therefore computed on the repo-local 1000-company sample, using the dataset snapshot date **2024-07-22** as the reference point for “last 12 months” funding logic.

Scoring is intentionally cheap and deterministic:

- `quick_ai_score()` uses only company description, industry tags, and lightweight keyword matching.
- No LLM call is used for the 1000-company sweep.
- Cell ranking uses the requested formula: population weight `0.3`, recent-funding weight `0.3`, bench-match weight `0.4`.

## Readiness Distribution

- `score=0` dormant: `825` companies (`82.5%`)
- `score=1` emerging: `138` companies (`13.8%`)
- `score=2` active: `15` companies (`1.5%`)
- `score=3` leading: `22` companies (`2.2%`)

This means only `37/1000` companies (`3.7%`) in the local sample clear the “active or leading” bar.

## Hand-Label Validation

I hand-labeled `30` companies across all four readiness bands using the public descriptions and category metadata already present in the local snapshot, then compared those labels against the heuristic output stored in [data/processed/market_map/manual_labels.json](/home/bethel/Documents/10academy/Conversion Engine for Sales Automation/data/processed/market_map/manual_labels.json).

| Band | Precision | Recall | Support |
| --- | --- | --- | --- |
| Dormant | `1.000` | `1.000` | `8` |
| Emerging | `0.750` | `0.667` | `9` |
| Active | `0.571` | `0.571` | `7` |
| Leading | `0.714` | `0.833` | `6` |

Overall:

- Macro precision: `0.759`
- Macro recall: `0.768`
- Exact-match accuracy: `0.767`
- 95% Wilson interval for exact-match accuracy: `[0.591, 0.882]`

## Known Error Modes

False positives:

- Companies that say “AI”, “analytics”, or “automation” in marketing copy without showing a strong operating signal.
- Services firms whose descriptions overstate technical depth relative to what can be verified from public metadata.

False negatives:

- Data-heavy firms that avoid explicit AI vocabulary in their public descriptions.
- Stealth or services-led teams that likely have internal AI capability but expose little public evidence in the snapshot.

## Interpretation

The heuristic is good enough for a cheap first-pass market map, but not good enough to run unattended strategy decisions without review. Dormant detection is strong; the weakest bands are `emerging` and `active`, where descriptive language is noisy and easy to over- or under-score. That is why the operational recommendation is:

1. Use the heuristic to rank sectors and cells cheaply.
2. Hand-review the top cells before committing outbound volume.
3. Keep the kill-switch active through `LIVE_OUTBOUND` so the system can be paused immediately if complaint or reply-rate metrics break.
