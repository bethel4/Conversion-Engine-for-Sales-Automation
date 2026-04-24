"use client";

import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";
import { Briefcase, Database, Flame, GitCompare, Loader2, Mail, Search, Sparkles, Users } from "lucide-react";

type Confidence = "high" | "medium" | "low" | "none";

type HiringBrief = Record<string, any>;
type CompetitorGapBrief = Record<string, any>;

type EnrichResult =
  | { status: "ok"; hiring: { brief: HiringBrief; brief_path: string }; competitor_gap: { brief: CompetitorGapBrief; brief_path: string } }
  | Record<string, any>;

function ConfidenceBadge({ value }: { value: Confidence | string | undefined }) {
  const v = (value ?? "none") as Confidence;
  const cls =
    v === "high"
      ? "bg-emerald-100 text-emerald-800"
      : v === "medium"
        ? "bg-amber-100 text-amber-900"
        : v === "low"
          ? "bg-rose-100 text-rose-800"
          : "bg-slate-100 text-slate-700";
  return <Badge className={cn("border-none", cls)}>{v}</Badge>;
}

export default function Page() {
  const [companyName, setCompanyName] = useState("Consolety");
  const [domain, setDomain] = useState("");
  const [usePlaywright, setUsePlaywright] = useState(false);
  const [peersLimit, setPeersLimit] = useState(10);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<EnrichResult | null>(null);

  const [prospectEmail, setProspectEmail] = useState("you+consolety@test.com");
  const [emailSubject, setEmailSubject] = useState("Quick idea for Consolety");
  const [emailText, setEmailText] = useState(
    "Saw a few signals worth sharing — open to a quick chat?"
  );
  const [hubspotLoading, setHubspotLoading] = useState(false);
  const [hubspotResult, setHubspotResult] = useState<any>(null);
  const [sendLoading, setSendLoading] = useState(false);
  const [sendResult, setSendResult] = useState<any>(null);
  const [replyText, setReplyText] = useState("Yes — can you share what you found?");
  const [replyLoading, setReplyLoading] = useState(false);
  const [replyResult, setReplyResult] = useState<any>(null);
  const [bookingId, setBookingId] = useState("demo-booking-001");
  const [bookingLoading, setBookingLoading] = useState(false);
  const [bookingResult, setBookingResult] = useState<any>(null);

  const hiringBrief: HiringBrief | null = useMemo(() => {
    if (!result || (result as any).status !== "ok") return null;
    return (result as any).hiring?.brief ?? null;
  }, [result]);

  const gapBrief: CompetitorGapBrief | null = useMemo(() => {
    if (!result || (result as any).status !== "ok") return null;
    return (result as any).competitor_gap?.brief ?? null;
  }, [result]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    setHubspotResult(null);
    setSendResult(null);
    setReplyResult(null);
    setBookingResult(null);
    try {
      const res = await fetch("/api/enrich", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          company_name: companyName,
          domain: domain.trim() || null,
          use_playwright: usePlaywright,
          peers_limit: peersLimit
        })
      });
      const data = (await res.json()) as EnrichResult;
      if (!res.ok) {
        const detail = (data as any)?.detail ?? (data as any)?.error ?? "Request failed";
        throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
      }
      setResult(data);
    } catch (err: any) {
      setError(err?.message ?? "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  async function enrichToHubSpot() {
    setHubspotLoading(true);
    setHubspotResult(null);
    try {
      const res = await fetch("/api/enrich-hubspot", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: prospectEmail,
          company_name: companyName,
          domain: domain.trim() || null
        })
      });
      const data = await res.json().catch(() => ({}));
      setHubspotResult({ status: res.status, data });
      if (!res.ok) {
        const detail = (data as any)?.detail ?? (data as any)?.error ?? "HubSpot enrichment failed";
        throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
      }
    } catch (err: any) {
      setError(err?.message ?? "Unknown error");
    } finally {
      setHubspotLoading(false);
    }
  }

  async function sendEmail() {
    setSendLoading(true);
    setSendResult(null);
    try {
      const res = await fetch("/api/send-email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          to: [prospectEmail],
          subject: emailSubject,
          text: emailText
        })
      });
      const data = await res.json().catch(() => ({}));
      setSendResult({ status: res.status, data });
      if (!res.ok) {
        const detail = (data as any)?.detail ?? (data as any)?.error ?? "Send failed";
        throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
      }
    } catch (err: any) {
      setError(err?.message ?? "Unknown error");
    } finally {
      setSendLoading(false);
    }
  }

  const lastMessageId: string | null = useMemo(() => {
    const id = sendResult?.data?.result?.id;
    return typeof id === "string" && id.trim() ? id : null;
  }, [sendResult]);

  async function simulateReply() {
    setReplyLoading(true);
    setReplyResult(null);
    try {
      if (!lastMessageId) throw new Error("Send an email first (no message_id yet).");
      const res = await fetch("/api/simulate-reply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sender_email: prospectEmail,
          message_id: lastMessageId,
          subject: emailSubject,
          text: replyText,
          to: []
        })
      });
      const data = await res.json().catch(() => ({}));
      setReplyResult({ status: res.status, data });
      if (!res.ok) {
        const detail = (data as any)?.detail ?? (data as any)?.error ?? "Reply simulation failed";
        throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
      }
    } catch (err: any) {
      setError(err?.message ?? "Unknown error");
    } finally {
      setReplyLoading(false);
    }
  }

  async function simulateBooking() {
    setBookingLoading(true);
    setBookingResult(null);
    try {
      const res = await fetch("/api/simulate-booking", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: prospectEmail,
          booking_id: bookingId,
          status: "confirmed"
        })
      });
      const data = await res.json().catch(() => ({}));
      setBookingResult({ status: res.status, data });
      if (!res.ok) {
        const detail = (data as any)?.detail ?? (data as any)?.error ?? "Booking simulation failed";
        throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
      }
    } catch (err: any) {
      setError(err?.message ?? "Unknown error");
    } finally {
      setBookingLoading(false);
    }
  }

  return (
    <main className="min-h-screen px-6 py-10">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-8">
        <header className="flex flex-col gap-2">
          <div className="inline-flex items-center gap-2 text-primary">
            <Sparkles className="h-5 w-5" />
            <span className="font-body text-sm text-muted-foreground">Lead Catalyst Pro</span>
          </div>
          <h1 className="font-headline text-4xl font-bold tracking-tight text-primary">Signal Enrichment Dashboard</h1>
          <p className="max-w-3xl text-muted-foreground">
            Run the local-only enrichment pipeline (Crunchbase ODM + job posts + layoffs + leadership + AI maturity) and
            view the merged <code className="rounded bg-muted px-1.5 py-0.5">hiring_signal_brief</code> and{" "}
            <code className="rounded bg-muted px-1.5 py-0.5">competitor_gap_brief</code> artifacts.
          </p>
        </header>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Search className="h-5 w-5 text-accent" /> Enrich a company
            </CardTitle>
            <CardDescription>Calls the FastAPI backend at <code className="rounded bg-muted px-1.5 py-0.5">/enrichment/hiring-brief</code> and <code className="rounded bg-muted px-1.5 py-0.5">/enrichment/competitor-gap</code>.</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={onSubmit} className="grid gap-6">
              <div className="grid gap-2">
                <label className="text-sm text-muted-foreground">Company name</label>
                <Input value={companyName} onChange={(e) => setCompanyName(e.target.value)} placeholder="Stripe" />
              </div>
              <div className="grid gap-2">
                <label className="text-sm text-muted-foreground">Domain (optional)</label>
                <Input value={domain} onChange={(e) => setDomain(e.target.value)} placeholder="stripe.com" />
              </div>
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <Switch checked={usePlaywright} onCheckedChange={setUsePlaywright} />
                  <div className="leading-tight">
                    <div className="text-sm">Use Playwright</div>
                    <div className="text-xs text-muted-foreground">Headless scraping (no login / no captcha bypass).</div>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <label className="text-sm text-muted-foreground">Peers</label>
                  <Input
                    className="w-24"
                    type="number"
                    min={1}
                    max={25}
                    value={peersLimit}
                    onChange={(e) => setPeersLimit(Number(e.target.value || 10))}
                  />
                </div>
              </div>
              <Button type="submit" className="gap-2 shadow-lg shadow-primary/20" disabled={loading}>
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Database className="h-4 w-4" />}
                Run enrichment
              </Button>
              {error ? (
                <div className="rounded-2xl bg-rose-50 p-4 text-sm text-rose-800 ring-1 ring-rose-200">
                  {error}
                </div>
              ) : null}
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="h-5 w-5 text-accent" /> Prospect actions (Render demo)
            </CardTitle>
            <CardDescription>
              Unbroken on-screen lifecycle: enrich → send → reply → qualify → booking step. All calls go to your backend so
              secrets stay server-side (Resend/HubSpot keys live in Render env vars).
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-6">
            <div className="grid gap-2">
              <label className="text-sm text-muted-foreground">Prospect email</label>
              <Input value={prospectEmail} onChange={(e) => setProspectEmail(e.target.value)} placeholder="you+consolety@test.com" />
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="grid gap-2">
                <label className="text-sm text-muted-foreground">Email subject</label>
                <Input value={emailSubject} onChange={(e) => setEmailSubject(e.target.value)} />
              </div>
              <div className="grid gap-2">
                <label className="text-sm text-muted-foreground">Email text</label>
                <Input value={emailText} onChange={(e) => setEmailText(e.target.value)} />
              </div>
            </div>

            <div className="flex flex-wrap gap-3">
              <Button type="button" variant="secondary" className="gap-2" onClick={enrichToHubSpot} disabled={hubspotLoading}>
                {hubspotLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Database className="h-4 w-4" />}
                Enrich → HubSpot
              </Button>
              <Button type="button" className="gap-2 shadow-lg shadow-primary/20" onClick={sendEmail} disabled={sendLoading}>
                {sendLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Mail className="h-4 w-4" />}
                Send email (Resend)
              </Button>
            </div>

            <div className="grid gap-4 rounded-2xl bg-card p-5 shadow-sm ring-1 ring-border/50">
              <div className="text-sm font-medium text-foreground">Reply + booking (for video continuity)</div>
              <div className="grid gap-2">
                <label className="text-sm text-muted-foreground">Reply text</label>
                <Input value={replyText} onChange={(e) => setReplyText(e.target.value)} />
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <Button type="button" variant="secondary" className="gap-2" onClick={simulateReply} disabled={replyLoading}>
                  {replyLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Mail className="h-4 w-4" />}
                  Simulate reply webhook
                </Button>
                <div className="text-xs text-muted-foreground">
                  message_id:{" "}
                  <code className="rounded bg-muted px-1.5 py-0.5">{lastMessageId ?? "n/a"}</code>
                </div>
              </div>

              <div className="grid gap-2 md:grid-cols-2">
                <div className="grid gap-2">
                  <label className="text-sm text-muted-foreground">Booking id</label>
                  <Input value={bookingId} onChange={(e) => setBookingId(e.target.value)} />
                </div>
                <div className="flex items-end gap-3">
                  <Button type="button" variant="secondary" className="gap-2" onClick={simulateBooking} disabled={bookingLoading}>
                    {bookingLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Database className="h-4 w-4" />}
                    Simulate booking webhook
                  </Button>
                </div>
              </div>

              <div className="text-xs text-muted-foreground">
                Tip: set <code className="rounded bg-muted px-1.5 py-0.5">CALCOM_BOOKING_LINK</code> on Render to auto-send a booking link email after the reply is received.
              </div>
            </div>

            {(hubspotResult || sendResult || replyResult || bookingResult) ? (
              <details className="rounded-2xl bg-muted p-4 ring-1 ring-border/50">
                <summary className="cursor-pointer select-none text-sm font-medium">Action responses</summary>
                <pre className="mt-3 max-h-80 overflow-auto text-xs">
                  {JSON.stringify(
                    { hubspot: hubspotResult, email: sendResult, reply: replyResult, booking: bookingResult },
                    null,
                    2
                  )}
                </pre>
              </details>
            ) : null}
          </CardContent>
        </Card>

        {hiringBrief ? (
          <section className="grid gap-6 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Briefcase className="h-5 w-5 text-accent" /> Hiring signal brief
                </CardTitle>
                <CardDescription>
                  Saved to <code className="rounded bg-muted px-1.5 py-0.5">{(result as any)?.hiring?.brief_path}</code>
                </CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 text-sm">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-medium">Company</div>
                  <ConfidenceBadge value={hiringBrief?.company?._confidence} />
                </div>
                <div className="text-muted-foreground">{hiringBrief?.company?.name}</div>

                <div className="flex items-center justify-between gap-3 pt-2">
                  <div className="font-medium">Funding</div>
                  <ConfidenceBadge value={hiringBrief?.funding?._confidence} />
                </div>
                <div className="text-muted-foreground">
                  funded={String(hiringBrief?.funding?.funded)} · days_ago={String(hiringBrief?.funding?.days_ago)} · type=
                  {String(hiringBrief?.funding?.last_funding_type ?? "n/a")}
                </div>

                <div className="flex items-center justify-between gap-3 pt-2">
                  <div className="font-medium">Job posts</div>
                  <ConfidenceBadge value={hiringBrief?.jobs?._confidence} />
                </div>
                <div className="text-muted-foreground">
                  eng={String(hiringBrief?.jobs?.engineering_roles)} · ai/ml={String(hiringBrief?.jobs?.ai_ml_roles)} · strength=
                  {String(hiringBrief?.jobs?.signal_strength)}
                </div>

                <div className="flex items-center justify-between gap-3 pt-2">
                  <div className="font-medium">Layoffs</div>
                  <ConfidenceBadge value={hiringBrief?.layoffs?._confidence} />
                </div>
                <div className="text-muted-foreground">had_layoff={String(hiringBrief?.layoffs?.had_layoff)}</div>

                <div className="flex items-center justify-between gap-3 pt-2">
                  <div className="font-medium">Leadership</div>
                  <ConfidenceBadge value={hiringBrief?.leadership_change?._confidence} />
                </div>
                <div className="text-muted-foreground">
                  new_leader_detected={String(hiringBrief?.leadership_change?.new_leader_detected)} · role=
                  {String(hiringBrief?.leadership_change?.role ?? "n/a")}
                </div>

                <div className="flex items-center justify-between gap-3 pt-2">
                  <div className="font-medium">AI maturity</div>
                  <ConfidenceBadge value={hiringBrief?.ai_maturity?._confidence} />
                </div>
                <div className="text-muted-foreground">
                  score={String(hiringBrief?.ai_maturity?.score)} · confidence={String(hiringBrief?.ai_maturity?.confidence)}
                </div>

                <details className="rounded-2xl bg-muted p-4 ring-1 ring-border/50">
                  <summary className="cursor-pointer select-none text-sm font-medium">Raw JSON</summary>
                  <pre className="mt-3 max-h-80 overflow-auto text-xs">
                    {JSON.stringify(hiringBrief, null, 2)}
                  </pre>
                </details>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <GitCompare className="h-5 w-5 text-accent" /> Competitor gap brief
                </CardTitle>
                <CardDescription>
                  Saved to <code className="rounded bg-muted px-1.5 py-0.5">{(result as any)?.competitor_gap?.brief_path}</code>
                </CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 text-sm">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-medium">Prospect percentile</div>
                  <Badge className="border-none bg-indigo-100 text-indigo-900">
                    {String(gapBrief?.prospect_percentile ?? "n/a")}th
                  </Badge>
                </div>

                <div className="text-muted-foreground">
                  peers={String(gapBrief?.meta?.peer_count ?? (gapBrief?.peers?.length ?? 0))}
                </div>

                <div className="pt-2 font-medium">Top gaps</div>
                <div className="grid gap-2">
                  {(gapBrief?.gaps ?? []).slice(0, 3).map((gap: any, idx: number) => (
                    <div key={idx} className="rounded-2xl bg-card p-4 shadow-sm ring-1 ring-border/50">
                      <div className="flex items-center justify-between gap-3">
                        <div className="truncate font-medium">{gap?.title ?? `Gap ${idx + 1}`}</div>
                        <Badge className="border-none bg-slate-100 text-slate-700">
                          {String(gap?.confidence ?? "heuristic")}
                        </Badge>
                      </div>
                      {gap?.finding ? (
                        <div className="mt-2 text-muted-foreground">{String(gap.finding)}</div>
                      ) : null}
                    </div>
                  ))}
                </div>

                <details className="rounded-2xl bg-muted p-4 ring-1 ring-border/50">
                  <summary className="cursor-pointer select-none text-sm font-medium">Raw JSON</summary>
                  <pre className="mt-3 max-h-80 overflow-auto text-xs">
                    {JSON.stringify(gapBrief, null, 2)}
                  </pre>
                </details>
              </CardContent>
            </Card>
          </section>
        ) : null}

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Flame className="h-5 w-5 text-accent" /> Notes
            </CardTitle>
            <CardDescription>Where outputs are stored and what to do if something fails.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-2 text-sm text-muted-foreground">
            <div>
              Brief JSON files are written by the backend to <code className="rounded bg-muted px-1.5 py-0.5">data/briefs/</code>.
            </div>
            <div>
              If you see <code className="rounded bg-muted px-1.5 py-0.5">No Crunchbase record found</code>, add the ODM sample
              under <code className="rounded bg-muted px-1.5 py-0.5">data/raw/crunchbase/</code>.
            </div>
            <div>
              If <code className="rounded bg-muted px-1.5 py-0.5">RESEND_API_KEY is not set</code> shows up, add it in Render
              Environment (local <code className="rounded bg-muted px-1.5 py-0.5">.env</code> does not apply to Render).
            </div>
            <div>
              If you enable Playwright, make sure you ran <code className="rounded bg-muted px-1.5 py-0.5">python3 -m playwright install chromium</code>.
            </div>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
