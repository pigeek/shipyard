// Thin API helper for the same-origin cookie-session SPA (ADR 0001).
//
// Identity comes from the httpOnly session cookie — there is no token in JS.
// Every request is sent with `credentials: "include"` so the cookie rides along.
// Mutations echo the readable `csrftoken` cookie back in the `X-CSRF-Token`
// header (double-submit), which is what the transport-aware CSRF gate checks.

export interface Me {
  id: string;
  email: string;
  is_active: boolean;
  is_verified: boolean;
  is_superuser: boolean;
}

function readCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
  return match ? decodeURIComponent(match[2]) : null;
}

export async function api(path: string, options: RequestInit = {}): Promise<Response> {
  const method = (options.method ?? "GET").toUpperCase();
  const headers = new Headers(options.headers);
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const csrf = readCookie("csrftoken");
    if (csrf) headers.set("X-CSRF-Token", csrf);
    if (options.body && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
  }
  return fetch(path, { ...options, headers, credentials: "include" });
}

export async function getMe(): Promise<Me | null> {
  const res = await api("/api/v1/users/me");
  return res.ok ? ((await res.json()) as Me) : null;
}

export async function logoutEverywhere(): Promise<void> {
  await api("/api/v1/auth/jwt/logout-all", { method: "POST" });
}
