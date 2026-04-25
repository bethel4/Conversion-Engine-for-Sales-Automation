# Tenacious ICP Definition

Four segments. Segment names are fixed for grading. Filters and pitch language may be adapted by your agent within the rules below.

---

## Segment 1 — Recently-funded Series A/B startups

### Qualifying filters
- Closed a Series A or Series B round in the last **180 days**, between **$5M and $30M**.
- Headcount **15–80** per LinkedIn or Crunchbase public count.
- Headquartered in North America, UK, Germany, France, Nordics, or Ireland. Other regions require manual approval.
- At least **five open engineering roles** on public job boards (BuiltIn, Wellfound, LinkedIn company page).

### Disqualifying filters
- Raised from a corporate-strategic investor only (no financial lead). These prospects typically have captive delivery capacity and do not buy offshore.
- Explicitly anti-offshore founder public stance — LinkedIn posts, podcasts, blog. If a founder has written about "why we will never outsource," the prospect is dead for Tenacious, skip.
- Already listed as a client of a direct Tenacious competitor (Andela, Turing, Revelo, TopTal) on the competitor's public case-study page.
- Layoff event in the last **90 days** of more than **15% of headcount** — this indicates cost pressure that shifts them to Segment 2, not Segment 1.

### Why they buy
Budget is fresh and runway is the clock. They need to scale engineering output faster than in-house recruiting can support. Tenacious lands here as a speed lever, not a cost lever.

### Pitch language
- **High AI-readiness (score 2–3)**: "scale your AI team faster than in-house hiring can support"
- **Low AI-readiness (score 0–1)**: "stand up your first AI function with a dedicated squad"

### Expected ACV
Talent outsourcing: \$[ACV_MIN]–\$[ACV_MAX] weighted by team size. Confirm against `seed/baseline_numbers.md` — do not invent.

---

## Segment 2 — Mid-market platforms restructuring cost

### Qualifying filters
- Public company or late-stage (Series C or later) with headcount **200–2,000**.
- Layoff event in the last **120 days** per layoffs.fyi, OR post-restructure press release in the last **90 days**.
- Engineering function remains active — at least **three open engineering roles** on public job boards after the layoff event. Zero open roles signals a frozen hire and the prospect is not buying.
- Public filings or press that signal cost discipline language from the CFO or CEO in the last two quarters.

### Disqualifying filters
- Layoff percentage above **40%** in a single event. Companies that deep in restructuring are typically in survival mode, not vendor expansion.
- Bankruptcy, acquisition in process, or going-private transaction announced in the last 180 days.
- Headquartered in a jurisdiction where offshore-delivery regulation is complex (certain federal contractors, regulated-defense tier). Check with program staff.

### Why they buy
Replace higher-cost in-house roles with offshore equivalents to preserve delivery capacity. A quiet signal of operational discipline to the board. Tenacious lands here as a cost lever with reliability guarantees.

### Pitch language
- **High AI-readiness (score 2–3)**: "preserve your AI delivery capacity while reshaping cost structure"
- **Low AI-readiness (score 0–1)**: "maintain platform delivery velocity through the restructure"

### Expected ACV
Talent outsourcing: \$[MID_OUTSOURCING_MIN]–\$[MID_OUTSOURCING_MAX] weighted by team size. Higher than Segment 1 because commitments tend to be longer (12–24 months) — the buyer is explicitly swapping in offshore headcount for retained headcount.

---

## Segment 3 — Engineering-leadership transitions

### Qualifying filters
- New **CTO** or **VP Engineering** appointed in the last **90 days** per Crunchbase People, press release, or LinkedIn "started a new position" post.
- Headcount **50–500** — the transition window matters most at this scale; below 50, founders do engineering themselves and below 500 means a new leader can actually reshape vendor mix; above 500, vendor decisions go through procurement and the 90-day window is too short.
- No announced CFO or CEO transition in the same 90-day window — a dual transition typically freezes procurement.

### Disqualifying filters
- New leader is an interim / acting appointment. Interim leaders rarely sign new vendor contracts.
- New leader's public history shows a strong in-house bias. Check their previous companies' public team-page language and any public writing.
- Tenacious or a direct competitor held a material vendor relationship with the company during the prior CTO's tenure — new leaders reassess, and this information is ambiguous without a warm introduction.

### Why they buy
New leaders routinely reassess vendor contracts and offshore mix in their first 6 months. This is a narrow but high-conversion window — the same prospect 9 months later is usually locked into their chosen vendor stack.

### Pitch language
AI-readiness score does **not** shift the pitch for Segment 3. The new leader's own AI stance is the variable that matters, not the prior state of the company. Open with a grounded reference to the transition (e.g., "congratulations on the CTO appointment — the first 90 days are typically when vendor mix gets reassessed") and let the leader's reply direct the technical language.

### Expected ACV
Variable. The segment converts at a higher rate than 1 or 2 but the deals span the full range — from a single dedicated squad (\$[SQUAD_MIN]) to a full platform-engineering restructure (\$[PLATFORM_MAX]+).

---

## Segment 4 — Specialized capability gaps

### Qualifying filters
- Company attempting a specific build that requires capability they do not have in-house. Signals include:
  - Repeated job postings for the same specialist role (ML platform engineer, agentic-systems engineer, data-contracts lead) open for 60+ days without hire.
  - Press or blog announcing a specific strategic initiative (e.g., "launching our AI product line in Q3") without corresponding team-page changes.
  - Conference talks or podcasts where the CTO describes a specific technical challenge that matches Tenacious project-consulting offerings.
- **AI-readiness score 2 or above**. Segment 4 is only pitched at readiness 2+; reaching out to a score-0 prospect with a Segment 4 pitch wastes the contact and damages the brand.

### Disqualifying filters
- AI-readiness score 0 or 1 (see above).
- The specific capability they need is not on Tenacious's current bench summary. Consulting engagements must be bench-feasible at proposal time.
- Prospect is currently public-case-studied by a specialist boutique firm in exactly the capability they need — the switching cost is too high for an outbound conversation.

### Why they buy
Project-based consulting, not outsourcing. They need a bounded delivery with a defined outcome — higher margin for Tenacious, shorter commitment for the client, and a portfolio artifact that grows the capability bench afterward.

### Pitch language
Always grounded in the specific capability gap inferred from public signal. The competitor gap brief is most valuable here — Segment 4 pitches lean on "three companies in your sector at your stage are doing X and you are not" more than any other segment.

### Expected ACV
Project consulting: \$[PROJECT_ACV_MIN]–\$[PROJECT_ACV_MAX] per engagement. See `seed/baseline_numbers.md` for the lower realized floor of \$[PROJECT_ACV_MIN] for starter fixed-scope work.

---

## Classification rules

When a prospect matches more than one segment, apply in order:

1. If layoff in last 120 days AND fresh funding: **Segment 2** (cost pressure dominates the buying window).
2. If new CTO/VP Eng in last 90 days: **Segment 3** (transition window dominates).
3. If specialized capability signal AND AI-readiness ≥ 2: **Segment 4**.
4. Otherwise, if fresh funding in last 180 days: **Segment 1**.
5. Otherwise, **abstain** — send a generic exploratory email, do not segment-specific pitch. This abstention case is part of the grading in Act IV.

## Confidence reporting

Your classifier must report confidence in the match as a number in [0, 1] based on how many qualifying filters fired versus how many relied on weak or inferred signals. Low confidence (< 0.6) should trigger the abstention path above.

## Do not adapt without documentation

The four segment names above are fixed for grading. You may refine the qualifying and disqualifying filters in your own classifier with justification in `method.md`, but you may not rename, merge, or split segments. A fifth segment is not permitted.
