# Act IV Mechanism Design

## Target Failure Mode

The primary failure mode is **confident but weakly grounded outreach**: the system sends a personalized-looking email even when the upstream signals do not justify a strong claim. The root cause is not only prompt quality. It is the absence of a hard mechanism that:

1. carries evidence quality forward from enrichment into messaging,
2. abstains when the best segment match is still weak,
3. prevents competitor-gap findings from being stated without public evidence, and
4. pauses the outbound path when live quality signals deteriorate.

The mechanism below addresses that root cause by making every stage evidence-aware rather than by only post-editing the final email text.

## Re-Implementable Mechanism

The full mechanism has four stages.

### 1. Signal Normalization

Each enrichment module emits a structured object with:

- signal value(s),
- `_confidence`,
- `checked_at`,
- `signal_timestamp`,
- `source_attribution`.

The four upstream modules are:

1. Crunchbase ODM lookup with funding recency filter
2. Public job-post scraping across first-party careers pages plus public BuiltIn / Wellfound / LinkedIn company jobs pages
3. layoffs.fyi CSV lookup
4. leadership-change detection from provided public press / Crunchbase-style source snippets

Missing-data behavior is explicit:

- missing Crunchbase record: raise `ValueError` and stop brief generation
- no open jobs: return zeros and `signal_strength="none"`
- no layoffs in window: return `had_layoff=false`
- no leadership change in window: return `new_leader_detected=false`

### 2. Evidence-Carrying Hiring Brief

The merged `hiring_signal_brief` is produced in `agent/enrichment/briefs.py`. Each section carries its own evidence metadata and confidence field. The brief sections are:

- `company`
- `funding`
- `jobs`
- `layoffs`
- `leadership_change`
- `ai_maturity`
- `tech_stack`
- `meta`

The brief is the canonical evidence object for downstream reasoning.

### 3. Qualification With Abstention

`agent/enrichment/icp.py` scores four segments:

1. `segment_1`: recently funded growth
2. `segment_2`: restructuring / layoffs
3. `segment_3`: leadership transition
4. `segment_4`: AI capability gap

The classifier computes a score for each segment and chooses the best one. It then applies an abstention threshold.

- if `max(segment_scores) >= 0.60`, emit that segment
- else emit `abstain`

This is the core mechanism that prevents weak evidence from becoming a strong claim.

### 4. Confidence-Aware Messaging

`agent/email_generator.py` transforms:

- hiring brief
- competitor gap brief
- ICP segment
- AI maturity score
- style guide seed files

into the first outbound email.

Generation rule:

- if `segment == "abstain"` or `confidence < 0.60`, generate `fallback_generic`
- otherwise generate `signal_grounded`

The generated email stores provenance:

- `generated_at`
- `prospect_id`
- `thread_id`
- `icp_segment`
- `icp_confidence`
- `signals_used`
- `generation_mode`

This makes the email inspectable as a mechanism output rather than an opaque artifact.

## Hyperparameters And Thresholds

These are the actual values used in source.

### Enrichment windows

- funding lookback: `180` days
- job-post comparison window: `60` days
- layoffs lookback: `120` days
- leadership-change lookback: `90` days

### AI maturity scoring

Raw point to score mapping in `agent/enrichment/ai_maturity.py`:

- raw `>= 2.5` -> score `3`
- raw `>= 1.5` -> score `2`
- raw `>= 0.5` -> score `1`
- raw `< 0.5` -> score `0`

Confidence buckets:

- evidence count `>= 4` -> `high`
- evidence count `>= 2` -> `medium`
- otherwise -> `low`

Pitch hint mapping:

- `high` -> `assert`
- `medium` -> `hedge`
- `low` -> `ask`

### ICP thresholds

- classifier abstention threshold: `0.60`
- Segment 4 hard gate: AI maturity score must be `>= 2`

### Segment-specific rules

Loaded from `data/processed/seed/icp_definition.md`:

- Segment 1 funding window: `180` days
- Segment 1 headcount band: `15-80`
- Segment 1 minimum engineering roles: `5`
- Segment 1 layoff override window: `90` days
- Segment 1 layoff override percentage: `15%`
- Segment 2 layoff window: `120` days
- Segment 2 headcount band: `200-2000`
- Segment 2 maximum layoff percentage: `40%`
- Segment 3 leadership window: `90` days
- Segment 3 headcount band: `50-500`
- Segment 4 minimum AI-readiness score: `2`

### Competitor-gap thresholds

- peer count target: `5-10`
- top-quartile cutoff: peers with AI maturity score `>= Q3`
- gap prevalence threshold: top-quartile prevalence must be `>= 0.60`
- high-confidence gap: prevalence `>= 0.80`
- maximum gap findings returned: `3`

### Tone checker

Loaded from `data/processed/seed/style_guide.md` plus code constants:

- cold email max words: from style guide seed
- score must be `>= 0.70` to mark tone as OK

## Why This Addresses The Root Cause

The bad outcome is not “emails sound generic.” The real problem is **unwarranted specificity**. The mechanism prevents that by:

1. attaching confidence to every upstream signal,
2. preserving evidence structure in the merged brief,
3. forcing the classifier to abstain when no segment clears `0.60`,
4. switching the message generator into `fallback_generic` when confidence is low, and
5. requiring public-signal evidence for competitor-gap findings.

That is a causal fix because it changes what the model is allowed to claim, not only how the claim is worded.

## Ablation Variants

Three ablations are defined against the main mechanism.

### Ablation A: No Abstention

Change:

- remove the `0.60` abstention threshold
- always choose the max-scoring segment

What it tests:

- whether abstention is the main control preventing false-positive personalization

Expected effect:

- higher apparent personalization rate
- worse factual precision
- more weakly grounded segment-specific emails

### Ablation B: No Competitor Gap Evidence Filter

Change:

- keep peer selection
- remove the requirement that a gap must have public evidence rows and top-quartile prevalence `>= 0.60`

What it tests:

- whether evidence-gated gap extraction is necessary to prevent speculative “research findings”

Expected effect:

- more gaps produced
- lower precision of gap findings
- more overclaiming risk in outreach

### Ablation C: No Confidence-Aware Messaging Switch

Change:

- keep enrichment and classification
- remove the `fallback_generic` switch for `segment == abstain` or `confidence < 0.60`
- always generate a segment-specific email

What it tests:

- whether the final messaging switch itself contributes materially beyond upstream scoring

Expected effect:

- more personalized-looking drafts
- higher mismatch between email claims and available evidence

## Statistical Test Plan

The main comparison is **full mechanism vs each ablation** on held-out synthetic prospect tasks and probe cases.

Primary metric:

- proportion of outreach drafts rated “factually supported” by the probe/eval harness

Secondary metrics:

- reply-intent classification accuracy
- competitor-gap evidence precision
- abstention rate
- tone-check pass rate

Planned tests:

1. For paired binary outcomes such as “factually supported / not supported”, use **McNemar’s test** between the full mechanism and each ablation.
2. For scalar metrics like confidence-calibration error or tone score, use a **paired bootstrap confidence interval** over task-level differences.

Decision threshold:

- significance threshold `p < 0.05`

The interpretation rule is:

- if an ablation materially worsens factual support with `p < 0.05`, the removed component is considered necessary to the mechanism.

<!-- market-map:start -->
## Market Map Validation Snapshot

This section is generated from `agent.market_map` and summarizes the batch market-space scoring outputs.

### Dataset

- Source: `/home/bethel/Documents/10academy/Conversion Engine for Sales Automation/data/raw/crunchbase/crunchbase-companies-information.csv`
- Companies scored: 1000
- Dataset as of: 2024-07-22

### Scoring Logic

- AI readiness is scored from 0 to 3 using keyword and industry evidence from company descriptions, industries, and named technologies.
- Sector is assigned with deterministic keyword rules over industries and company text.
- Size band is derived from Crunchbase employee ranges.
- Recent funding uses the last 12 months of disclosed rounds.
- Bench match estimates how well the company stack aligns with Tenacious bench supply.

### Cell Ranking

- Cells are grouped by `sector + size_band + ai_readiness`.
- Cells with fewer than 3 companies are dropped from priority ranking.
- Combined score weights population, average recent funding, and bench match.

### Validation

- Manual label sample size: 30
- Macro precision: 0.759
- Macro recall: 0.768
- Exact-match accuracy: 0.767
- 95% CI for accuracy: [0.591, 0.882]

#### Per-Band Metrics

| Band | Precision | Recall | Support |
| --- | ---: | ---: | ---: |
| dormant | 1.0 | 1.0 | 8 |
| emerging | 0.75 | 0.667 | 9 |
| active | 0.571 | 0.571 | 7 |
| leading | 0.714 | 0.833 | 6 |

#### Known False Positives

- Marketing copy that says AI or analytics without clear evidence of an actual AI product or team.
- Services firms that mention automation capabilities but do not show sustained AI-readiness signals.

#### Known False Negatives

- Stealth or services-heavy companies with sparse public descriptions and no explicit AI vocabulary.
- Domain-specific data platforms that look operationally advanced but avoid AI terminology in public copy.
<!-- market-map:end -->
