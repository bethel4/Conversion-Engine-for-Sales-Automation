"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";
import {
  ArrowUpRight,
  BrainCircuit,
  Building2,
  CalendarCheck2,
  Database,
  Flame,
  GitCompare,
  Loader2,
  Mail,
  MessageSquareReply,
  RefreshCw,
  Search,
  Send,
  Sparkles,
  Users,
} from "lucide-react";

type Confidence = "high" | "medium" | "low" | "none";
type HiringBrief = Record<string, any>;
type CompetitorGapBrief = Record<string, any>;
type QualificationSnapshot = {
  segment: string;
  confidence: number;
  pitchAngle: string;
} | null;

type ProspectApiRecord = {
  id: string;
  prospect_name: string;
  company: string;
  email: string;
  domain?: string | null;
  phone?: string | null;
  crunchbase_id?: string | null;
  thread_id?: string | null;
  lifecycle_stage?: string | null;
  last_activity?: string | null;
  qualification?: {
    segment?: string | null;
    confidence?: number | null;
    pitch_angle?: string | null;
  } | null;
  email_subject?: string | null;
  email_text?: string | null;
  reply_text?: string | null;
  booking_id?: string | null;
  use_playwright?: boolean | null;
  peers_limit?: number | null;
  latest_hiring_brief?: HiringBrief | null;
  latest_hiring_brief_path?: string | null;
  latest_competitor_gap_brief?: CompetitorGapBrief | null;
  latest_competitor_gap_brief_path?: string | null;
  hubspot?: any;
  last_message_id?: string | null;
  booking_status?: string | null;
  booking_start_time?: string | null;
  booking_title?: string | null;
  activity?: Array<{ type?: string; title?: string; description?: string; timestamp?: string | null }> | null;
};

type ProspectSeed = {
  id: string;
  prospectName: string;
  company: string;
  email: string;
  domain: string;
  phone: string | null;
  crunchbaseId: string;
  threadId: string | null;
  lifecycleStage: string;
  lastActivity: string | null;
  qualification: QualificationSnapshot;
  emailSubject: string;
  emailText: string;
  replyText: string;
  bookingId: string;
  usePlaywright: boolean;
  peersLimit: number;
  latestHiringBrief: HiringBrief | null;
  latestHiringBriefPath: string | null;
  latestCompetitorGapBrief: CompetitorGapBrief | null;
  latestCompetitorGapBriefPath: string | null;
  hubspot: any;
  lastMessageId: string | null;
  bookingStatus: string | null;
  bookingStartTime: string | null;
  bookingTitle: string | null;
  activity: Array<{ type: string; title: string; description: string; timestamp: string | null }>;
};

type EnrichResult =
  | {
      status: "ok";
      hiring: { brief: HiringBrief; brief_path: string };
      competitor_gap: { brief: CompetitorGapBrief; brief_path: string };
      crm?: any;
      prospect?: any;
    }
  | Record<string, any>;

type TimelineEventType =
  | "enrichment_completed"
  | "email_sent"
  | "email_reply_received"
  | "qualification_complete"
  | "booking_link_sent"
  | "call_booked";

type TimelineEntry = {
  type: TimelineEventType;
  title: string;
  description: string;
  timestamp: string | null;
  complete: boolean;
};

type ProspectUiState = {
  domain: string;
  usePlaywright: boolean;
  peersLimit: number;
  emailSubject: string;
  emailText: string;
  replyText: string;
  bookingId: string;
  enrichResult: EnrichResult | null;
  hubspotResult: any;
  sendResult: any;
  replyResult: any;
  bookingResult: any;
  enrichmentLoading: boolean;
  prospectActionLoading: string | null;
  enrichmentError: string | null;
  actionsError: string | null;
  showRawJson: boolean;
  threadId: string | null;
  lifecycleStage: string;
  lastActivity: string | null;
  qualification: QualificationSnapshot;
  timelineEvents: Partial<Record<TimelineEventType, string>>;
  lastMessageId: string | null;
};

const TIMELINE_TEMPLATE: Array<Pick<TimelineEntry, "type" | "title" | "description">> = [
  {
    type: "enrichment_completed",
    title: "Enrichment completed",
    description: "Signal brief, competitor gap, and CRM enrichment are ready for review.",
  },
  {
    type: "email_sent",
    title: "Outreach sent",
    description: "Prospect email was sent through MailerSend.",
  },
  {
    type: "email_reply_received",
    title: "Reply processed",
    description: "Inbound reply has been processed and the thread moved into active follow-up.",
  },
  {
    type: "qualification_complete",
    title: "Qualification complete",
    description: "ICP segment, confidence, and pitch angle are available for the sales team.",
  },
  {
    type: "booking_link_sent",
    title: "Booking link sent",
    description: "Cal.com booking link has been delivered to the prospect.",
  },
  {
    type: "call_booked",
    title: "Booking synced",
    description: "Cal.com booking has been synced back into HubSpot.",
  },
];

function mapProspectRecord(record: ProspectApiRecord): ProspectSeed {
  const qualification = record.qualification
    ? {
        segment: String(record.qualification.segment ?? "abstain"),
        confidence: Number(record.qualification.confidence ?? 0),
        pitchAngle: String(record.qualification.pitch_angle ?? "exploratory_generic"),
      }
    : null;
  return {
    id: record.id,
    prospectName: record.prospect_name,
    company: record.company,
    email: record.email,
    domain: record.domain ?? "",
    phone: record.phone ?? null,
    crunchbaseId: record.crunchbase_id ?? record.company.toLowerCase(),
    threadId: record.thread_id ?? null,
    lifecycleStage: record.lifecycle_stage ?? "New",
    lastActivity: record.last_activity ?? null,
    qualification,
    emailSubject: record.email_subject ?? `Quick signal review for ${record.company}`,
    emailText:
      record.email_text ??
      `Saw a few public signals around ${record.company} that may be worth a closer look. Open to a short exchange?`,
    replyText: record.reply_text ?? "Yes — can you share what you found?",
    bookingId: record.booking_id ?? `booking-${record.id}-001`,
    usePlaywright: Boolean(record.use_playwright),
    peersLimit: Number(record.peers_limit ?? 10),
    latestHiringBrief: record.latest_hiring_brief ?? null,
    latestHiringBriefPath: record.latest_hiring_brief_path ?? null,
    latestCompetitorGapBrief: record.latest_competitor_gap_brief ?? null,
    latestCompetitorGapBriefPath: record.latest_competitor_gap_brief_path ?? null,
    hubspot: record.hubspot ?? null,
    lastMessageId: record.last_message_id ?? null,
    bookingStatus: record.booking_status ?? null,
    bookingStartTime: record.booking_start_time ?? null,
    bookingTitle: record.booking_title ?? null,
    activity: (record.activity ?? []).map((item) => ({
      type: String(item.type ?? ""),
      title: String(item.title ?? ""),
      description: String(item.description ?? ""),
      timestamp: item.timestamp ?? null,
    })),
  };
}

function buildThreadId(company: string) {
  const slug = company
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
  return `thread_${slug || "prospect"}_001`;
}

function formatTimestamp(value: string | null) {
  if (!value) return "No activity yet";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return value;
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(dt);
}

function confidenceClass(value: Confidence | string | undefined) {
  const v = String(value ?? "none").toLowerCase() as Confidence;
  const mapping: Record<Confidence, { label: string; className: string }> = {
    high: { label: "strong", className: "bg-emerald-100 text-emerald-800 ring-emerald-200" },
    medium: { label: "moderate", className: "bg-amber-100 text-amber-900 ring-amber-200" },
    low: { label: "cautious", className: "bg-rose-100 text-rose-800 ring-rose-200" },
    none: { label: "unavailable", className: "bg-slate-100 text-slate-700 ring-slate-200" },
  };
  return mapping[v] ?? mapping.none;
}

function ConfidenceBadge({ value }: { value: Confidence | string | undefined }) {
  const resolved = confidenceClass(value);
  return <Badge className={cn("border-none capitalize", resolved.className)}>{resolved.label}</Badge>;
}

function StatusBadge({ value }: { value: string }) {
  const normalized = value.toLowerCase();
  const cls =
    normalized.includes("booked") || normalized.includes("completed")
      ? "bg-emerald-100 text-emerald-800 ring-emerald-200"
      : normalized.includes("qualified") || normalized.includes("booking")
        ? "bg-sky-100 text-sky-800 ring-sky-200"
        : normalized.includes("reply") || normalized.includes("outreach")
          ? "bg-amber-100 text-amber-900 ring-amber-200"
          : "bg-slate-100 text-slate-700 ring-slate-200";
  return <Badge className={cn("border-none", cls)}>{value}</Badge>;
}

function MetricCard({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <Card className="bg-white/90">
      <CardContent className="p-5">
        <div className="text-xs uppercase tracking-[0.24em] text-muted-foreground">{label}</div>
        <div className="mt-3 text-3xl font-semibold text-foreground">{value}</div>
        <div className="mt-2 text-sm text-muted-foreground">{hint}</div>
      </CardContent>
    </Card>
  );
}

function SignalCard({
  title,
  confidence,
  children,
}: {
  title: string;
  confidence: Confidence | string | undefined;
  children: ReactNode;
}) {
  return (
    <div className="rounded-[24px] border border-border/80 bg-white/85 p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="text-sm font-semibold text-foreground">{title}</div>
        <ConfidenceBadge value={confidence} />
      </div>
      <div className="mt-4 space-y-2 text-sm text-muted-foreground">{children}</div>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-border/60 py-3 last:border-b-0">
      <div className="text-sm text-muted-foreground">{label}</div>
      <div className="text-right text-sm font-medium text-foreground">{value}</div>
    </div>
  );
}

function buildEnrichResult(seed: ProspectSeed): EnrichResult | null {
  if (!seed.latestHiringBrief && !seed.latestCompetitorGapBrief) return null;
  return {
    status: "ok",
    hiring: {
      brief: seed.latestHiringBrief ?? {},
      brief_path: seed.latestHiringBriefPath ?? "",
    },
    competitor_gap: {
      brief: seed.latestCompetitorGapBrief ?? {},
      brief_path: seed.latestCompetitorGapBriefPath ?? "",
    },
  };
}

function createInitialProspectState(seed: ProspectSeed, existing?: ProspectUiState): ProspectUiState {
  const timelineEvents: Partial<Record<TimelineEventType, string>> = { ...(existing?.timelineEvents ?? {}) };
  for (const item of seed.activity) {
    if (item.timestamp && item.type && !(item.type in timelineEvents)) {
      const key = item.type as TimelineEventType;
      if (TIMELINE_TEMPLATE.some((entry) => entry.type === key)) timelineEvents[key] = item.timestamp;
    }
  }
  return {
    domain: existing?.domain ?? seed.domain,
    usePlaywright: existing?.usePlaywright ?? seed.usePlaywright,
    peersLimit: existing?.peersLimit ?? seed.peersLimit,
    emailSubject: existing?.emailSubject ?? seed.emailSubject,
    emailText: existing?.emailText ?? seed.emailText,
    replyText: existing?.replyText ?? seed.replyText,
    bookingId: existing?.bookingId ?? seed.bookingId,
    enrichResult: buildEnrichResult(seed) ?? existing?.enrichResult ?? null,
    hubspotResult: seed.hubspot ? { status: 200, data: { hubspot: seed.hubspot }, timestamp: seed.lastActivity } : existing?.hubspotResult ?? null,
    sendResult: seed.lastMessageId ? { data: { result: { id: seed.lastMessageId } }, timestamp: seed.lastActivity } : existing?.sendResult ?? null,
    replyResult: seed.activity.some((item) => item.type === "email_reply_received")
      ? { status: 200, timestamp: seed.lastActivity }
      : existing?.replyResult ?? null,
    bookingResult: seed.bookingStatus ? { status: 200, data: { booking_status: seed.bookingStatus }, timestamp: seed.lastActivity } : existing?.bookingResult ?? null,
    enrichmentLoading: false,
    prospectActionLoading: null,
    enrichmentError: null,
    actionsError: null,
    showRawJson: existing?.showRawJson ?? false,
    threadId: seed.threadId,
    lifecycleStage: seed.lifecycleStage,
    lastActivity: seed.lastActivity,
    qualification: seed.qualification,
    timelineEvents,
    lastMessageId: seed.lastMessageId,
  };
}

function getProspectStateSummary(state: ProspectUiState | undefined) {
  if (!state) {
    return {
      segment: "Pending",
      confidence: "n/a",
      aiMaturity: "—",
      lifecycleStage: "New",
      lastActivity: "No activity yet",
    };
  }
  const qualification = state.qualification;
  const hiringBrief = (state.enrichResult as any)?.hiring?.brief ?? null;
  return {
    segment: qualification?.segment ?? "Pending",
    confidence: qualification ? `${qualification.confidence.toFixed(2)}` : "n/a",
    aiMaturity: hiringBrief?.ai_maturity?.score ?? "—",
    lifecycleStage: state.lifecycleStage,
    lastActivity: formatTimestamp(state.lastActivity),
  };
}

function buildTimeline(state: ProspectUiState): TimelineEntry[] {
  const completed = new Set<TimelineEventType>();
  if (state.enrichResult) completed.add("enrichment_completed");
  if (state.qualification) completed.add("qualification_complete");
  if (state.lastMessageId) completed.add("email_sent");
  if (state.replyResult) completed.add("email_reply_received");
  if (state.lifecycleStage.toLowerCase().includes("booking link")) completed.add("booking_link_sent");
  if (state.bookingResult) completed.add("call_booked");

  return TIMELINE_TEMPLATE.map((item) => ({
    ...item,
    timestamp: state.timelineEvents[item.type] ?? state.lastActivity ?? null,
    complete: completed.has(item.type),
  }));
}

export default function Page() {
  const [backendUrl, setBackendUrl] = useState<string | null>(null);
  const [prospects, setProspects] = useState<ProspectSeed[]>([]);
  const [selectedProspectId, setSelectedProspectId] = useState<string | null>(null);
  const [prospectStates, setProspectStates] = useState<Record<string, ProspectUiState>>({});
  const [prospectsLoading, setProspectsLoading] = useState(true);

  async function loadProspects() {
    setProspectsLoading(true);
    try {
      const res = await fetch("/api/prospects", { cache: "no-store" });
      const data = await res.json().catch(() => ({}));
      const items = Array.isArray((data as any)?.prospects) ? (data as any).prospects : [];
      const mapped = items.map((item: ProspectApiRecord) => mapProspectRecord(item));
      setProspects(mapped);
      setSelectedProspectId((current) => (current && mapped.some((item) => item.id === current) ? current : mapped[0]?.id ?? null));
      setProspectStates((current) =>
        Object.fromEntries(mapped.map((item) => [item.id, createInitialProspectState(item, current[item.id])]))
      );
    } finally {
      setProspectsLoading(false);
    }
  }

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch("/api/config", { cache: "no-store" });
        const data = await res.json().catch(() => ({}));
        if (typeof data?.agent_api_url === "string") setBackendUrl(data.agent_api_url);
      } catch {
        // ignore
      }
      await loadProspects();
    })();
  }, []);

  const selectedProspect = useMemo(
    () => prospects.find((prospect) => prospect.id === selectedProspectId) ?? prospects[0] ?? null,
    [prospects, selectedProspectId]
  );

  const selectedState = selectedProspect ? prospectStates[selectedProspect.id] : null;
  const hiringBrief = ((selectedState?.enrichResult as any)?.hiring?.brief ?? null) as HiringBrief | null;
  const gapBrief = ((selectedState?.enrichResult as any)?.competitor_gap?.brief ?? null) as CompetitorGapBrief | null;
  const timeline = selectedState ? buildTimeline(selectedState) : [];

  function updateSelectedState(updater: (current: ProspectUiState) => ProspectUiState) {
    if (!selectedProspect) return;
    setProspectStates((current) => ({
      ...current,
      [selectedProspect.id]: updater(current[selectedProspect.id]),
    }));
  }

  async function refreshHubSpotStatus() {
    if (!selectedProspect || !selectedState) return;
    updateSelectedState((current) => ({ ...current, prospectActionLoading: "hubspot", actionsError: null }));
    try {
      const res = await fetch("/api/enrich-hubspot", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prospect_id: selectedProspect.id,
          email: selectedProspect.email,
          company_name: selectedProspect.company,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error((data as any)?.detail ?? (data as any)?.error ?? "CRM refresh failed");
      updateSelectedState((current) => ({
        ...current,
        hubspotResult: { status: res.status, data, timestamp: new Date().toISOString() },
        prospectActionLoading: null,
      }));
      await loadProspects();
    } catch (error: any) {
      updateSelectedState((current) => ({
        ...current,
        prospectActionLoading: null,
        actionsError: error?.message ?? "Unknown error",
      }));
    }
  }

  async function runEnrichment() {
    if (!selectedProspect || !selectedState) return;
    updateSelectedState((current) => ({ ...current, enrichmentLoading: true, enrichmentError: null, actionsError: null }));
    try {
      const res = await fetch("/api/enrich", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prospect_id: selectedProspect.id,
          company_name: selectedProspect.company,
          domain: selectedState.domain.trim() || null,
        }),
      });
      const data = (await res.json().catch(() => ({}))) as EnrichResult;
      if (!res.ok) throw new Error((data as any)?.detail ?? (data as any)?.error ?? "Enrichment failed");
      updateSelectedState((current) => ({
        ...current,
        enrichResult: {
          status: "ok",
          hiring: data.hiring,
          competitor_gap: data.competitor_gap,
          crm: (data as any).crm,
          prospect: (data as any).prospect,
        },
        enrichmentLoading: false,
      }));
      await loadProspects();
    } catch (error: any) {
      updateSelectedState((current) => ({
        ...current,
        enrichmentLoading: false,
        enrichmentError: error?.message ?? "Unknown error",
      }));
    }
  }

  async function sendOutreach() {
    if (!selectedProspect || !selectedState) return;
    updateSelectedState((current) => ({ ...current, prospectActionLoading: "send-email", actionsError: null }));
    try {
      const res = await fetch("/api/send-email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prospect_id: selectedProspect.id,
          to: [selectedProspect.email],
          subject: selectedState.emailSubject,
          text: selectedState.emailText,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error((data as any)?.detail ?? (data as any)?.error ?? "Outreach send failed");
      updateSelectedState((current) => ({
        ...current,
        sendResult: { status: res.status, data, timestamp: new Date().toISOString() },
        prospectActionLoading: null,
        lastMessageId: (data as any)?.result?.id ?? current.lastMessageId,
      }));
      await loadProspects();
    } catch (error: any) {
      updateSelectedState((current) => ({
        ...current,
        prospectActionLoading: null,
        actionsError: error?.message ?? "Unknown error",
      }));
    }
  }

  async function processReply() {
    if (!selectedProspect || !selectedState) return;
    updateSelectedState((current) => ({ ...current, prospectActionLoading: "reply", actionsError: null }));
    try {
      const res = await fetch("/api/process-reply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prospect_id: selectedProspect.id,
          message_id: selectedState.lastMessageId,
          subject: selectedState.emailSubject,
          text: selectedState.replyText,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error((data as any)?.detail ?? (data as any)?.error ?? "Reply processing failed");
      updateSelectedState((current) => ({
        ...current,
        replyResult: { status: res.status, data, timestamp: new Date().toISOString() },
        prospectActionLoading: null,
      }));
      await loadProspects();
    } catch (error: any) {
      updateSelectedState((current) => ({
        ...current,
        prospectActionLoading: null,
        actionsError: error?.message ?? "Unknown error",
      }));
    }
  }

  async function sendBookingLink() {
    if (!selectedProspect || !selectedState) return;
    updateSelectedState((current) => ({ ...current, prospectActionLoading: "booking-link", actionsError: null }));
    try {
      const res = await fetch("/api/send-booking-link", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prospect_id: selectedProspect.id }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error((data as any)?.detail ?? (data as any)?.error ?? "Booking link send failed");
      updateSelectedState((current) => ({
        ...current,
        prospectActionLoading: null,
      }));
      await loadProspects();
    } catch (error: any) {
      updateSelectedState((current) => ({
        ...current,
        prospectActionLoading: null,
        actionsError: error?.message ?? "Unknown error",
      }));
    }
  }

  async function syncBooking() {
    if (!selectedProspect || !selectedState) return;
    updateSelectedState((current) => ({ ...current, prospectActionLoading: "booking", actionsError: null }));
    try {
      const res = await fetch("/api/sync-booking", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prospect_id: selectedProspect.id,
          booking_id: selectedState.bookingId,
          status: "confirmed",
          title: `${selectedProspect.company} discovery call`,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error((data as any)?.detail ?? (data as any)?.error ?? "Booking sync failed");
      updateSelectedState((current) => ({
        ...current,
        bookingResult: { status: res.status, data, timestamp: new Date().toISOString() },
        prospectActionLoading: null,
      }));
      await loadProspects();
    } catch (error: any) {
      updateSelectedState((current) => ({
        ...current,
        prospectActionLoading: null,
        actionsError: error?.message ?? "Unknown error",
      }));
    }
  }

  const dashboardStats = useMemo(() => {
    const qualified = prospects.filter((prospect) => prospectStates[prospect.id]?.qualification).length;
    const activeThreads = prospects.filter((prospect) => prospectStates[prospect.id]?.lastMessageId).length;
    const booked = prospects.filter((prospect) => prospectStates[prospect.id]?.bookingResult).length;
    return { qualified, activeThreads, booked };
  }, [prospects, prospectStates]);

  if (!selectedProspect || !selectedState) {
    return (
      <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(242,181,76,0.18),_transparent_28%),linear-gradient(180deg,_rgba(255,255,255,0.92),_rgba(245,247,250,0.98))] px-4 py-6 md:px-8 md:py-8">
        <div className="mx-auto max-w-[1200px]">
          <Card className="border border-border/70 bg-white/90">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Users className="h-5 w-5 text-primary" />
                Prospects
              </CardTitle>
              <CardDescription>
                {prospectsLoading ? "Loading prospects from backend storage." : "No prospects found in backend storage."}
              </CardDescription>
            </CardHeader>
          </Card>
        </div>
      </main>
    );
  }

  const detailIdentity = {
    threadId: selectedState.threadId ?? buildThreadId(selectedProspect.company),
    crunchbaseId: hiringBrief?.company?.crunchbase_id ?? selectedProspect.crunchbaseId,
  };

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(242,181,76,0.18),_transparent_28%),linear-gradient(180deg,_rgba(255,255,255,0.92),_rgba(245,247,250,0.98))] px-4 py-6 md:px-8 md:py-8">
      <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6">
        <header className="overflow-hidden rounded-[32px] border border-border/70 bg-white/85 px-6 py-6 shadow-[0_20px_60px_rgba(15,23,42,0.08)] backdrop-blur md:px-8">
          <div className="flex flex-col gap-8 xl:flex-row xl:items-end xl:justify-between">
            <div className="max-w-3xl">
              <div className="inline-flex items-center gap-2 rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-medium uppercase tracking-[0.22em] text-amber-900">
                <Sparkles className="h-3.5 w-3.5" />
                Tenacious Pipeline Workspace
              </div>
              <h1 className="mt-4 font-headline text-4xl font-bold tracking-tight text-slate-950 md:text-5xl">
                Work live prospects from enrichment through booked discovery.
              </h1>
              <p className="mt-4 max-w-2xl text-base leading-7 text-slate-600">
                Prospects are loaded from backend storage, enrichment artifacts are generated by the pipeline, outreach is
                sent through MailerSend, and CRM plus booking state are synced back into HubSpot.
              </p>
            </div>
            <div className="grid gap-3 md:grid-cols-3 xl:w-[560px]">
              <MetricCard label="Qualified Prospects" value={String(dashboardStats.qualified)} hint="Enriched and ready for sales follow-up." />
              <MetricCard label="Active Threads" value={String(dashboardStats.activeThreads)} hint="Prospects with outbound email activity." />
              <MetricCard label="Calls Booked" value={String(dashboardStats.booked)} hint="Bookings synced into CRM." />
            </div>
          </div>
          <div className="mt-6 flex flex-wrap items-center gap-3 text-sm text-slate-600">
            <div className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1.5">
              <ArrowUpRight className="h-4 w-4 text-slate-500" />
              Backend URL
              <span className="rounded-full bg-white px-2 py-0.5 font-medium text-slate-900 shadow-sm">
                {backendUrl ?? "loading..."}
              </span>
            </div>
            <div className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1.5">
              <Flame className="h-4 w-4 text-slate-500" />
              Product flow
              <span className="font-medium text-slate-900">Prospect → Enrichment → Outreach → Reply → Booking Link → Booking Sync</span>
            </div>
          </div>
        </header>

        <div className="grid gap-6 xl:grid-cols-[420px_minmax(0,1fr)]">
          <Card className="overflow-hidden border border-border/70 bg-white/85 backdrop-blur">
            <CardHeader className="border-b border-border/70 pb-4">
              <CardTitle className="flex items-center gap-2">
                <Users className="h-5 w-5 text-primary" />
                Prospects
              </CardTitle>
              <CardDescription>Loaded from backend storage. Select a prospect to review signals and move the thread forward.</CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="min-w-full text-left text-sm">
                  <thead className="bg-slate-50/90 text-xs uppercase tracking-[0.18em] text-slate-500">
                    <tr>
                      <th className="px-5 py-4 font-medium">Prospect</th>
                      <th className="px-5 py-4 font-medium">Company</th>
                      <th className="px-5 py-4 font-medium">Email</th>
                      <th className="px-5 py-4 font-medium">Segment</th>
                      <th className="px-5 py-4 font-medium">Confidence</th>
                      <th className="px-5 py-4 font-medium">AI</th>
                      <th className="px-5 py-4 font-medium">Stage</th>
                      <th className="px-5 py-4 font-medium">Last activity</th>
                    </tr>
                  </thead>
                  <tbody>
                    {prospects.map((prospect) => {
                      const state = prospectStates[prospect.id];
                      const summary = getProspectStateSummary(state);
                      const active = prospect.id === selectedProspect.id;
                      return (
                        <tr
                          key={prospect.id}
                          className={cn("cursor-pointer border-t border-border/60 transition-colors hover:bg-amber-50/40", active && "bg-amber-50/70")}
                          onClick={() => setSelectedProspectId(prospect.id)}
                        >
                          <td className="px-5 py-4 align-top font-semibold text-slate-900">{prospect.prospectName}</td>
                          <td className="px-5 py-4 align-top text-slate-600">{prospect.company}</td>
                          <td className="px-5 py-4 align-top text-slate-600">{prospect.email}</td>
                          <td className="px-5 py-4 align-top">
                            <Badge className="border-none bg-slate-100 text-slate-700">{summary.segment}</Badge>
                          </td>
                          <td className="px-5 py-4 align-top text-slate-600">{summary.confidence}</td>
                          <td className="px-5 py-4 align-top text-slate-900">{summary.aiMaturity}</td>
                          <td className="px-5 py-4 align-top">
                            <StatusBadge value={summary.lifecycleStage} />
                          </td>
                          <td className="px-5 py-4 align-top text-xs text-slate-500">{summary.lastActivity}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          <div className="grid gap-6">
            <div className="grid gap-6 2xl:grid-cols-[1.1fr_0.9fr]">
              <Card className="border border-border/70 bg-white/90">
                <CardHeader className="border-b border-border/60 pb-4">
                  <CardTitle className="flex items-center gap-2">
                    <Building2 className="h-5 w-5 text-primary" />
                    Prospect Detail
                  </CardTitle>
                  <CardDescription>Identity, account context, and thread continuity for the current prospect.</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-4 md:grid-cols-2">
                  <div className="rounded-[24px] border border-border/70 bg-slate-50/80 p-5">
                    <div className="text-xs uppercase tracking-[0.24em] text-muted-foreground">Identity</div>
                    <div className="mt-4 text-2xl font-semibold text-slate-950">{selectedProspect.prospectName}</div>
                    <div className="mt-2 text-sm text-slate-600">{selectedProspect.company}</div>
                    <div className="mt-4 space-y-3 text-sm">
                      <DetailRow label="Email" value={selectedProspect.email} />
                      <DetailRow label="Thread ID" value={detailIdentity.threadId} />
                      <DetailRow label="Crunchbase ID" value={detailIdentity.crunchbaseId} />
                    </div>
                  </div>
                  <div className="rounded-[24px] border border-border/70 bg-white p-5">
                    <div className="text-xs uppercase tracking-[0.24em] text-muted-foreground">Commercial Snapshot</div>
                    <div className="mt-4 space-y-3 text-sm">
                      <DetailRow label="Lifecycle stage" value={<StatusBadge value={selectedState.lifecycleStage} />} />
                      <DetailRow
                        label="ICP segment"
                        value={<Badge className="border-none bg-slate-100 text-slate-700">{selectedState.qualification?.segment ?? "Pending"}</Badge>}
                      />
                      <DetailRow label="Qualification confidence" value={selectedState.qualification ? selectedState.qualification.confidence.toFixed(2) : "n/a"} />
                      <DetailRow label="Pitch angle" value={selectedState.qualification?.pitchAngle ?? "exploratory_generic"} />
                      <DetailRow label="Last activity" value={formatTimestamp(selectedState.lastActivity)} />
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card className="border border-border/70 bg-white/90">
                <CardHeader className="border-b border-border/60 pb-4">
                  <CardTitle className="flex items-center gap-2">
                    <Send className="h-5 w-5 text-primary" />
                    Prospect Actions
                  </CardTitle>
                  <CardDescription>Product actions that use the live backend flow, with MailerSend as the primary email channel.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-5">
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <label className="text-sm text-muted-foreground">Domain</label>
                      <Input value={selectedState.domain} onChange={(event) => updateSelectedState((current) => ({ ...current, domain: event.target.value }))} />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm text-muted-foreground">Peer count</label>
                      <Input
                        type="number"
                        min={5}
                        max={10}
                        value={selectedState.peersLimit}
                        onChange={(event) => updateSelectedState((current) => ({ ...current, peersLimit: Number(event.target.value || 10) }))}
                      />
                    </div>
                  </div>

                  <div className="flex items-center justify-between rounded-[22px] border border-border/70 bg-slate-50/70 px-4 py-3">
                    <div>
                      <div className="text-sm font-medium text-slate-900">Use Playwright for job-post capture</div>
                      <div className="text-xs text-slate-500">Useful when the careers page requires client-side rendering.</div>
                    </div>
                    <Switch checked={selectedState.usePlaywright} onCheckedChange={(checked) => updateSelectedState((current) => ({ ...current, usePlaywright: checked }))} />
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm text-muted-foreground">Outreach subject</label>
                    <Input value={selectedState.emailSubject} onChange={(event) => updateSelectedState((current) => ({ ...current, emailSubject: event.target.value }))} />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm text-muted-foreground">Outreach body</label>
                    <textarea
                      value={selectedState.emailText}
                      onChange={(event) => updateSelectedState((current) => ({ ...current, emailText: event.target.value }))}
                      className="min-h-[96px] w-full rounded-[22px] border border-border/70 bg-white px-4 py-3 text-sm shadow-sm outline-none ring-0 transition focus:border-ring"
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm text-muted-foreground">Reply text for emergency manual fallback</label>
                    <textarea
                      value={selectedState.replyText}
                      onChange={(event) => updateSelectedState((current) => ({ ...current, replyText: event.target.value }))}
                      className="min-h-[80px] w-full rounded-[22px] border border-border/70 bg-white px-4 py-3 text-sm shadow-sm outline-none ring-0 transition focus:border-ring"
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm text-muted-foreground">Booking ID</label>
                    <Input value={selectedState.bookingId} onChange={(event) => updateSelectedState((current) => ({ ...current, bookingId: event.target.value }))} />
                  </div>

                  <div className="grid gap-3 md:grid-cols-2">
                    <Button type="button" className="gap-2" onClick={runEnrichment} disabled={selectedState.enrichmentLoading}>
                      {selectedState.enrichmentLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                      Run Enrichment
                    </Button>
                    <Button type="button" variant="secondary" className="gap-2" onClick={sendOutreach} disabled={selectedState.prospectActionLoading === "send-email"}>
                      {selectedState.prospectActionLoading === "send-email" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Mail className="h-4 w-4" />}
                      Send email (MailerSend)
                    </Button>
                    <Button type="button" variant="secondary" className="gap-2" onClick={processReply} disabled={selectedState.prospectActionLoading === "reply"}>
                      {selectedState.prospectActionLoading === "reply" ? <Loader2 className="h-4 w-4 animate-spin" /> : <MessageSquareReply className="h-4 w-4" />}
                      Process Reply
                    </Button>
                    <Button type="button" variant="secondary" className="gap-2" onClick={sendBookingLink} disabled={selectedState.prospectActionLoading === "booking-link"}>
                      {selectedState.prospectActionLoading === "booking-link" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                      Send Booking Link
                    </Button>
                    <Button type="button" variant="secondary" className="gap-2" onClick={syncBooking} disabled={selectedState.prospectActionLoading === "booking"}>
                      {selectedState.prospectActionLoading === "booking" ? <Loader2 className="h-4 w-4 animate-spin" /> : <CalendarCheck2 className="h-4 w-4" />}
                      Sync Booking
                    </Button>
                    <Button type="button" variant="secondary" className="gap-2" onClick={refreshHubSpotStatus} disabled={selectedState.prospectActionLoading === "hubspot"}>
                      {selectedState.prospectActionLoading === "hubspot" ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                      Refresh CRM
                    </Button>
                  </div>

                  <div className="grid gap-3 md:grid-cols-2">
                    <div className="rounded-[22px] border border-border/70 bg-slate-50/70 p-4">
                      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">Last message ID</div>
                      <div className="mt-2 break-all text-sm font-semibold text-slate-900">{selectedState.lastMessageId ?? "Not sent yet"}</div>
                    </div>
                    <div className="rounded-[22px] border border-border/70 bg-slate-50/70 p-4">
                      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">Thread continuity</div>
                      <div className="mt-2 text-sm font-semibold text-slate-900">{detailIdentity.threadId}</div>
                    </div>
                  </div>

                  {selectedState.enrichmentError ? (
                    <div className="rounded-[22px] border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
                      <div className="font-semibold">Enrichment Error</div>
                      <div className="mt-1">{selectedState.enrichmentError}</div>
                    </div>
                  ) : null}
                  {selectedState.actionsError ? (
                    <div className="rounded-[22px] border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
                      <div className="font-semibold">Action Error</div>
                      <div className="mt-1">{selectedState.actionsError}</div>
                    </div>
                  ) : null}
                </CardContent>
              </Card>
            </div>

            <div className="grid gap-6 2xl:grid-cols-[1.05fr_0.95fr]">
              <Card className="border border-border/70 bg-white/90">
                <CardHeader className="border-b border-border/60 pb-4">
                  <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                    <div>
                      <CardTitle className="flex items-center gap-2">
                        <Database className="h-5 w-5 text-primary" />
                        Hiring Signal Brief
                      </CardTitle>
                      <CardDescription>Artifact-backed signal cards, with raw JSON available for validation.</CardDescription>
                    </div>
                    <div className="flex items-center gap-3 rounded-full border border-border/70 bg-slate-50 px-4 py-2">
                      <span className="text-sm text-slate-600">View Raw JSON</span>
                      <Switch checked={selectedState.showRawJson} onCheckedChange={(checked) => updateSelectedState((current) => ({ ...current, showRawJson: checked }))} />
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-5">
                  {hiringBrief ? (
                    <>
                      <div className="grid gap-4 xl:grid-cols-2">
                        <SignalCard title="Funding signal" confidence={hiringBrief?.funding?._confidence}>
                          <div>Funded: {String(hiringBrief?.funding?.funded)}</div>
                          <div>Round: {String(hiringBrief?.funding?.round_type ?? hiringBrief?.funding?.last_funding_type ?? "n/a")}</div>
                          <div>Funding recency: {String(hiringBrief?.funding?.days_ago ?? "n/a")} days ago</div>
                        </SignalCard>
                        <SignalCard title="Job-post velocity" confidence={hiringBrief?.jobs?._confidence}>
                          <div>Engineering roles: {String(hiringBrief?.jobs?.engineering_roles ?? 0)}</div>
                          <div>AI/ML roles: {String(hiringBrief?.jobs?.ai_ml_roles ?? 0)}</div>
                          <div>Velocity (60d): {String(hiringBrief?.jobs?.velocity_60d ?? 0)}</div>
                        </SignalCard>
                        <SignalCard title="Layoffs" confidence={hiringBrief?.layoffs?._confidence}>
                          <div>Detected: {String(hiringBrief?.layoffs?.had_layoff ?? false)}</div>
                          <div>Recency: {String(hiringBrief?.layoffs?.days_ago ?? "n/a")} days ago</div>
                        </SignalCard>
                        <SignalCard title="Leadership" confidence={hiringBrief?.leadership_change?._confidence}>
                          <div>Detected: {String(hiringBrief?.leadership_change?.new_leader_detected ?? false)}</div>
                          <div>Role: {String(hiringBrief?.leadership_change?.role ?? "n/a")}</div>
                        </SignalCard>
                      </div>

                      <div className="rounded-[24px] border border-border/70 bg-slate-50/70 p-5">
                        <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                          <BrainCircuit className="h-4 w-4 text-primary" />
                          AI maturity
                        </div>
                        <div className="mt-4 grid gap-4 md:grid-cols-3">
                          <div className="rounded-[20px] bg-white p-4">
                            <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Score</div>
                            <div className="mt-2 text-3xl font-semibold text-slate-950">{String(hiringBrief?.ai_maturity?.score ?? 0)}</div>
                          </div>
                          <div className="rounded-[20px] bg-white p-4">
                            <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Confidence</div>
                            <div className="mt-2">
                              <ConfidenceBadge value={hiringBrief?.ai_maturity?._confidence} />
                            </div>
                          </div>
                          <div className="rounded-[20px] bg-white p-4">
                            <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Tech stack</div>
                            <div className="mt-2 text-sm text-slate-700">{(hiringBrief?.tech_stack?.technologies ?? []).join(", ") || "n/a"}</div>
                          </div>
                        </div>
                      </div>

                      {selectedState.showRawJson ? (
                        <details open className="rounded-[24px] border border-border/80 bg-slate-950 p-5 text-slate-100">
                          <summary className="cursor-pointer text-sm font-medium">hiring_signal_brief.json</summary>
                          <pre className="mt-4 overflow-auto text-xs">{JSON.stringify(hiringBrief, null, 2)}</pre>
                        </details>
                      ) : null}
                    </>
                  ) : (
                    <div className="rounded-[24px] border border-dashed border-border/80 bg-slate-50/70 p-8 text-sm text-slate-500">
                      Run enrichment to generate the current hiring signal brief artifact for this prospect.
                    </div>
                  )}
                </CardContent>
              </Card>

              <Card className="border border-border/70 bg-white/90">
                <CardHeader className="border-b border-border/60 pb-4">
                  <CardTitle className="flex items-center gap-2">
                    <GitCompare className="h-5 w-5 text-primary" />
                    Competitor Gap Brief
                  </CardTitle>
                  <CardDescription>Peer context, percentile ranking, and actionable gaps framed for live sales conversations.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-5">
                  {gapBrief ? (
                    <>
                      <div className="grid gap-4 md:grid-cols-2">
                        <div className="rounded-[24px] border border-border/80 bg-slate-950 p-5 text-white">
                          <div className="text-xs uppercase tracking-[0.2em] text-slate-400">Prospect percentile</div>
                          <div className="mt-3 text-5xl font-semibold">{String(gapBrief?.prospect_percentile ?? 0)}th</div>
                          <div className="mt-2 text-sm text-slate-300">Positioned against peers with overlapping industry and size signals.</div>
                        </div>
                        <div className="rounded-[24px] border border-border/80 bg-slate-50/80 p-5">
                          <div className="text-xs uppercase tracking-[0.2em] text-slate-500">Peer set</div>
                          <div className="mt-3 text-3xl font-semibold text-slate-900">{String(gapBrief?.meta?.peer_count ?? gapBrief?.peers?.length ?? 0)}</div>
                          <div className="mt-2 text-sm text-slate-600">Comparable companies used to frame the current gap brief.</div>
                        </div>
                      </div>

                      <div>
                        <div className="text-sm font-semibold text-slate-900">Peer companies</div>
                        <div className="mt-4 grid gap-3">
                          {(gapBrief?.peers ?? []).slice(0, 10).map((peer: any, index: number) => (
                            <div key={`${peer?.name ?? "peer"}-${index}`} className="grid gap-3 rounded-[20px] border border-border/70 bg-white p-4 md:grid-cols-[1fr_auto_auto] md:items-center">
                              <div>
                                <div className="font-medium text-slate-900">{String(peer?.name ?? `Peer ${index + 1}`)}</div>
                                <div className="mt-1 text-sm text-slate-500">{(peer?.industries ?? []).join(", ") || "Industry not available"}</div>
                              </div>
                              <div className="text-sm text-slate-600">Employees: {String(peer?.num_employees ?? "n/a")}</div>
                              <Badge className="border-none bg-slate-100 text-slate-700">AI maturity {String(peer?.ai_maturity?.score ?? 0)}</Badge>
                            </div>
                          ))}
                        </div>
                      </div>

                      <div>
                        <div className="text-sm font-semibold text-slate-900">Specific gaps</div>
                        <div className="mt-4 grid gap-3">
                          {(gapBrief?.gaps ?? []).slice(0, 3).map((gap: any, index: number) => (
                            <div key={`${gap?.gap ?? "gap"}-${index}`} className="rounded-[22px] border border-border/70 bg-slate-50/80 p-5">
                              <div className="flex items-center justify-between gap-3">
                                <div className="text-base font-semibold text-slate-900">{String(gap?.gap ?? `Gap ${index + 1}`).replace(/_/g, " ")}</div>
                                <ConfidenceBadge value={gap?.confidence} />
                              </div>
                              <div className="mt-3 text-sm text-slate-600">Top-quartile prevalence: {String(gap?.evidence?.top_quartile_prevalence ?? "n/a")}</div>
                              <div className="mt-1 text-sm text-slate-600">Sample peers: {(gap?.evidence?.sample_peers ?? []).join(", ") || "n/a"}</div>
                              <div className="mt-4 rounded-[18px] bg-white p-4 text-sm text-slate-700">
                                <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Pitch hook</div>
                                <div className="mt-2 leading-6">{String(gap?.pitch_hook ?? "No pitch hook available")}</div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>

                      {selectedState.showRawJson ? (
                        <details open className="rounded-[24px] border border-border/80 bg-slate-950 p-5 text-slate-100">
                          <summary className="cursor-pointer text-sm font-medium">competitor_gap_brief.json</summary>
                          <pre className="mt-4 overflow-auto text-xs">{JSON.stringify(gapBrief, null, 2)}</pre>
                        </details>
                      ) : null}
                    </>
                  ) : (
                    <div className="rounded-[24px] border border-dashed border-border/80 bg-slate-50/70 p-8 text-sm text-slate-500">
                      Run enrichment to generate the current competitor gap artifact for this prospect.
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>

            <div className="grid gap-6 2xl:grid-cols-[0.92fr_1.08fr]">
              <Card className="border border-border/70 bg-white/90">
                <CardHeader className="border-b border-border/60 pb-4">
                  <CardTitle className="flex items-center gap-2">
                    <Flame className="h-5 w-5 text-primary" />
                    Conversion Timeline
                  </CardTitle>
                  <CardDescription>Track the full lifecycle from enrichment to booking sync on one screen.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {timeline.map((event) => (
                    <div
                      key={event.type}
                      className={cn("rounded-[24px] border p-5 transition-colors", event.complete ? "border-emerald-200 bg-emerald-50/80" : "border-border/70 bg-slate-50/70")}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <div className="text-sm font-semibold text-slate-900">{event.title}</div>
                          <div className="mt-2 text-sm leading-6 text-slate-600">{event.description}</div>
                        </div>
                        <Badge className={cn("border-none", event.complete ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-700")}>
                          {event.complete ? "complete" : "pending"}
                        </Badge>
                      </div>
                      <div className="mt-3 text-xs uppercase tracking-[0.18em] text-slate-500">{event.complete ? formatTimestamp(event.timestamp) : "Waiting"}</div>
                    </div>
                  ))}
                </CardContent>
              </Card>

              <Card className="border border-border/70 bg-white/90">
                <CardHeader className="border-b border-border/60 pb-4">
                  <CardTitle className="flex items-center gap-2">
                    <Mail className="h-5 w-5 text-primary" />
                    Action Status
                  </CardTitle>
                  <CardDescription>Surface the concrete identifiers and CRM state a sales operator needs.</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-4">
                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                    <div className="rounded-[22px] border border-border/70 bg-slate-50/70 p-4">
                      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">Thread ID</div>
                      <div className="mt-2 text-sm font-semibold text-slate-900">{detailIdentity.threadId}</div>
                    </div>
                    <div className="rounded-[22px] border border-border/70 bg-slate-50/70 p-4">
                      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">Last message ID</div>
                      <div className="mt-2 break-all text-sm font-semibold text-slate-900">{selectedState.lastMessageId ?? "n/a"}</div>
                    </div>
                    <div className="rounded-[22px] border border-border/70 bg-slate-50/70 p-4">
                      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">Backend</div>
                      <div className="mt-2 text-sm font-semibold text-slate-900">{backendUrl ?? "loading..."}</div>
                    </div>
                  </div>

                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="rounded-[24px] border border-border/70 bg-white p-5">
                      <div className="text-sm font-semibold text-slate-900">HubSpot sync</div>
                      <div className="mt-2 text-sm text-slate-600">{selectedState.hubspotResult ? "Latest CRM sync completed." : "No CRM sync recorded yet."}</div>
                      <div className="mt-4 space-y-2 text-sm text-slate-600">
                        <div>Status: {selectedState.hubspotResult?.status ?? "n/a"}</div>
                        <div>Contact ID: {selectedState.hubspotResult?.data?.hubspot?.id ?? selectedState.hubspotResult?.data?.crm?.hubspot?.id ?? "n/a"}</div>
                        <div>Segment: {selectedState.qualification?.segment ?? "Pending"}</div>
                        <div>Thread ID: {detailIdentity.threadId}</div>
                      </div>
                    </div>
                    <div className="rounded-[24px] border border-border/70 bg-white p-5">
                      <div className="text-sm font-semibold text-slate-900">Booking flow</div>
                      <div className="mt-2 text-sm text-slate-600">
                        {selectedState.bookingResult ? "Booking sync is recorded in CRM." : "Send the booking link, let the prospect book in Cal.com, then sync the booking."}
                      </div>
                      <div className="mt-4 space-y-2 text-sm text-slate-600">
                        <div>Booking ID: {selectedState.bookingId}</div>
                        <div>Booking status: {selectedState.bookingResult?.data?.booking_status ?? "Pending"}</div>
                        <div>Last activity: {formatTimestamp(selectedState.lastActivity)}</div>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
