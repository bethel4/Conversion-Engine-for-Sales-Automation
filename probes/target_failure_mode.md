# Target Failure Mode

## Winner

`signal_over_claiming` is the single highest-ROI failure mode to fix first.

The layoff/funding misclassification is the worst single-event miss by business cost, but signal over-claiming wins on ROI because it triggers much more often, is already partially fixable with local phrasing controls, and compounds directly into Tenacious’s known stalled-thread problem.

## Assumptions

These are the business assumptions used for the derivation:

- Average contract value: `$480K ACV`
- Outbound volume: `60` prospects per week
- Annual outbound volume: `60 × 52 = 3,120`
- Discovery conversion from a healthy thread: `35%`
- Existing stalled-thread rate: `30-40%`; use midpoint `35%`
- Conservative close rate from discovery: `15%`
- Weak hiring signal prevalence: `30%` of outbound
- Incremental avoidable stall attributable to over-claiming in the weak-signal slice: `6 percentage points`
- Share of outbound that is genuinely ICP-qualified enough to matter financially: `8%`

The first four values come from the challenge framing and examples. The last three are conservative modeling assumptions used only to rank ROI.

## Math

### 1) How often does it trigger?

- Annual outbound = `3,120`
- Weak-signal slice = `3,120 × 30% = 936`
- Financially relevant prospects inside that slice = `936 × 8% = 74.88`, or about `75`

### 2) What is the incremental harm?

- If over-claiming adds `6%` avoidable stalls in that qualified weak-signal slice:
- Lost qualified threads per year = `75 × 6% = 4.5`

### 3) What is each lost thread worth?

Expected revenue per qualified thread:

- `$480K ACV × 35% discovery conversion × 15% close-from-discovery`
- `= $25.2K expected revenue per qualified thread`

Pipeline value at discovery per qualified thread:

- `$480K × 35% = $168K weighted pipeline`

### 4) Annual impact

Expected revenue lost:

- `4.5 × $25.2K = $113.4K / year`

Weighted pipeline lost:

- `4.5 × $168K = $756K / year`

This is the conservative floor because it excludes:

- Brand damage from visibly fabricated research
- Multi-contact account contamination after a bad first impression
- Additional sender reputation damage from repeated negative replies

## Why It Beats Other Candidates

### Versus ICP layoff misclassification

- `icp_misclassification` has the highest single-thread downside.
- It likely triggers less often than weak-signal over-claiming.
- The fix is also narrow and already mostly in place.
- ROI is therefore lower than the broader weak-signal problem, even though per-event cost is higher.

### Versus bench over-commitment

- `bench_over_commitment` is catastrophic when it happens.
- It should occur relatively rarely because explicit staffing-capacity questions are a later-funnel event.
- The newly added bench gate is also a simple hard block, so residual risk is smaller.

### Versus scheduling edge cases

- Scheduling errors hurt high-intent opportunities, but they happen later and less frequently than weak-signal messaging errors.
- Timezone handling is now mostly a deterministic systems problem rather than a pervasive language problem.

## Fix Cost

Fix cost is medium, not high:

- Existing `phrase_with_confidence()` logic already supports `assert` / `hedge` / `ask`
- Existing `audit_overclaiming()` already blocks low-confidence growth language
- The missing work is mostly composer-level enforcement and broader regression coverage, not novel modeling

That means the ratio of:

- high trigger frequency
- meaningful business cost
- medium implementation effort

is best for `signal_over_claiming`.

## Recommendation

Prioritize signal over-claiming as the top failure mode for the next iteration.

Concrete next steps:

1. Route every weak or missing hiring signal through the low-confidence phrasing path by default.
2. Make `audit_overclaiming()` a hard send-block, not just a diagnostic.
3. Add composer-level snapshot tests for weak-signal emails so the guardrail covers final outbound copy, not just helper functions.
4. Log over-claiming audit failures to the evaluation layer so probe regressions are visible before send.
