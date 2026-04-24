import { NextResponse } from "next/server";

type SendEmailRequest = {
  to: string[];
  subject: string;
  text?: string | null;
  html?: string | null;
  tags?: Array<Record<string, string>>;
};

const AGENT_API_URL = process.env.AGENT_API_URL ?? "http://127.0.0.1:8000";

export async function POST(req: Request) {
  let payload: SendEmailRequest;
  try {
    payload = (await req.json()) as SendEmailRequest;
  } catch {
    return NextResponse.json({ error: "Malformed JSON body" }, { status: 400 });
  }

  if (!payload.to || payload.to.length === 0) {
    return NextResponse.json({ error: "`to` is required" }, { status: 400 });
  }
  if (!payload.subject || !payload.subject.trim()) {
    return NextResponse.json({ error: "`subject` is required" }, { status: 400 });
  }
  if (!payload.text && !payload.html) {
    return NextResponse.json({ error: "Either `text` or `html` is required" }, { status: 400 });
  }

  const res = await fetch(`${AGENT_API_URL}/emails/send`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      to: payload.to,
      subject: payload.subject,
      text: payload.text ?? null,
      html: payload.html ?? null,
      tags: payload.tags ?? []
    }),
    cache: "no-store"
  });

  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}

