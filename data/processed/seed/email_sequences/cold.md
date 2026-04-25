# Cold Outreach Email Sequence

Three-email cold sequence. The agent composes each email fresh per prospect using the hiring signal brief and competitor gap brief, but preserves the structure and tone markers below. **Re-generating these emails verbatim across prospects is a tone violation** — the whole point is that each prospect sees a signal-grounded message, not a template.

---

## Email 1 — Signal-grounded opener

**Timing:** Day 0 (first contact).

**Subject line patterns** (pick the one that matches the highest-confidence signal):
- `Context: [specific funding event]` — Segment 1
- `Note on [specific restructure or layoff event]` — Segment 2
- `Congrats on the [role] appointment` — Segment 3
- `Question on [specific capability signal]` — Segment 4

**Body structure** (max 120 words):

```
[Salutation — first name only, no "Hi there" or "Dear"]

[Sentence 1: single concrete fact from the hiring signal brief.
 Must be verifiable against a public source.]

[Sentence 2: the typical bottleneck or opportunity companies in this
 state hit. Frame as observation, not assertion.]

[Sentence 3: one specific thing Tenacious does that matches the state.
 No service menu, no "we also do X."]

[Sentence 4: the ask. 15 minutes. A specific day. Cal.com link.]

[Signature: first name, title, Tenacious, gettenacious.com]
```

### Example — Segment 1

> Subject: Context: your $14M Series B and the Python team
>
> Elena,
>
> You closed the Series B in February and have three Python-engineering roles open on Wellfound since then. The typical bottleneck for teams in that state is recruiting capacity, not budget.
>
> We run dedicated engineering squads for companies scaling post-Series-B — senior engineers available in 7–14 days, embedded in your stack, with a 3-hour minimum overlap with Pacific time. Not a staffing agency; a delivery team.
>
> Worth 15 minutes next Tuesday or Wednesday to walk you through how that lands? → [Cal link]
>
> Elena
> Research Partner, Tenacious Intelligence Corporation
> gettenacious.com

### Example — Segment 3

> Subject: Congrats on the CTO appointment
>
> Marcus,
>
> Congratulations on the CTO role at Orrin — LinkedIn shows you started in late January. In our experience, the first 90 days are when vendor mix gets a fresh look.
>
> If offshore delivery is on your list for that review, we'd welcome 15 minutes to walk you through our model — managed teams, not staff aug, and full time-zone overlap with US East.
>
> No pitch deck on the first call. A conversation about what your first-90-days vendor reassessment should probably include.
>
> → [Cal link]
>
> Marcus
> Research Partner, Tenacious Intelligence Corporation
> gettenacious.com

---

## Email 2 — Research-finding follow-up

**Timing:** Day 5 (if no reply to Email 1).

**Purpose:** Not a nag. The agent introduces a **new piece of information** — typically a specific competitor-gap finding from the competitor gap brief — and lets that new content justify the touch.

**Subject line patterns:**
- `One more data point: [specific peer-company signal]`
- `Your peer [sector] companies and [specific capability]`
- `Follow-up with a specific comparison` — only when the gap is unambiguous

**Body structure** (max 100 words):

```
[Short opener — one line, no "just following up" or "circling back"]

[The new data point — grounded in competitor_gap_brief.json.
 Two sentences maximum. Specific peer companies named where public.]

[The question the finding raises. Not an assertion that the prospect is
 behind — a question about whether the pattern is deliberate.]

[The ask, softer than Email 1 — a conversation about the pattern, not
 a product pitch.]

[Signature]
```

### Example — Segment 4

> Subject: Your peer platforms and the MLOps function
>
> Marcus,
>
> Adding one data point from our research on platforms at your stage.
>
> Three companies in your sub-niche (Adludio, Protaige, and one I can share on a call) have opened MLOps-engineer roles in the last 60 days. Orrin has not — curious whether that's a deliberate choice, a scoping-in-progress, or just not on the public job board yet.
>
> No pitch here, just interested in the pattern. If you want to compare notes → [Cal link].
>
> Marcus
> Research Partner, Tenacious Intelligence Corporation
> gettenacious.com

---

## Email 3 — The gracious close

**Timing:** Day 12 (if no reply to Email 2).

**Purpose:** Close the thread with dignity. Leave a door open without pestering. Research shows that a clean close outperforms a fourth follow-up on both immediate reply rate and six-month pipeline conversion.

**Subject line patterns:**
- `Closing the loop on [original topic]`
- `Last note from my side`

**Body structure** (max 70 words):

```
[One sentence acknowledging the thread is likely not a fit right now.]

[One sentence with a specific, non-pushy invitation — e.g., a link to a
 longer-form artifact (not a lead magnet), an offer to share raw signal
 data, or a note that the agent will reach out again in 6 months.]

[Signature]
```

### Example

> Subject: Closing the loop on our research note
>
> Elena,
>
> I'll stop bothering your inbox — looks like the timing isn't right, which is fine.
>
> If the hiring-velocity data on your sector would be useful on its own, happy to send a one-pager; reply "yes" and I'll drop it in your inbox with no calendar ask. Otherwise I'll check back in Q3.
>
> All the best,
>
> Elena
> Research Partner, Tenacious Intelligence Corporation
> gettenacious.com

---

## What the sequence must NOT do

- **No bumping the thread.** Three emails is the maximum. A fourth touch within 30 days is a policy violation and will be caught in the tone-preservation probe.
- **No fake urgency.** "Your competitors are moving fast" is a ban. The data carries itself or it does not.
- **No social proof dumps.** Logos, case-study names, and customer counts do not belong in cold outreach to a senior engineering leader. They read as marketing filler.
- **No "just circling back," "hope this finds you well," "wanted to touch base."** These phrases are a tone violation under the Direct marker.

## Sequence termination rules

The agent stops the sequence immediately when:

1. The prospect replies (thread moves to the reply-handling module).
2. The prospect opts out (handled by the email handler).
3. The prospect bounces or the address is invalid (logged, contact marked closed in HubSpot).
4. A later enrichment pass indicates the prospect should be disqualified under the ICP definition (e.g., a layoff event occurs between Email 1 and Email 2). Close the thread, log the reason.

## Per-segment adjustments

The base sequence above is for Segment 1 and Segment 3. Adjust:

- **Segment 2** (mid-market restructuring): Soften the urgency language in Email 1. Post-restructure CFOs are wary of high-energy outbound. Lead with the restructure date as a neutral fact, not a "window closing" framing.
- **Segment 4** (specialized capability): Email 2 competitor-gap content is more important than for other segments — the gap brief is the core value proposition.
- **Low AI-readiness (score 0–1)**: Never use Segment 4 pitch language. Default to Segment 1 or Segment 2 framing with softer AI-adjacent vocabulary.
