import { NextResponse } from "next/server";

type SyncBookingRequest = {
  prospect_id: string;
  booking_id: string;
  status?: "confirmed" | "accepted" | "completed";
  start_time?: string | null;
  title?: string | null;
};

const AGENT_API_URL = process.env.AGENT_API_URL ?? "http://127.0.0.1:8000";

export async function POST(req: Request) {
  let payload: SyncBookingRequest;
  try {
    payload = (await req.json()) as SyncBookingRequest;
  } catch {
    return NextResponse.json({ error: "Malformed JSON body" }, { status: 400 });
  }

  if (!payload.prospect_id || !payload.prospect_id.trim()) {
    return NextResponse.json({ error: "`prospect_id` is required" }, { status: 400 });
  }
  if (!payload.booking_id || !payload.booking_id.trim()) {
    return NextResponse.json({ error: "`booking_id` is required" }, { status: 400 });
  }

  const res = await fetch(`${AGENT_API_URL}/prospects/${encodeURIComponent(payload.prospect_id)}/sync-booking`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      booking_id: payload.booking_id,
      booking_status: payload.status ?? "confirmed",
      start_time: payload.start_time ?? null,
      title: payload.title ?? null
    }),
    cache: "no-store"
  });

  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}
