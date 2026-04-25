import { NextResponse } from "next/server";

const AGENT_API_URL = process.env.AGENT_API_URL ?? "http://127.0.0.1:8000";

export async function GET() {
  const res = await fetch(`${AGENT_API_URL}/prospects`, {
    cache: "no-store"
  });

  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}
