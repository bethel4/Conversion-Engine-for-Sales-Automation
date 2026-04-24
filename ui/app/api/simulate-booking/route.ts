import { NextResponse } from "next/server";

type SimulateBookingRequest = {
  email: string;
  booking_id: string;
  status?: "confirmed" | "accepted" | "completed";
  start_time?: string | null;
  title?: string | null;
};

const AGENT_API_URL = process.env.AGENT_API_URL ?? "http://127.0.0.1:8000";

export async function POST(req: Request) {
  let payload: SimulateBookingRequest;
  try {
    payload = (await req.json()) as SimulateBookingRequest;
  } catch {
    return NextResponse.json({ error: "Malformed JSON body" }, { status: 400 });
  }

  if (!payload.email || !payload.email.trim()) {
    return NextResponse.json({ error: "`email` is required" }, { status: 400 });
  }
  if (!payload.booking_id || !payload.booking_id.trim()) {
    return NextResponse.json({ error: "`booking_id` is required" }, { status: 400 });
  }

  const webhookPayload = {
    triggerEvent: "booking.created",
    data: {
      booking: {
        id: payload.booking_id,
        status: payload.status ?? "confirmed",
        startTime: payload.start_time ?? null,
        title: payload.title ?? "Discovery call",
        attendee: {
          email: payload.email
        }
      }
    }
  };

  const res = await fetch(`${AGENT_API_URL}/calendar/webhook`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(webhookPayload),
    cache: "no-store"
  });

  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}

