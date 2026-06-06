import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";

export async function POST(request: NextRequest) {
  try {
    const form = await request.formData();
    const baseUrl = process.env.INGESTION_API_URL;
    if (!baseUrl) {
      return NextResponse.json(
        { error: "INGESTION_API_URL not configured on server" },
        { status: 500 },
      );
    }

    const res = await fetch(`${baseUrl}/docs/upload`, {
      method: "POST",
      body: form,
    });

    const contentType = res.headers.get("content-type") || "application/json";
    const bodyText = await res.text();
    return new NextResponse(bodyText, {
      status: res.status,
      headers: { "content-type": contentType },
    });
  } catch (e: any) {
    return NextResponse.json(
      { error: e?.message || "Upload proxy failed" },
      { status: 500 },
    );
  }
}

