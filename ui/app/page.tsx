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

type EmailSource = {
  used_enrichment_data?: boolean;
  used_icp_segment?: boolean;
  used_ai_maturity_score?: boolean;
  used_competitor_gap_brief?: boolean;
  used_style_guide?: boolean;
  used_email_sequences?: boolean;
  used_case_studies?: boolean;
  signals_used?: string[];
  seed_files_loaded?: Record<string, string | null>;
  fallback_reason?: string | null;
  pitch_language_hint?: string | null;
  generation_mode?: "signal_grounded" | "fallback_generic" | string | null;
} | null;

type EmailGenerationMetadata = {
  generated_at?: string | null;
  prospect_id?: string | null;
  thread_id?: string | null;
  icp_segment?: string | null;
  icp_confidence?: number | null;
  signals_used?: string[];
  generation_mode?: "signal_grounded" | "fallback_generic" | string | null;
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
  last_reply_message_id?: string | null;
  last_reply_subject?: string | null;
  last_reply_text?: string | null;
  last_reply_html?: string | null;
  last_reply_received_at?: string | null;
  last_reply_source?: string | null;
  reply_intent?: string | null;
  reply_intent_confidence?: number | null;
  reply_intent_reason?: string | null;
  reply_next_action?: Record<string, any> | null;
  last_delivery_event?: string | null;
  last_delivery_at?: string | null;
  email_source?: EmailSource;
  email_warning?: string | null;
  email_generated?: boolean | null;
  email_generated_at?: string | null;
  email_generation_metadata?: EmailGenerationMetadata;
  email_approved?: boolean | null;
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
  booking_artifact?: BookingArtifact | null;
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
  lastReplyMessageId: string | null;
  lastReplySubject: string | null;
  lastReplyText: string | null;
  lastReplyHtml: string | null;
  lastReplyReceivedAt: string | null;
  lastReplySource: string | null;
  replyIntent: string | null;
  replyIntentConfidence: number | null;
  replyIntentReason: string | null;
  replyNextAction: Record<string, any> | null;
  lastDeliveryEvent: string | null;
  lastDeliveryAt: string | null;
  emailSource: EmailSource;
  emailWarning: string | null;
  emailGenerated: boolean;
  emailGeneratedAt: string | null;
  emailGenerationMetadata: EmailGenerationMetadata;
  emailApproved: boolean;
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
  bookingArtifact: BookingArtifact | null;
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
  | "email_generated"
  | "email_approved"
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

type BookingArtifact = {
  status: string;
  event_type: string;
  attendee_name: string;
  attendee_email: string;
  start_time: string | null;
  timezone: string;
  calcom_booking_id: string;
  calcom_uid: string | null;
  synced_at: string;
  raw_calcom_data: any;
};

type ProspectUiState = {
  domain: string;
  usePlaywright: boolean;
  peersLimit: number;
  lastReplyMessageId: string | null;
  lastReplySubject: string | null;
  lastReplyText: string | null;
  lastReplyHtml: string | null;
  lastReplyReceivedAt: string | null;
  lastReplySource: string | null;
  replyIntent: string | null;
  replyIntentConfidence: number | null;
  replyIntentReason: string | null;
  replyNextAction: Record<string, any> | null;
  lastDeliveryEvent: string | null;
  lastDeliveryAt: string | null;
  emailSource: EmailSource;
  emailWarning: string | null;
  emailGenerated: boolean;
  emailGeneratedAt: string | null;
  emailGenerationMetadata: EmailGenerationMetadata;
  emailApproved: boolean;
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
  bookingArtifact: BookingArtifact | null;
};

type ProspectCreateForm = {
  company: string;
  prospectName: string;
  email: string;
  domain: string;
  phone: string;
  peersLimit: number;
  usePlaywright: boolean;
};

type CompanySuggestion = {
  name: string;
  id?: string | null;
  domain?: string | null;
  country?: string | null;
  employee_count?: number | null;
  industries?: string[];
  description?: string | null;
};

const EMPTY_PROSPECT_FORM: ProspectCreateForm = {
  company: "",
  prospectName: "",
  email: "",
  domain: "",
  phone: "",
  peersLimit: 10,
  usePlaywright: false,
};

function normalizePeersLimit(value: number) {
  if (!Number.isFinite(value)) return 10;
  return Math.max(1, Math.min(25, Math.round(value)));
}

function validateProspectForm(form: ProspectCreateForm) {
  if (!form.company.trim()) return "Company is required.";
  if (!form.prospectName.trim()) return "Prospect name is required.";
  if (!Number.isInteger(form.peersLimit) || form.peersLimit < 1 || form.peersLimit > 25) {
    return "Peer count must be between 1 and 25.";
  }
  return null;
}

const TIMELINE_TEMPLATE: Array<Pick<TimelineEntry, "type" | "title" | "description">> = [
  {
    type: "enrichment_completed",
    title: "Enrichment completed",
    description: "Signal brief, competitor gap, and CRM enrichment are ready for review.",
  },
  {
    type: "email_generated",
    title: "Email generated",
    description: "Draft email has been generated from enrichment, ICP classification, and seed assets.",
  },
  {
    type: "email_approved",
    title: "Email approved",
    description: "An operator has approved the generated email for live send.",
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
    lastReplyMessageId: record.last_reply_message_id ?? null,
    lastReplySubject: record.last_reply_subject ?? null,
    lastReplyText: record.last_reply_text ?? null,
    lastReplyHtml: record.last_reply_html ?? null,
    lastReplyReceivedAt: record.last_reply_received_at ?? null,
    lastReplySource: record.last_reply_source ?? null,
    replyIntent: record.reply_intent ?? null,
    replyIntentConfidence: typeof record.reply_intent_confidence === "number" ? record.reply_intent_confidence : null,
    replyIntentReason: record.reply_intent_reason ?? null,
    replyNextAction: record.reply_next_action ?? null,
    lastDeliveryEvent: record.last_delivery_event ?? null,
    lastDeliveryAt: record.last_delivery_at ?? null,
    emailSource: record.email_source ?? null,
    emailWarning: record.email_warning ?? null,
    emailGenerated: Boolean(record.email_generated),
    emailGeneratedAt: record.email_generated_at ?? null,
    emailGenerationMetadata: record.email_generation_metadata ?? null,
    emailApproved: Boolean(record.email_approved),
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
    bookingArtifact: record.booking_artifact ?? null,
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

function BooleanBadge({ value }: { value: boolean }) {
  return (
    <Badge className={cn("border-none", value ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-700")}>
      {value ? "yes" : "no"}
    </Badge>
  );
}

function BookingArtifactCard({ artifact }: { artifact: BookingArtifact }) {
  const formatDate = (dateString: string | null) => {
    if (!dateString) return "Not set";
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric", 
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
      timeZoneName: "short",
    }).format(new Date(dateString));
  };

  return (
    <div className="rounded-[24px] border border-emerald-200 bg-emerald-50/80 p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-100 text-emerald-600">
            ✅
          </div>
          <div className="text-sm font-semibold text-emerald-900">Booking confirmed</div>
        </div>
        <Badge className="border-none bg-emerald-100 text-emerald-800">confirmed</Badge>
      </div>
      
      <div className="mt-4 space-y-3 text-sm text-emerald-800">
        <div className="font-medium">{artifact.event_type}</div>
        
        <div className="grid gap-2 md:grid-cols-2">
          <div>
            <div className="text-xs uppercase tracking-[0.18em] text-emerald-600">Attendee</div>
            <div className="mt-1 font-medium">{artifact.attendee_name}</div>
            <div className="text-emerald-700">{artifact.attendee_email}</div>
          </div>
          
          <div>
            <div className="text-xs uppercase tracking-[0.18em] text-emerald-600">Date/Time</div>
            <div className="mt-1 font-medium">{formatDate(artifact.start_time)}</div>
            <div className="text-emerald-700">Timezone: {artifact.timezone}</div>
          </div>
        </div>
        
        <div className="grid gap-2 md:grid-cols-2">
          <div>
            <div className="text-xs uppercase tracking-[0.18em] text-emerald-600">Cal.com Booking ID</div>
            <div className="mt-1 font-mono text-xs">{artifact.calcom_booking_id}</div>
          </div>
          
          <div>
            <div className="text-xs uppercase tracking-[0.18em] text-emerald-600">Synced at</div>
            <div className="mt-1 font-medium">{formatDate(artifact.synced_at)}</div>
          </div>
        </div>
      </div>
    </div>
  );
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

function LaunchpadCard({
  form,
  loading,
  error,
  suggestions,
  suggestionsLoading,
  onChange,
  onPickCompany,
  onSubmit,
}: {
  form: ProspectCreateForm;
  loading: boolean;
  error: string | null;
  suggestions: CompanySuggestion[];
  suggestionsLoading: boolean;
  onChange: <K extends keyof ProspectCreateForm>(field: K, value: ProspectCreateForm[K]) => void;
  onPickCompany: (company: CompanySuggestion) => void;
  onSubmit: () => void;
}) {
  return (
    <Card className="border border-amber-200 bg-[linear-gradient(135deg,rgba(255,248,235,0.98),rgba(255,255,255,0.96))] shadow-[0_20px_60px_rgba(217,119,6,0.14)]">
      <CardHeader className="border-b border-amber-200/70 pb-4">
        <div className="inline-flex w-fit items-center gap-2 rounded-full bg-amber-100 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.22em] text-amber-900">
          <Sparkles className="h-3.5 w-3.5" />
          New Prospect
        </div>
        <CardTitle className="mt-3 text-2xl text-slate-950">Launch a live company into the pipeline</CardTitle>
        <CardDescription>
          Create the prospect record once, then drive enrichment, ICP, email generation, approval, send, and nurture from the UI.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5 p-5">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <label className="text-sm text-muted-foreground">Company</label>
            <Input value={form.company} onChange={(event) => onChange("company", event.target.value)} placeholder="SnapTrade" />
            <div className="rounded-[18px] border border-border/70 bg-white/80 p-2">
              <div className="mb-2 text-[11px] uppercase tracking-[0.18em] text-slate-500">
                {suggestionsLoading ? "Searching local company list..." : "Choose from local Crunchbase sample"}
              </div>
              <div className="grid gap-2">
                {suggestions.slice(0, 5).map((company) => (
                  <button
                    key={`${company.name}-${company.id ?? "company"}`}
                    type="button"
                    className="rounded-[14px] border border-border/70 bg-slate-50/70 px-3 py-2 text-left transition-colors hover:bg-amber-50"
                    onClick={() => onPickCompany(company)}
                  >
                    <div className="text-sm font-medium text-slate-900">{company.name}</div>
                    <div className="text-xs text-slate-500">
                      {company.domain ?? "no domain"}{company.industries && company.industries.length ? ` · ${company.industries.slice(0, 2).join(", ")}` : ""}
                    </div>
                  </button>
                ))}
                {!suggestionsLoading && suggestions.length === 0 ? (
                  <div className="px-2 py-1 text-xs text-slate-500">No matches yet. Type part of the company name.</div>
                ) : null}
              </div>
            </div>
          </div>
          <div className="space-y-2">
            <label className="text-sm text-muted-foreground">Prospect name</label>
            <Input value={form.prospectName} onChange={(event) => onChange("prospectName", event.target.value)} placeholder="Bethel Yohannes" />
          </div>
          <div className="space-y-2">
            <label className="text-sm text-muted-foreground">Email</label>
            <Input value={form.email} onChange={(event) => onChange("email", event.target.value)} placeholder="Optional: auto-generated if empty" />
          </div>
          <div className="space-y-2">
            <label className="text-sm text-muted-foreground">Domain</label>
            <Input value={form.domain} onChange={(event) => onChange("domain", event.target.value)} placeholder="snaptrade.com" />
          </div>
          <div className="space-y-2">
            <label className="text-sm text-muted-foreground">Phone</label>
            <Input value={form.phone} onChange={(event) => onChange("phone", event.target.value)} placeholder="Optional: synthetic phone if empty" />
          </div>
          <div className="space-y-2">
            <label className="text-sm text-muted-foreground">Peer count</label>
            <Input
              type="number"
              min={1}
              max={25}
              value={form.peersLimit}
              onChange={(event) => onChange("peersLimit", normalizePeersLimit(Number(event.target.value || 10)))}
            />
          </div>
        </div>
        <div className="flex items-center justify-between rounded-[22px] border border-amber-200/70 bg-white/75 px-4 py-3">
          <div>
            <div className="text-sm font-medium text-slate-900">Use Playwright for job-post capture</div>
            <div className="text-xs text-slate-500">Enable this only when the target careers page needs client-side rendering.</div>
          </div>
          <Switch checked={form.usePlaywright} onCheckedChange={(checked) => onChange("usePlaywright", checked)} />
        </div>
        {error ? (
          <div className="rounded-[18px] border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</div>
        ) : null}
        <div className="flex flex-wrap items-center gap-3">
          <Button type="button" className="gap-2" onClick={onSubmit} disabled={loading}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Building2 className="h-4 w-4" />}
            Create Prospect
          </Button>
          <div className="text-sm text-slate-600">Recommended first demo record: `SnapTrade`, `snaptrade.com`, your own inbox email.</div>
        </div>
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
    lastReplyMessageId: seed.lastReplyMessageId ?? existing?.lastReplyMessageId ?? null,
    lastReplySubject: seed.lastReplySubject ?? existing?.lastReplySubject ?? null,
    lastReplyText: seed.lastReplyText ?? existing?.lastReplyText ?? null,
    lastReplyHtml: seed.lastReplyHtml ?? existing?.lastReplyHtml ?? null,
    lastReplyReceivedAt: seed.lastReplyReceivedAt ?? existing?.lastReplyReceivedAt ?? null,
    lastReplySource: seed.lastReplySource ?? existing?.lastReplySource ?? null,
    replyIntent: seed.replyIntent ?? existing?.replyIntent ?? null,
    replyIntentConfidence: seed.replyIntentConfidence ?? existing?.replyIntentConfidence ?? null,
    replyIntentReason: seed.replyIntentReason ?? existing?.replyIntentReason ?? null,
    replyNextAction: seed.replyNextAction ?? existing?.replyNextAction ?? null,
    lastDeliveryEvent: seed.lastDeliveryEvent ?? existing?.lastDeliveryEvent ?? null,
    lastDeliveryAt: seed.lastDeliveryAt ?? existing?.lastDeliveryAt ?? null,
    emailSource: seed.emailSource ?? existing?.emailSource ?? null,
    emailWarning: seed.emailWarning ?? existing?.emailWarning ?? null,
    emailGenerated: seed.emailGenerated ?? existing?.emailGenerated ?? false,
    emailGeneratedAt: seed.emailGeneratedAt ?? existing?.emailGeneratedAt ?? null,
    emailGenerationMetadata: seed.emailGenerationMetadata ?? existing?.emailGenerationMetadata ?? null,
    emailApproved: seed.emailApproved ?? existing?.emailApproved ?? false,
    emailSubject: existing?.emailSubject ?? seed.emailSubject,
    emailText: existing?.emailText ?? seed.emailText,
    replyText: existing?.replyText ?? seed.replyText,
    bookingId: existing?.bookingId ?? seed.bookingId,
    enrichResult: buildEnrichResult(seed) ?? existing?.enrichResult ?? null,
    hubspotResult: seed.hubspot ? { status: 200, data: { hubspot: seed.hubspot }, timestamp: seed.lastActivity } : existing?.hubspotResult ?? null,
    sendResult: seed.lastMessageId ? { data: { result: { id: seed.lastMessageId } }, timestamp: seed.lastActivity } : existing?.sendResult ?? null,
    replyResult: seed.activity.some((item) => item.type === "email_reply_received")
      ? { status: 200, timestamp: seed.lastReplyReceivedAt ?? seed.lastActivity, source: seed.lastReplySource ?? "webhook" }
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
    bookingArtifact: existing?.bookingArtifact ?? seed.bookingArtifact ?? null,
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
  if (state.emailGenerated) completed.add("email_generated");
  if (state.emailApproved) completed.add("email_approved");
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
  const [liveOutbound, setLiveOutbound] = useState(true);
  const [emailProvider, setEmailProvider] = useState<string | null>(null);
  const [rollbackBatchSize, setRollbackBatchSize] = useState(50);
  const [newProspect, setNewProspect] = useState<ProspectCreateForm>(EMPTY_PROSPECT_FORM);
  const [creatingProspect, setCreatingProspect] = useState(false);
  const [createProspectError, setCreateProspectError] = useState<string | null>(null);
  const [companySuggestions, setCompanySuggestions] = useState<CompanySuggestion[]>([]);
  const [companySuggestionsLoading, setCompanySuggestionsLoading] = useState(false);
  const [prospects, setProspects] = useState<ProspectSeed[]>([]);
  const [selectedProspectId, setSelectedProspectId] = useState<string | null>(null);
  const [prospectStates, setProspectStates] = useState<Record<string, ProspectUiState>>({});
  const [prospectsLoading, setProspectsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<string>("live-inbox");

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
        setLiveOutbound(Boolean(data?.live_outbound ?? true));
        setEmailProvider(typeof data?.email_provider === "string" ? data.email_provider : null);
        setRollbackBatchSize(Number(data?.rollback_batch_size ?? 50));
      } catch {
        // ignore
      }
      await loadProspects();
    })();
  }, []);

  useEffect(() => {
    const query = newProspect.company.trim();
    if (!query) {
      setCompanySuggestions([]);
      return;
    }
    const timeoutId = setTimeout(async () => {
      setCompanySuggestionsLoading(true);
      try {
        const res = await fetch(`/api/prospects?q=${encodeURIComponent(query)}&limit=8`, {
          method: "PUT",
          cache: "no-store",
        });
        const data = await res.json().catch(() => ({}));
        setCompanySuggestions(Array.isArray((data as any)?.companies) ? (data as any).companies : []);
      } catch {
        setCompanySuggestions([]);
      } finally {
        setCompanySuggestionsLoading(false);
      }
    }, 250);
    return () => clearTimeout(timeoutId);
  }, [newProspect.company]);

  const selectedProspect = useMemo(
    () => prospects.find((prospect) => prospect.id === selectedProspectId) ?? prospects[0] ?? null,
    [prospects, selectedProspectId]
  );

  const selectedState = selectedProspect ? prospectStates[selectedProspect.id] : null;
  const hiringBrief = ((selectedState?.enrichResult as any)?.hiring?.brief ?? null) as HiringBrief | null;
  const gapBrief = ((selectedState?.enrichResult as any)?.competitor_gap?.brief ?? null) as CompetitorGapBrief | null;
  const timeline = selectedState ? buildTimeline(selectedState) : [];
  const outboundPaused = !liveOutbound;
  const qualificationReady = Boolean(selectedState?.qualification);
  const enrichmentReady = Boolean(selectedState?.enrichResult);
  const emailGenerated = Boolean(
    selectedState?.emailGenerated &&
      selectedState?.emailSource &&
      selectedState?.emailSubject.trim() &&
      selectedState?.emailText.trim()
  );
  const emailApproved = Boolean(selectedState?.emailApproved);
  const emailSendReady = Boolean(enrichmentReady && qualificationReady && emailGenerated && emailApproved && !outboundPaused);
  const lowConfidenceFallback =
    Boolean(selectedState?.qualification?.segment === "abstain") ||
    Boolean((selectedState?.qualification?.confidence ?? 0) < 0.6);
  const emailWarning = selectedState?.emailWarning ?? (lowConfidenceFallback ? "This is a generic fallback email because ICP confidence is low." : null);
  const loadedSeedFiles = selectedState?.emailSource?.seed_files_loaded ?? {};
  const seedFilesLoaded = Object.values(loadedSeedFiles).filter(Boolean).length;
  const emailGenerationMetadata = selectedState?.emailGenerationMetadata ?? null;
  const pipelineStatuses = [
    {
      key: "seed",
      label: "Seed files loaded",
      complete: seedFilesLoaded > 0,
      detail: seedFilesLoaded > 0 ? `${seedFilesLoaded} asset(s) loaded` : "Generate email to inspect loaded assets",
    },
    {
      key: "enrichment",
      label: "Enrichment completed",
      complete: enrichmentReady,
      detail: enrichmentReady ? "Hiring brief and competitor gap are available" : "Run enrichment first",
    },
    {
      key: "icp",
      label: "ICP classified",
      complete: qualificationReady,
      detail: qualificationReady
        ? `${selectedState?.qualification?.segment ?? "abstain"} @ ${(selectedState?.qualification?.confidence ?? 0).toFixed(2)}`
        : "ICP classification appears after enrichment",
    },
    {
      key: "generated",
      label: "Email generated",
      complete: emailGenerated,
      detail: emailGenerated ? "Draft came from the backend generator" : "Generate the email draft before editing",
    },
    {
      key: "approved",
      label: "Email approved",
      complete: emailApproved,
      detail: emailApproved ? "Approved for live send" : "Approve after reviewing or editing",
    },
    {
      key: "sent",
      label: "Email sent",
      complete: Boolean(selectedState?.lastMessageId),
      detail: selectedState?.lastMessageId ?? "Waiting for approved send",
    },
  ];

  function updateSelectedState(updater: (current: ProspectUiState) => ProspectUiState) {
    if (!selectedProspect) return;
    setProspectStates((current) => ({
      ...current,
      [selectedProspect.id]: updater(current[selectedProspect.id]),
    }));
  }

  function updateNewProspect<K extends keyof ProspectCreateForm>(field: K, value: ProspectCreateForm[K]) {
    if (createProspectError) setCreateProspectError(null);
    setNewProspect((current) => ({ ...current, [field]: value }));
  }

  function pickSuggestedCompany(company: CompanySuggestion) {
    setNewProspect((current) => ({
      ...current,
      company: company.name,
      domain: company.domain ?? current.domain,
      prospectName: current.prospectName || "Demo Prospect",
    }));
  }

  async function createProspectRecord() {
    const validationError = validateProspectForm(newProspect);
    if (validationError) {
      setCreateProspectError(validationError);
      return;
    }

    const normalizedPeersLimit = normalizePeersLimit(newProspect.peersLimit);
    setCreatingProspect(true);
    setCreateProspectError(null);
    try {
      const res = await fetch("/api/prospects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          company: newProspect.company.trim(),
          prospect_name: newProspect.prospectName.trim(),
          email: newProspect.email.trim(),
          domain: newProspect.domain.trim() || null,
          phone: newProspect.phone.trim() || null,
          peers_limit: normalizedPeersLimit,
          use_playwright: newProspect.usePlaywright,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error((data as any)?.detail ?? (data as any)?.error ?? "Prospect creation failed");
      const createdId = String((data as any)?.prospect?.id ?? "");
      setNewProspect(EMPTY_PROSPECT_FORM);
      await loadProspects();
      if (createdId) setSelectedProspectId(createdId);
      setActiveTab("dashboard");
    } catch (error: any) {
      setCreateProspectError(error?.message ?? "Unknown error");
    } finally {
      setCreatingProspect(false);
    }
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
          use_playwright: selectedState.usePlaywright,
          peers_limit: selectedState.peersLimit,
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

  async function generateEmail() {
    if (!selectedProspect || !selectedState) return;
    updateSelectedState((current) => ({ ...current, prospectActionLoading: "generate-email", actionsError: null }));
    try {
      const res = await fetch("/api/generate-email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prospect_id: selectedProspect.id,
          approval_reset: true,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error((data as any)?.detail ?? (data as any)?.error ?? "Email generation failed");
      updateSelectedState((current) => ({
        ...current,
        prospectActionLoading: null,
        emailSubject: (data as any)?.email?.subject ?? current.emailSubject,
        emailText: (data as any)?.email?.text ?? current.emailText,
        emailSource: (data as any)?.email?.source ?? null,
        emailWarning: (data as any)?.email?.warning ?? null,
        emailGenerated: true,
        emailGeneratedAt: (data as any)?.generation_metadata?.generated_at ?? new Date().toISOString(),
        emailGenerationMetadata: (data as any)?.generation_metadata ?? null,
        emailApproved: false,
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

  async function approveEmail(approved: boolean) {
    if (!selectedProspect || !selectedState) return;
    updateSelectedState((current) => ({ ...current, prospectActionLoading: approved ? "approve-email" : "unapprove-email", actionsError: null }));
    try {
      const res = await fetch("/api/approve-email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prospect_id: selectedProspect.id,
          approved,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error((data as any)?.detail ?? (data as any)?.error ?? "Email approval update failed");
      updateSelectedState((current) => ({
        ...current,
        prospectActionLoading: null,
        emailApproved: Boolean((data as any)?.approved),
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
      const manualText = selectedState.replyText.trim();
      const useStoredReply = manualText.length === 0 && Boolean(selectedState.lastReplyText);
      const res = await fetch("/api/process-reply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prospect_id: selectedProspect.id,
          message_id: useStoredReply ? selectedState.lastReplyMessageId : selectedState.lastMessageId,
          subject: useStoredReply ? selectedState.lastReplySubject : selectedState.emailSubject,
          text: useStoredReply ? null : manualText,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error((data as any)?.detail ?? (data as any)?.error ?? "Reply processing failed");
      updateSelectedState((current) => ({
        ...current,
        replyResult: { status: res.status, data, timestamp: new Date().toISOString(), source: useStoredReply ? "stored_webhook_reply" : "manual" },
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
          attendee_name: selectedProspect.prospectName,
          attendee_email: selectedProspect.email,
          timezone: "EAT", // Default to East Africa Time as per requirements
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error((data as any)?.detail ?? (data as any)?.error ?? "Booking sync failed");
      updateSelectedState((current) => ({
        ...current,
        bookingResult: { status: res.status, data, timestamp: new Date().toISOString() },
        bookingArtifact: (data as any)?.booking_artifact ?? null,
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
        <div className="mx-auto grid max-w-[1200px] gap-6">
          <LaunchpadCard
            form={newProspect}
            loading={creatingProspect}
            error={createProspectError}
            suggestions={companySuggestions}
            suggestionsLoading={companySuggestionsLoading}
            onChange={updateNewProspect}
            onPickCompany={pickSuggestedCompany}
            onSubmit={createProspectRecord}
          />
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
    <main className="min-h-screen bg-[radial-gradient(circle_at_top-left,_rgba(242,181,76,0.18),_transparent_28%),linear-gradient(180deg,_rgba(255,255,255,0.92),_rgba(245,247,250,0.98))] px-4 py-6 md:px-8 md:py-8">
      <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6 overflow-x-clip">
        {/* Navigation Tabs */}
        <div className="overflow-hidden rounded-[32px] border border-border/70 bg-white/85 px-6 py-4 shadow-[0_20px_60px_rgba(15,23,42,0.08)] backdrop-blur md:px-8">
          <nav className="flex gap-6">
            {[
              { id: "dashboard", label: "Dashboard" },
              { id: "prospect-brief", label: "Prospect brief" },
              { id: "live-inbox", label: "Live inbox" },
              { id: "call-booking", label: "Call booking" },
              { id: "full-pipeline", label: "Full pipeline" },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "px-4 py-2 text-sm font-medium rounded-lg transition-colors",
                  activeTab === tab.id
                    ? "bg-amber-100 text-amber-900"
                    : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
                )}
              >
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        {/* Live Inbox View */}
        {activeTab === "live-inbox" && (
          <div className="grid gap-6 xl:grid-cols-[minmax(0,380px)_minmax(0,1fr)]">
            {/* Active Threads */}
            <Card className="min-w-0 overflow-hidden border border-border/70 bg-white/85 backdrop-blur">
              <CardHeader className="border-b border-border/70 pb-4">
                <CardTitle className="flex items-center gap-2">
                  <Users className="h-5 w-5 text-primary" />
                  Active threads
                </CardTitle>
                <CardDescription>Real-time prospect conversations and booking status.</CardDescription>
              </CardHeader>
              <CardContent className="p-0">
                <div className="max-w-full overflow-x-auto">
                  {prospectsLoading ? (
                    <div className="p-8 text-center text-sm text-slate-500">Loading threads...</div>
                  ) : (
                    <div className="divide-y divide-border/60">
                      {prospects.map((prospect) => {
                        const state = prospectStates[prospect.id];
                        const hasBooking = state?.bookingArtifact?.status === "confirmed";
                        const hasReply = state?.lastReplyText;
                        const lastActivity = formatTimestamp(state?.lastActivity);
                        
                        return (
                          <div
                            key={prospect.id}
                            className={cn(
                              "cursor-pointer p-4 transition-colors hover:bg-amber-50/40",
                              selectedProspectId === prospect.id && "bg-amber-50/70"
                            )}
                            onClick={() => setSelectedProspectId(prospect.id)}
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0 flex-1">
                                <div className="font-semibold text-slate-900">
                                  {prospect.prospectName} · {prospect.company}
                                </div>
                                {hasReply && (
                                  <div className="mt-1 text-sm text-slate-600 truncate">
                                    "{state.lastReplyText.substring(0, 60)}..."
                                  </div>
                                )}
                                {hasBooking && (
                                  <div className="mt-1 text-sm text-slate-600 truncate">
                                    "{state.bookingArtifact?.start_time ? new Date(state.bookingArtifact.start_time).toLocaleString('en-US', {
                                      weekday: 'short',
                                      hour: 'numeric',
                                      minute: '2-digit',
                                      timeZoneName: 'short'
                                    }) : 'Booking confirmed'}"
                                  </div>
                                )}
                              </div>
                              <div className="flex flex-col items-end gap-2">
                                <div className="text-xs text-slate-500">
                                  {hasBooking ? "call booked" : hasReply ? "qualify intent" : lastActivity}
                                </div>
                                {hasBooking && (
                                  <Badge className="border-none bg-emerald-100 text-emerald-800 text-xs">
                                    call booked
                                  </Badge>
                                )}
                                {state?.lastMessageId && !hasBooking && (
                                  <Badge className="border-none bg-slate-100 text-slate-700 text-xs">
                                    sent
                                  </Badge>
                                )}
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Conversation View */}
            <Card className="min-w-0 border border-border/70 bg-white/90">
              {selectedProspect && selectedState ? (
                <>
                  <CardHeader className="border-b border-border/60 pb-4">
                    <CardTitle className="flex items-center gap-2">
                      <Mail className="h-5 w-5 text-primary" />
                      {selectedProspect.prospectName} &lt;{selectedProspect.email}&gt;
                    </CardTitle>
                    <CardDescription>{selectedProspect.company} · Thread: {selectedState.threadId}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    {/* Original Email */}
                    {selectedState.emailSubject && selectedState.emailText && (
                      <div className="rounded-[24px] border border-border/70 bg-slate-50/80 p-5">
                        <div className="text-xs uppercase tracking-[0.18em] text-slate-500 mb-2">Original Message</div>
                        <div className="font-semibold text-slate-900 mb-2">{selectedState.emailSubject}</div>
                        <div className="text-sm text-slate-700 whitespace-pre-wrap">{selectedState.emailText}</div>
                      </div>
                    )}

                    {/* Reply */}
                    {selectedState.lastReplyText && (
                      <div className="rounded-[24px] border border-emerald-200 bg-emerald-50/80 p-5">
                        <div className="text-xs uppercase tracking-[0.18em] text-emerald-600 mb-2">Reply from {selectedProspect.prospectName}</div>
                        <div className="text-sm text-emerald-800 whitespace-pre-wrap">{selectedState.lastReplyText}</div>
                        <div className="mt-2 text-xs text-emerald-600">{formatTimestamp(selectedState.lastReplyReceivedAt)}</div>
                      </div>
                    )}

                    {/* System Classification */}
                    {selectedState.replyIntent && (
                      <div className="rounded-[24px] border border-sky-200 bg-sky-50/80 p-5">
                        <div className="text-xs uppercase tracking-[0.18em] text-sky-600 mb-2">System</div>
                        <div className="text-sm text-sky-800 space-y-2">
                          <div><strong>Intent classified:</strong> {selectedState.replyIntent}</div>
                          {selectedState.replyNextAction && (
                            <div><strong>Next action:</strong> {selectedState.replyNextAction.type?.replace(/_/g, ' ')}</div>
                          )}
                          {selectedState.qualification && (
                            <div><strong>Bench match:</strong> {selectedState.qualification.segment} ✓ confidence {selectedState.qualification.confidence.toFixed(2)}</div>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Agent Draft */}
                    {selectedState.replyNextAction?.draft && (
                      <div className="rounded-[24px] border border-amber-200 bg-amber-50/80 p-5">
                        <div className="text-xs uppercase tracking-[0.18em] text-amber-600 mb-2">Agent reply (draft) - tone: pass</div>
                        <div className="text-sm text-amber-800 whitespace-pre-wrap">{selectedState.replyNextAction.draft}</div>
                      </div>
                    )}

                    {/* Booking Artifact */}
                    <div className="rounded-[24px] border border-border/70 bg-white p-5">
                      <div className="text-sm font-semibold text-slate-900 mb-4">Booking Artifact State</div>
                      {selectedState.bookingArtifact && selectedState.bookingArtifact.status === "confirmed" ? (
                        <BookingArtifactCard artifact={selectedState.bookingArtifact} />
                      ) : (
                        <div className="rounded-[22px] border border-dashed border-border/70 bg-slate-50/70 p-4 text-center text-sm text-slate-500">
                          No confirmed booking yet.
                        </div>
                      )}
                    </div>
                  </CardContent>
                </>
              ) : (
                <CardContent className="p-8 text-center text-sm text-slate-500">
                  Select a thread to view conversation
                </CardContent>
              )}
            </Card>
          </div>
        )}

        {/* Original Dashboard View */}
        {activeTab === "dashboard" && (
          <div className="space-y-6">
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
                    Run the full production demo from one screen: create the prospect, enrich it, generate the signal-grounded draft, approve, send, process reply, and sync booking.
                  </p>
                </div>
                <div className="grid gap-3 md:grid-cols-3 xl:w-[560px]">
                  <MetricCard label="Qualified Prospects" value={String(dashboardStats.qualified)} hint="Enriched and ready for follow-up." />
                  <MetricCard label="Active Threads" value={String(dashboardStats.activeThreads)} hint="Prospects with outbound activity." />
                  <MetricCard label="Calls Booked" value={String(dashboardStats.booked)} hint="Bookings synced into CRM." />
                </div>
              </div>
            </header>

            <LaunchpadCard
              form={newProspect}
              loading={creatingProspect}
              error={createProspectError}
              suggestions={companySuggestions}
              suggestionsLoading={companySuggestionsLoading}
              onChange={updateNewProspect}
              onPickCompany={pickSuggestedCompany}
              onSubmit={createProspectRecord}
            />

            <div className="grid gap-6 xl:grid-cols-[minmax(0,360px)_minmax(0,1fr)]">
              <Card className="border border-border/70 bg-white/90">
                <CardHeader className="border-b border-border/60 pb-4">
                  <CardTitle className="flex items-center gap-2">
                    <Users className="h-5 w-5 text-primary" />
                    Prospects
                  </CardTitle>
                  <CardDescription>Select the record you want to present live.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 p-4">
                  {prospects.map((prospect) => {
                    const summary = getProspectStateSummary(prospectStates[prospect.id]);
                    const active = prospect.id === selectedProspect.id;
                    return (
                      <button
                        key={prospect.id}
                        type="button"
                        className={cn(
                          "w-full rounded-[22px] border px-4 py-4 text-left transition-colors",
                          active ? "border-amber-300 bg-amber-50/80" : "border-border/70 bg-slate-50/70 hover:bg-slate-100"
                        )}
                        onClick={() => setSelectedProspectId(prospect.id)}
                      >
                        <div className="text-sm font-semibold text-slate-900">{prospect.company}</div>
                        <div className="mt-1 text-sm text-slate-600">{prospect.prospectName}</div>
                        <div className="mt-1 text-xs text-slate-500">{prospect.email}</div>
                        <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
                          <span>{summary.segment}</span>
                          <span>{summary.aiMaturity}</span>
                        </div>
                      </button>
                    );
                  })}
                </CardContent>
              </Card>

              <div className="grid gap-6">
                <Card className="border border-border/70 bg-white/90">
                  <CardHeader className="border-b border-border/60 pb-4">
                    <CardTitle className="flex items-center gap-2">
                      <Building2 className="h-5 w-5 text-primary" />
                      Selected Prospect
                    </CardTitle>
                    <CardDescription>{selectedProspect.company} · {selectedProspect.prospectName}</CardDescription>
                  </CardHeader>
                  <CardContent className="grid gap-4 md:grid-cols-3">
                    <div className="rounded-[22px] border border-border/70 bg-slate-50/70 p-4">
                      <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Thread</div>
                      <div className="mt-2 text-sm font-semibold text-slate-900">{detailIdentity.threadId}</div>
                    </div>
                    <div className="rounded-[22px] border border-border/70 bg-slate-50/70 p-4">
                      <div className="text-xs uppercase tracking-[0.18em] text-slate-500">ICP</div>
                      <div className="mt-2 text-sm font-semibold text-slate-900">{selectedState.qualification?.segment ?? "Pending"}</div>
                    </div>
                    <div className="rounded-[22px] border border-border/70 bg-slate-50/70 p-4">
                      <div className="text-xs uppercase tracking-[0.18em] text-slate-500">AI Maturity</div>
                      <div className="mt-2 text-sm font-semibold text-slate-900">{String(hiringBrief?.ai_maturity?.score ?? 0)}</div>
                    </div>
                  </CardContent>
                </Card>

                <Card className="border border-border/70 bg-white/90">
                  <CardHeader className="border-b border-border/60 pb-4">
                    <CardTitle className="flex items-center gap-2">
                      <Send className="h-5 w-5 text-primary" />
                      Demo Controls
                    </CardTitle>
                    <CardDescription>Drive the presentation from here without terminal commands.</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-5">
                    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                      <Button type="button" className="gap-2" onClick={runEnrichment} disabled={selectedState.enrichmentLoading}>
                        {selectedState.enrichmentLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                        Run Enrichment
                      </Button>
                      <Button type="button" variant="secondary" className="gap-2" onClick={generateEmail} disabled={!enrichmentReady || !qualificationReady || selectedState.prospectActionLoading === "generate-email"}>
                        {selectedState.prospectActionLoading === "generate-email" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                        Generate Email
                      </Button>
                      <Button type="button" variant="secondary" className="gap-2" onClick={() => approveEmail(true)} disabled={!emailGenerated || emailApproved || selectedState.prospectActionLoading === "approve-email"}>
                        {selectedState.prospectActionLoading === "approve-email" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Mail className="h-4 w-4" />}
                        Approve
                      </Button>
                      <Button type="button" variant="secondary" className="gap-2" onClick={sendOutreach} disabled={!emailSendReady || selectedState.prospectActionLoading === "send-email"}>
                        {selectedState.prospectActionLoading === "send-email" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                        Send Email
                      </Button>
                      <Button type="button" variant="secondary" className="gap-2" onClick={processReply} disabled={selectedState.prospectActionLoading === "reply"}>
                        {selectedState.prospectActionLoading === "reply" ? <Loader2 className="h-4 w-4 animate-spin" /> : <MessageSquareReply className="h-4 w-4" />}
                        Process Reply
                      </Button>
                      <Button type="button" variant="secondary" className="gap-2" onClick={syncBooking} disabled={selectedState.prospectActionLoading === "booking"}>
                        {selectedState.prospectActionLoading === "booking" ? <Loader2 className="h-4 w-4 animate-spin" /> : <CalendarCheck2 className="h-4 w-4" />}
                        Sync Booking
                      </Button>
                    </div>

                    <div className="grid gap-3 md:grid-cols-2">
                      {pipelineStatuses.map((item) => (
                        <div key={item.key} className={cn("rounded-[20px] border p-4", item.complete ? "border-emerald-200 bg-emerald-50/80" : "border-border/70 bg-slate-50/70")}>
                          <div className="flex items-center justify-between gap-3">
                            <div className="text-sm font-semibold text-slate-900">{item.label}</div>
                            <Badge className={cn("border-none", item.complete ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-700")}>
                              {item.complete ? "complete" : "pending"}
                            </Badge>
                          </div>
                          <div className="mt-2 text-sm text-slate-600">{item.detail}</div>
                        </div>
                      ))}
                    </div>

                    {selectedState.enrichmentError ? (
                      <div className="rounded-[22px] border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{selectedState.enrichmentError}</div>
                    ) : null}
                    {selectedState.actionsError ? (
                      <div className="rounded-[22px] border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{selectedState.actionsError}</div>
                    ) : null}
                  </CardContent>
                </Card>
              </div>
            </div>
          </div>
        )}

        {/* Other Tab Placeholders */}
        {activeTab === "prospect-brief" && (
          <Card className="p-8 text-center">
            <h2 className="text-xl font-semibold text-slate-900 mb-2">Prospect Brief</h2>
            <p className="text-slate-600">Detailed prospect analysis and brief generation coming soon.</p>
          </Card>
        )}

        {activeTab === "call-booking" && (
          <Card className="p-8 text-center">
            <h2 className="text-xl font-semibold text-slate-900 mb-2">Call Booking</h2>
            <p className="text-slate-600">Calendar integration and booking management coming soon.</p>
          </Card>
        )}

        {activeTab === "full-pipeline" && (
          <div className="grid gap-6 xl:grid-cols-[minmax(0,430px)_minmax(0,1fr)]">
            <LaunchpadCard
              form={newProspect}
              loading={creatingProspect}
              error={createProspectError}
              suggestions={companySuggestions}
              suggestionsLoading={companySuggestionsLoading}
              onChange={updateNewProspect}
              onPickCompany={pickSuggestedCompany}
              onSubmit={createProspectRecord}
            />
            <Card className="border border-border/70 bg-white/90">
              <CardHeader className="border-b border-border/60 pb-4">
                <CardTitle className="flex items-center gap-2">
                  <Sparkles className="h-5 w-5 text-primary" />
                  Pipeline Command Center
                </CardTitle>
                <CardDescription>Present the entire conversion engine on one screen: source a prospect, create it, enrich it, classify it, generate copy, send, and move to booking.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-5">
                <div className="grid gap-4 md:grid-cols-3">
                  <div className="rounded-[22px] border border-border/70 bg-slate-50/70 p-4">
                    <div className="text-xs uppercase tracking-[0.2em] text-slate-500">Selected prospect</div>
                    <div className="mt-2 text-xl font-semibold text-slate-950">{selectedProspect.company}</div>
                    <div className="mt-1 text-sm text-slate-600">{selectedProspect.email}</div>
                  </div>
                  <div className="rounded-[22px] border border-border/70 bg-slate-50/70 p-4">
                    <div className="text-xs uppercase tracking-[0.2em] text-slate-500">Current stage</div>
                    <div className="mt-2"><StatusBadge value={selectedState.lifecycleStage} /></div>
                    <div className="mt-2 text-sm text-slate-600">{selectedState.qualification?.segment ?? "Awaiting qualification"}</div>
                  </div>
                  <div className="rounded-[22px] border border-border/70 bg-slate-50/70 p-4">
                    <div className="text-xs uppercase tracking-[0.2em] text-slate-500">Delivery rail</div>
                    <div className="mt-2 text-xl font-semibold text-slate-950">{emailProvider ?? "configured"}</div>
                    <div className="mt-1 text-sm text-slate-600">{outboundPaused ? "Outbound paused" : "Outbound live"}</div>
                  </div>
                </div>
                <div className="grid gap-3">
                  {[
                    { step: "1. Prospect creation", detail: "Create the record directly in the app so production storage has a working lead.", ready: true },
                    { step: "2. Enrichment + CRM write", detail: enrichmentReady ? "Hiring brief, competitor gap, and CRM payload are available." : "Run enrichment to create the artifacts and CRM sync.", ready: enrichmentReady },
                    { step: "3. ICP + email generation", detail: qualificationReady ? `Segment ${selectedState.qualification?.segment} at ${(selectedState.qualification?.confidence ?? 0).toFixed(2)}.` : "Qualification appears after enrichment and gates email generation.", ready: qualificationReady },
                    { step: "4. Operator approval + send", detail: emailSendReady ? "Draft is approved and ready for live send." : "Approve the generated draft before sending.", ready: emailApproved },
                    { step: "5. Reply handling + booking", detail: selectedState.bookingArtifact ? "Reply and booking artifacts have been captured." : "Process replies and sync booking to complete the loop.", ready: Boolean(selectedState.replyResult || selectedState.bookingArtifact) },
                  ].map((item) => (
                    <div
                      key={item.step}
                      className={cn(
                        "rounded-[22px] border p-4",
                        item.ready ? "border-emerald-200 bg-emerald-50/75" : "border-border/70 bg-slate-50/70"
                      )}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="text-sm font-semibold text-slate-900">{item.step}</div>
                        <Badge className={cn("border-none", item.ready ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-700")}>
                          {item.ready ? "ready" : "pending"}
                        </Badge>
                      </div>
                      <div className="mt-2 text-sm text-slate-600">{item.detail}</div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </main>
  );
}
