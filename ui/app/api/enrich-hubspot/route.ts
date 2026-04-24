import { NextResponse } from "next/server";

type EnrichHubSpotRequest = {
  email: string;
  company_name: string;
  phone?: string | null;
  domain?: string | null;
  leadership_sources?: Array<Record<string, unknown>>;
};

const AGENT_API_URL = process.env.AGENT_API_URL ?? "http://127.0.0.1:8000";

export async function POST(req: Request) {
  let payload: EnrichHubSpotRequest;
  try {
    payload = (await req.json()) as EnrichHubSpotRequest;
  } catch {
    return NextResponse.json({ error: "Malformed JSON body" }, { status: 400 });
  }

  if (!payload.email || !payload.email.trim()) {
    return NextResponse.json({ error: "`email` is required" }, { status: 400 });
  }
  if (!payload.company_name || !payload.company_name.trim()) {
    return NextResponse.json({ error: "`company_name` is required" }, { status: 400 });
  }

  const res = await fetch(`${AGENT_API_URL}/crm/prospects/enrich`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: payload.email,
      company_name: payload.company_name,
      phone: payload.phone ?? null,
      domain: payload.domain ?? null,
      leadership_sources: payload.leadership_sources ?? []
    }),
    cache: "no-store"
  });

  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}

