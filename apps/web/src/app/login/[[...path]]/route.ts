import { NextRequest, NextResponse } from "next/server";

const WECHAT_ADAPTER = process.env.INTERNAL_WECHAT_ADAPTER_URL || "http://localhost:5000";

export async function GET(request: NextRequest) {
  return proxyRequest(request, "GET");
}

export async function POST(request: NextRequest) {
  return proxyRequest(request, "POST");
}

async function proxyRequest(request: NextRequest, method: string) {
  const restPath = request.nextUrl.pathname.replace(/^\/login/, "");
  const url = `${WECHAT_ADAPTER}${restPath}${request.nextUrl.search}`;

  const headers: Record<string, string> = {};
  request.headers.forEach((value, key) => {
    const lower = key.toLowerCase();
    if (!["host", "connection", "content-length"].includes(lower)) {
      headers[key] = value;
    }
  });

  let body: BodyInit | undefined;
  if (method !== "GET" && method !== "HEAD") {
    body = await request.arrayBuffer();
  }

  try {
    const response = await fetch(url, { method, headers, body, redirect: "manual" });

    const responseHeaders = new Headers();
    response.headers.forEach((value, key) => {
      const lower = key.toLowerCase();
      if (!["content-encoding", "content-length", "transfer-encoding"].includes(lower)) {
        responseHeaders.set(key, value);
      }
    });

    const data = await response.arrayBuffer();

    return new NextResponse(data, {
      status: response.status,
      headers: responseHeaders,
    });
  } catch (error) {
    return NextResponse.json(
      { error: `Failed to connect to WeChat adapter: ${error}` },
      { status: 502 }
    );
  }
}
