import { NextResponse } from "next/server";

const AGENT_API_URL = process.env.AGENT_API_URL ?? "http://127.0.0.1:8000";

export async function GET() {
  try {
    const res = await fetch(`${AGENT_API_URL}/config`, { cache: "no-store" });
    const backend = await res.json().catch(() => ({}));
    return NextResponse.json(
      {
        agent_api_url: AGENT_API_URL,
        live_outbound: Boolean((backend as any)?.live_outbound),
        email_provider: (backend as any)?.email_provider ?? null,
        rollback_batch_size: Number((backend as any)?.rollback_batch_size ?? 50),
      },
      { status: res.ok ? 200 : res.status }
    );
  } catch {
    return NextResponse.json({
      agent_api_url: AGENT_API_URL,
      live_outbound: true,
      email_provider: null,
      rollback_batch_size: 50,
    });
  }
}
