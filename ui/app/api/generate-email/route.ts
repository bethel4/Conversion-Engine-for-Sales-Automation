import { NextResponse } from "next/server";

type GenerateEmailRequest = {
  prospect_id: string;
  approval_reset?: boolean;
};

const AGENT_API_URL = process.env.AGENT_API_URL ?? "http://127.0.0.1:8000";

export async function POST(req: Request) {
  let payload: GenerateEmailRequest;
  try {
    payload = (await req.json()) as GenerateEmailRequest;
  } catch {
    return NextResponse.json({ error: "Malformed JSON body" }, { status: 400 });
  }

  if (!payload.prospect_id || !payload.prospect_id.trim()) {
    return NextResponse.json({ error: "`prospect_id` is required" }, { status: 400 });
  }

  const res = await fetch(`${AGENT_API_URL}/prospects/${encodeURIComponent(payload.prospect_id)}/generate-email`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      approval_reset: payload.approval_reset ?? true,
    }),
    cache: "no-store",
  });

  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}
