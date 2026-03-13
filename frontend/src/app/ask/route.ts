/**
 * Server-side proxy route for AI instructional assistant.
 * The browser calls /ask (neutral URL, bypasses ad blockers).
 * This handler forwards the request to the backend server-to-server.
 */
import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.BACKEND_INTERNAL_URL ?? "http://backend:8000";

export async function POST(request: NextRequest) {
  try {
    const body = await request.text();
    const auth = request.headers.get("Authorization") ?? "";
    const cookie = request.headers.get("Cookie") ?? "";

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (auth) headers["Authorization"] = auth;
    if (cookie) headers["Cookie"] = cookie;

    const res = await fetch(`${BACKEND}/tutor/chat`, {
      method: "POST",
      headers,
      body,
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    console.error("[/ask proxy] error:", err);
    return NextResponse.json({ detail: "Proxy error — could not reach backend" }, { status: 502 });
  }
}
