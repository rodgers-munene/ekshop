import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import { decodeJwtClaims, isExpired, isExpiringSoon } from "@/lib/jwt";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL;

const PROTECTED_PAGES = [
  "/dashboard",
  "/account",
  "/checkout",
  "/orders",
  "/wishlist",
  "/messages",
  "/admin",
  // Platform financials. The backend now requires an admin token for
  // /investor/*, so this page must be guarded here too or an anonymous
  // visit lands on an empty "could not load" shell.
  "/ir-f1c04c9098",
  // The rider portal. It has its own cookie (`ekshop_agent_token`) and is guarded
  // by its own layout, but leaving it out of this list meant the proxy never ran
  // its refresh logic for agent routes -- so an expired rider token left the app
  // in a half-signed-in state instead of being renewed or cleared.
  "/agent",
];
const AUTH_PAGES = ["/login", "/register"];
const PROTECTED_API_PREFIXES = [
  "/api/dashboard",
  "/api/account",
  "/api/checkout",
  "/api/wishlist",
  "/api/paystack",
  "/api/mpesa",
  "/api/conversations",
  "/api/admin",
  "/api/delivery",
  // Fulfillment, pricing and agent routes. These were missing, so the proxy
  // skipped them entirely and they relied on each route handler checking its own
  // cookie. The handlers still check -- defence in depth -- but a route that
  // forgot one would have been reachable with no token at all.
  "/api/fulfillments",
  "/api/pricing",
  "/api/agent",
];

const COOKIE_OPTS = {
  httpOnly: true,
  sameSite: "lax" as const,
  path: "/",
  secure: process.env.NODE_ENV === "production",
};

async function tryRefresh(refreshToken: string): Promise<{ access_token: string; refresh_token: string } | null> {
  try {
    const res = await fetch(`${BASE_URL}/auth/refresh?raw_token=${encodeURIComponent(refreshToken)}`, {
      method: "POST",
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const isProtectedPage = PROTECTED_PAGES.some((p) => pathname === p || pathname.startsWith(`${p}/`));
  const isAuthPage = AUTH_PAGES.some((p) => pathname === p);
  const isProtectedApi = PROTECTED_API_PREFIXES.some((p) => pathname.startsWith(p));

  if (!isProtectedPage && !isAuthPage && !isProtectedApi) {
    return NextResponse.next();
  }

  let accessToken = request.cookies.get("ekshop_token")?.value;
  const refreshToken = request.cookies.get("ekshop_refresh")?.value;
  const response = NextResponse.next();
  const claims = decodeJwtClaims(accessToken);
  const hadToken = Boolean(accessToken);
  // A session only "ended" if there was one to end: someone who never signed in
  // must not be told their session expired.
  let sessionEnded = false;

  const clearSession = () => {
    accessToken = undefined;
    response.cookies.delete("ekshop_token");
    response.cookies.delete("ekshop_refresh");
  };

  if (claims?.role === "admin") {
    // Admin sessions are absolute: one login, a fixed window, then a fresh
    // login. Renewing here would quietly defeat that cap, so an admin token is
    // either still valid or the session is over.
    if (isExpired(claims)) {
      clearSession();
      sessionEnded = true;
    }
  } else if (refreshToken && isExpiringSoon(claims)) {
    const refreshed = await tryRefresh(refreshToken);
    if (refreshed) {
      accessToken = refreshed.access_token;
      response.cookies.set("ekshop_token", refreshed.access_token, { ...COOKIE_OPTS, maxAge: 60 * 60 * 24 * 7 });
      response.cookies.set("ekshop_refresh", refreshed.refresh_token, { ...COOKIE_OPTS, maxAge: 60 * 60 * 24 * 30 });
    } else {
      clearSession();
      sessionEnded = hadToken;
    }
  } else if (isExpired(claims)) {
    // Ran out with nothing left to renew it with.
    clearSession();
    sessionEnded = hadToken;
  }

  // API routes: never redirect, let the route handler return its own 401.
  // Just pass through with whatever refreshed cookies were set above.
  if (isProtectedApi) {
    return response;
  }

  if (isProtectedPage && !accessToken) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", pathname + request.nextUrl.search);
    if (sessionEnded) loginUrl.searchParams.set("reason", "expired");
    const redirect = NextResponse.redirect(loginUrl);
    response.cookies.getAll().forEach((c) => redirect.cookies.set(c));
    return redirect;
  }

  if (isAuthPage && accessToken) {
    const redirect = NextResponse.redirect(new URL("/", request.url));
    response.cookies.getAll().forEach((c) => redirect.cookies.set(c));
    return redirect;
  }

  return response;
}

export const config = {
  matcher: [
    "/dashboard/:path*",
    "/account/:path*",
    "/checkout/:path*",
    "/orders/:path*",
    "/wishlist/:path*",
    "/messages/:path*",
    "/admin/:path*",
    "/ir-f1c04c9098",
    "/login",
    "/register",
    "/api/dashboard/:path*",
    "/api/account/:path*",
    "/api/checkout/:path*",
    "/api/wishlist/:path*",
    "/api/paystack/:path*",
    "/api/mpesa/:path*",
    "/api/conversations/:path*",
    "/api/admin/:path*",
    "/api/delivery/:path*",
  ],
};
