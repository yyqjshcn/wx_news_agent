const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchApi(path: string, options: RequestInit = {}) {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || "Request failed");
  }
  return res.json();
}

export const api = {
  get: (path: string) => fetchApi(path),
  post: (path: string, body: unknown) =>
    fetchApi(path, { method: "POST", body: JSON.stringify(body) }),
  patch: (path: string, body: unknown) =>
    fetchApi(path, { method: "PATCH", body: JSON.stringify(body) }),
  delete: (path: string) => fetchApi(path, { method: "DELETE" }),
};
