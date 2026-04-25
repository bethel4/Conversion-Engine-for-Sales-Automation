import { NextResponse } from "next/server";

type SendBookingLinkRequest = {
  prospect_id: string;
  subject?: string | null;
};

const AGENT_API_URL = process.env.AGENT_API_URL ?? "http://127.0.0.1:8000";

export async function POST(req: Request) {
  let payload: SendBookingLinkRequest;
  try {
    payload = (await req.json()) as SendBookingLinkRequest;
  } catch {
    return NextResponse.json({ error: "Malformed JSON body" }, { status: 400 });
  }

  if (!payload.prospect_id || !payload.prospect_id.trim()) {
    return NextResponse.json({ error: "`prospect_id` is required" }, { status: 400 });
  }

  const res = await fetch(`${AGENT_API_URL}/prospects/${encodeURIComponent(payload.prospect_id)}/send-booking-link`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      subject: payload.subject ?? null
    }),
    cache: "no-store"
  });

  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}
