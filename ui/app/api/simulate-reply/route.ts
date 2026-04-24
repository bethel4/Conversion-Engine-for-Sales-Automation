import { NextResponse } from "next/server";

type SimulateReplyRequest = {
  sender_email: string;
  message_id: string;
  subject?: string | null;
  text: string;
  to?: string[] | null;
};

const AGENT_API_URL = process.env.AGENT_API_URL ?? "http://127.0.0.1:8000";

export async function POST(req: Request) {
  let payload: SimulateReplyRequest;
  try {
    payload = (await req.json()) as SimulateReplyRequest;
  } catch {
    return NextResponse.json({ error: "Malformed JSON body" }, { status: 400 });
  }

  if (!payload.sender_email || !payload.sender_email.trim()) {
    return NextResponse.json({ error: "`sender_email` is required" }, { status: 400 });
  }
  if (!payload.message_id || !payload.message_id.trim()) {
    return NextResponse.json({ error: "`message_id` is required" }, { status: 400 });
  }
  if (!payload.text || !payload.text.trim()) {
    return NextResponse.json({ error: "`text` is required" }, { status: 400 });
  }

  // Matches `agent/main.py` parsing:
  // - event type must contain "reply"
  // - payload can be wrapped under `data`
  const webhookPayload = {
    type: "email.reply",
    data: {
      email_id: payload.message_id,
      from: payload.sender_email,
      to: payload.to ?? [],
      subject: payload.subject ?? null,
      text: payload.text
    }
  };

  const res = await fetch(`${AGENT_API_URL}/emails/webhook`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(webhookPayload),
    cache: "no-store"
  });

  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}

