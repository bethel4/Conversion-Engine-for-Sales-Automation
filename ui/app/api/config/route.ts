import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    agent_api_url: process.env.AGENT_API_URL ?? "http://127.0.0.1:8000"
  });
}

