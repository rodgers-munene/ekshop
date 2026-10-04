import { cookies } from "next/headers";
import { NextResponse } from "next/server";

/**
 * Shared plumbing for the BFF proxy routes.
 *
 * The existing proxy files each declare their own `BASE_URL` and repeat the
 * cookie/forward/parse sequence. That was tolerable at nine files and is not
 * tolerable at twenty, so new routes use these helpers. Existing routes are left
 * alone rather than rewritten: a sweeping refactor of working proxies on the same
 * day as a delivery deadline trades a known-good state for an unknown one.
 *
 * These routes exist because `next.config.ts` defines no rewrites, so the browser
 * cannot reach the backend directly.
 */

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL;

/** Cookie holding a buyer / seller / admin token. */
const USER_COOKIE = "ekshop_token";
/** Cookie holding a rider token. Deliberately separate: a rider token cannot
 *  authorise a merchant call, and vice versa. */
const AGENT_COOKIE = "ekshop_agent_token";

async function tokenFor(cookieName: string): Promise<string | null> {
  const cookieStore = await cookies();
  return cookieStore.get(cookieName)?.value ?? null;
}

type TokenKind = "user" | "agent";

async function authHeaderFor(kind: TokenKind): Promise<string | null> {
  const token = await tokenFor(kind === "agent" ? AGENT_COOKIE : USER_COOKIE);
  return token ? `Bearer ${token}` : null;
}

const unauthorized = () =>
  NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

/** Proxy a request to the backend, or answer 401 if the caller has no token. */
export async function proxy(
  kind: TokenKind,
  path: string,
  init: RequestInit & { search?: string } = {},
): Promise<NextResponse> {
  const auth = await authHeaderFor(kind);
  if (!auth) return unauthorized();

  const { search, ...rest } = init;
  const res = await fetch(`${API_BASE_URL}${path}${search ?? ""}`, {
    ...rest,
    headers: {
      Authorization: auth,
      ...(rest.body ? { "Content-Type": "application/json" } : {}),
      ...(rest.headers ?? {}),
    },
    // Prices and job state must never be cached: a stale quote is a wrong price.
    cache: "no-store",
  });

  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}

/** Same as {@link proxy} but reads and forwards a JSON request body. */
export async function proxyJson(
  kind: TokenKind,
  path: string,
  req: Request,
  method: "POST" | "PATCH" | "PUT" | "DELETE",
): Promise<NextResponse> {
  const body = await req.json().catch(() => ({}));
  return proxy(kind, path, { method, body: JSON.stringify(body) });
}

/** Guard for the `(dashboard)` / `(admin)` server components. */
export async function authHeader(kind: TokenKind = "user"): Promise<string | null> {
  return authHeaderFor(kind);
}