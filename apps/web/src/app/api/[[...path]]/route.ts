import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.INTERNAL_API_URL || "http://localhost:8000";

export async function GET(request: NextRequest) {
  return handleRequest(request, "GET");
}

export async function POST(request: NextRequest) {
  return handleRequest(request, "POST");
}

export async function PUT(request: NextRequest) {
  return handleRequest(request, "PUT");
}

export async function PATCH(request: NextRequest) {
  return handleRequest(request, "PATCH");
}

export async function DELETE(request: NextRequest) {
  return handleRequest(request, "DELETE");
}

export async function OPTIONS(request: NextRequest) {
  return handleRequest(request, "OPTIONS");
}

async function handleRequest(request: NextRequest, method: string) {
  const path = request.nextUrl.pathname;
  const url = `${API_BASE}${path}${request.nextUrl.search}`;

  const headers: Record<string, string> = {};
  request.headers.forEach((value, key) => {
    if (!["host", "connection", "content-length"].includes(key.toLowerCase())) {
      headers[key] = value;
    }
  });

  let body: BodyInit | undefined;
  if (method !== "GET" && method !== "HEAD" && method !== "OPTIONS") {
    body = await request.arrayBuffer();
  }

  try {
    const response = await fetch(url, {
      method,
      headers,
      body,
    });

    const responseHeaders = new Headers();
    response.headers.forEach((value, key) => {
      if (!["content-encoding", "content-length", "transfer-encoding"].includes(key.toLowerCase())) {
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
      { detail: `Failed to connect to backend API: ${error}` },
      { status: 502 }
    );
  }
}
