import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL;

const PROTECTED_PAGES = ["/dashboard", "/account", "/checkout", "/orders", "/wishlist", "/messages", "/admin"];
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
];

const COOKIE_OPTS = {
  httpOnly: true,
  sameSite: "lax" as const,
  path: "/",
  secure: process.env.NODE_ENV === "production",
};

function decodeExpiryMs(token: string): number | null {
  try {
    const payload = token.split(".")[1];
    const json = JSON.parse(Buffer.from(payload, "base64url").toString("utf-8"));
    return typeof json.exp === "number" ? json.exp * 1000 : null;
  } catch {
    return null;
  }
}

function isExpiringSoon(token: string | undefined): boolean {
  if (!token) return true;
  const expiryMs = decodeExpiryMs(token);
  return expiryMs === null || expiryMs < Date.now() + 60_000; // refresh within 1 min of expiry
}

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

  if (isExpiringSoon(accessToken) && refreshToken) {
    const refreshed = await tryRefresh(refreshToken);
    if (refreshed) {
      accessToken = refreshed.access_token;
      response.cookies.set("ekshop_token", refreshed.access_token, { ...COOKIE_OPTS, maxAge: 60 * 60 * 24 * 7 });
      response.cookies.set("ekshop_refresh", refreshed.refresh_token, { ...COOKIE_OPTS, maxAge: 60 * 60 * 24 * 30 });
    } else {
      accessToken = undefined;
      response.cookies.delete("ekshop_token");
      response.cookies.delete("ekshop_refresh");
    }
  }

  // API routes: never redirect, let the route handler return its own 401.
  // Just pass through with whatever refreshed cookies were set above.
  if (isProtectedApi) {
    return response;
  }

  if (isProtectedPage && !accessToken) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", pathname);
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
