import { NextResponse } from "next/server";

type ProcessReplyRequest = {
  prospect_id: string;
  message_id?: string | null;
  subject?: string | null;
  text: string;
};

const AGENT_API_URL = process.env.AGENT_API_URL ?? "http://127.0.0.1:8000";

export async function POST(req: Request) {
  let payload: ProcessReplyRequest;
  try {
    payload = (await req.json()) as ProcessReplyRequest;
  } catch {
    return NextResponse.json({ error: "Malformed JSON body" }, { status: 400 });
  }

  if (!payload.prospect_id || !payload.prospect_id.trim()) {
    return NextResponse.json({ error: "`prospect_id` is required" }, { status: 400 });
  }
  if (!payload.text || !payload.text.trim()) {
    return NextResponse.json({ error: "`text` is required" }, { status: 400 });
  }

  const res = await fetch(`${AGENT_API_URL}/prospects/${encodeURIComponent(payload.prospect_id)}/process-reply`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message_id: payload.message_id ?? null,
      subject: payload.subject ?? null,
      text: payload.text
    }),
    cache: "no-store"
  });

  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}
