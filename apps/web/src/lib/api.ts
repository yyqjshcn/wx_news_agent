async function fetchApi(path: string, options: RequestInit = {}) {
  const res = await fetch(path, {
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
  post: (path: string, body?: unknown) =>
    fetchApi(path, { method: "POST", body: body !== undefined ? JSON.stringify(body) : undefined }),
  patch: (path: string, body?: unknown) =>
    fetchApi(path, { method: "PATCH", body: body !== undefined ? JSON.stringify(body) : undefined }),
  delete: (path: string) => fetchApi(path, { method: "DELETE" }),
};
