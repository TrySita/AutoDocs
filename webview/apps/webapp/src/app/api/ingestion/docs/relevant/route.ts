import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";

export async function POST(request: NextRequest) {
  try {
    const baseUrl = process.env.INGESTION_API_URL;
    if (!baseUrl) {
      return NextResponse.json(
        { error: "INGESTION_API_URL not configured on server" },
        { status: 500 },
      );
    }
    const payload = await request.json();
    const res = await fetch(`${baseUrl}/docs/relevant`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
    const bodyText = await res.text();
    const contentType = res.headers.get("content-type") || "application/json";
    return new NextResponse(bodyText, {
      status: res.status,
      headers: { "content-type": contentType },
    });
  } catch (e: any) {
    return NextResponse.json(
      { error: e?.message || "Relevant docs proxy failed" },
      { status: 500 },
    );
  }
}

