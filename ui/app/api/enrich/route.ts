import { NextResponse } from "next/server";

type EnrichRequest = {
  prospect_id?: string;
  company_name: string;
  domain?: string | null;
  use_playwright?: boolean;
  peers_limit?: number;
  out_dir?: string;
  leadership_sources?: Array<Record<string, unknown>>;
};

const AGENT_API_URL = process.env.AGENT_API_URL ?? "http://127.0.0.1:8000";

export async function POST(req: Request) {
  let payload: EnrichRequest;
  try {
    payload = (await req.json()) as EnrichRequest;
  } catch {
    return NextResponse.json({ error: "Malformed JSON body" }, { status: 400 });
  }

  if (!payload.company_name || !payload.company_name.trim()) {
    return NextResponse.json({ error: "`company_name` is required" }, { status: 400 });
  }

  if (payload.prospect_id && payload.prospect_id.trim()) {
    const res = await fetch(`${AGENT_API_URL}/prospects/${encodeURIComponent(payload.prospect_id)}/enrich`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        domain: payload.domain ?? null,
        use_playwright: Boolean(payload.use_playwright),
        peers_limit: payload.peers_limit ?? 10,
        leadership_sources: payload.leadership_sources ?? []
      }),
      cache: "no-store"
    });

    const data = await res.json().catch(() => ({}));
    return NextResponse.json(data, { status: res.status });
  }

  const outDir = payload.out_dir ?? "data/briefs";

  const hiringRes = await fetch(`${AGENT_API_URL}/enrichment/hiring-brief`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      company_name: payload.company_name,
      domain: payload.domain ?? null,
      use_playwright: Boolean(payload.use_playwright),
      out_dir: outDir,
      leadership_sources: payload.leadership_sources ?? []
    }),
    cache: "no-store"
  });

  const hiring = await hiringRes.json().catch(() => ({}));
  if (!hiringRes.ok) {
    return NextResponse.json(hiring, { status: hiringRes.status });
  }

  const gapRes = await fetch(`${AGENT_API_URL}/enrichment/competitor-gap`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      company_name: payload.company_name,
      hiring_brief: hiring.brief,
      peers_limit: payload.peers_limit ?? 10,
      out_dir: outDir
    }),
    cache: "no-store"
  });

  const competitor_gap = await gapRes.json().catch(() => ({}));
  if (!gapRes.ok) {
    return NextResponse.json(competitor_gap, { status: gapRes.status });
  }

  return NextResponse.json({ status: "ok", hiring, competitor_gap }, { status: 200 });
}
