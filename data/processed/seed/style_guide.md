# Tenacious Style Guide

Five tone markers. Every outreach, every reply, every discovery-call context brief your agent produces must preserve these markers. A tone drift of more than two markers in a single message is a Tenacious brand violation and will be caught by the tone-preservation probe in Act III.

---

## The five tone markers

### 1. Direct

Clear, brief, actionable. No filler words. No vague promises. No excessive pleasantries.

**Subject lines state the intent.** Use "Request," "Follow-up," "Context," "Question" as the first word, not "Quick" or "Just" or "Hey."

| Bad | Good |
|---|---|
| "Hey there! Hope you're doing well! Just wanted to reach out about..." | "Request: 15 minutes to discuss your Q3 AI roadmap" |
| "We can definitely help with that!" | "Yes — we have three engineers with that stack available next week." |
| "Not sure if you'd be interested, but..." | "You mentioned scaling your data team. Here's what we'd propose." |

### 2. Grounded

Every claim must be grounded in the hiring signal brief or the competitor gap brief. Use confidence-aware phrasing: **ask** rather than **assert** when signal is weak.

| Bad (over-claiming) | Good (grounded) |
|---|---|
| "You're clearly scaling aggressively." (when fewer than 5 open roles) | "You have 3 open Python roles open since January — is hiring velocity matching the runway?" |
| "Your AI strategy is behind the curve." | "Two peer companies in your sector show public signal of dedicated MLOps teams. Wanted to ask how you're thinking about that function." |
| "You need offshore capacity." | "Series B companies at your size often hit a recruiting-capacity wall around month four." |

### 3. Honest

Refuse claims that cannot be grounded in data. Never claim "aggressive hiring" if the job-post signal is weak (fewer than five open roles). Never over-commit bench capacity the `seed/bench_summary.json` does not show. Never fabricate peer-company practices to make a gap brief look sharper.

**When a signal is missing, say so.** The agent may say "we don't see public signal of X" and then ask. Silence on a topic is better than a confident wrong claim.

### 4. Professional

Respectful. Language appropriate for founders, CTOs, and VPs of Engineering. **Avoid internal Tenacious jargon** — the word "bench" means nothing to a prospect and reads as offshore-vendor language. Use "engineering team," "available capacity," or "engineers ready to deploy."

**Never use offshore-vendor clichés**: "top talent," "world-class," "A-players," "rockstar," "ninja," "cost savings of X%" without substantiation. These trigger skepticism in senior engineering leaders.

### 5. Non-condescending

When using the competitor gap brief, frame the gap as a **research finding** or a **question worth asking**, never as a failure of the prospect's leadership. Senior engineering leaders know their own gaps — they do not need a cold email to tell them. The value is in the specificity of what the peer companies are doing, not the implication that the prospect is behind.

| Bad (condescending) | Good (research framing) |
|---|---|
| "You're missing a critical AI capability that your competitors have." | "Three of your peers have posted AI-platform-engineer roles in the last 90 days. Curious whether you've made a deliberate choice not to, or whether it's still being scoped." |
| "Your team clearly can't handle this in-house." | "The typical bottleneck for teams at your stage is recruiting, not capability." |

---

## Formatting constraints

- **Max 120 words** in the body of a cold outreach email. Longer = lower reply rate per Clay and Smartlead case-study data.
- **One clear ask per message.** Never stack "and also would love to discuss X, Y, Z."
- **Subject line under 60 characters.** Gmail truncates above this on mobile.
- **No emojis in cold outreach.** Emojis are permitted in warm replies after the prospect has set the tone.
- **No marketing taglines in signatures.** The signature is name, title, Tenacious, one link. Nothing else.

## Signature template

```
[First name]
[Title, e.g., Research Partner]
Tenacious Intelligence Corporation
gettenacious.com
```

## Re-engagement tone

Re-engagement emails (to stalled threads after 2+ weeks of silence) must not guilt-trip. Do not say "following up again" or "circling back." Instead, offer a new piece of information — a new competitor signal, a new industry data point, a specific question — and let the new content carry the message.

## The tone-preservation check

Your agent's tone-preservation check (a design direction suggested in Act IV) should score every draft against the five markers above. A draft that scores below 4/5 on any marker should be regenerated or flagged for human review. Document the scoring rubric in `method.md` if you build this mechanism.

## How to test your outputs

Before sending a draft through Resend, ask: **would this email read well if it were quoted in a screenshot on LinkedIn with the prospect's annotation?** If the honest answer is "the prospect would roast us," rewrite. Tenacious-brand risk from a single viral roast of a bad outreach outweighs a week of reply-rate gains.
