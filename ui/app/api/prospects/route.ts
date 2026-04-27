import { NextResponse } from "next/server";

const AGENT_API_URL = process.env.AGENT_API_URL ?? "http://127.0.0.1:8000";

function normalizeErrorMessage(data: any) {
  const detail = data?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (!item || typeof item !== "object") return null;
        const path = Array.isArray(item.loc) ? item.loc.slice(1).join(".") : null;
        const message = typeof item.msg === "string" ? item.msg : null;
        if (!message) return null;
        return path ? `${path}: ${message}` : message;
      })
      .filter(Boolean);
    if (messages.length) return messages.join("; ");
  }
  if (typeof data?.error === "string" && data.error.trim()) return data.error;
  return null;
}

export async function GET() {
  const res = await fetch(`${AGENT_API_URL}/prospects`, {
    cache: "no-store"
  });

  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}

export async function PUT(req: Request) {
  const { searchParams } = new URL(req.url);
  const q = searchParams.get("q") ?? "";
  const limit = searchParams.get("limit") ?? "20";
  const res = await fetch(`${AGENT_API_URL}/companies?q=${encodeURIComponent(q)}&limit=${encodeURIComponent(limit)}`, {
    cache: "no-store",
  });

  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}

export async function POST(req: Request) {
  let payload: Record<string, unknown>;
  try {
    payload = (await req.json()) as Record<string, unknown>;
  } catch {
    return NextResponse.json({ error: "Malformed JSON body" }, { status: 400 });
  }

  const res = await fetch(`${AGENT_API_URL}/prospects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    cache: "no-store",
  });

  const data = await res.json().catch(() => ({}));
  const error = !res.ok ? normalizeErrorMessage(data) : null;
  if (error) {
    return NextResponse.json({ ...data, error }, { status: res.status });
  }
  return NextResponse.json(data, { status: res.status });
}
