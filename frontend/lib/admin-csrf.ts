import { cookies } from "next/headers";
import { NextResponse, NextRequest } from "next/server";

const CSRF_COOKIE_NAME = "ekshop_admin_csrf";
const CSRF_HEADER_NAME = "x-csrf-token";

export function generateCsrfToken(): string {
  const array = new Uint8Array(32);
  crypto.getRandomValues(array);
  return Array.from(array, (b) => b.toString(16).padStart(2, "0")).join("");
}

export async function getCsrfToken(): Promise<string | undefined> {
  const cookieStore = await cookies();
  return cookieStore.get(CSRF_COOKIE_NAME)?.value;
}

export async function setCsrfCookie(token: string): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.set(CSRF_COOKIE_NAME, token, {
    httpOnly: true,
    sameSite: "strict",
    path: "/",
    secure: process.env.NODE_ENV === "production",
    maxAge: 60 * 60 * 24 * 7, // 7 days, matches admin token
  });
}

export async function deleteCsrfCookie(): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.delete(CSRF_COOKIE_NAME);
}

export async function validateCsrf(request: Request): Promise<boolean> {
  const cookieStore = await cookies();
  const cookieToken = cookieStore.get(CSRF_COOKIE_NAME)?.value;
  const headerToken = request.headers.get(CSRF_HEADER_NAME);

  if (!cookieToken || !headerToken) return false;
  return subtleEqual(cookieToken, headerToken);
}

function subtleEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) {
    diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return diff === 0;
}

export async function ensureCsrfToken(response: NextResponse): Promise<NextResponse> {
  const cookieStore = await cookies();
  const existing = cookieStore.get(CSRF_COOKIE_NAME)?.value;
  if (!existing) {
    const token = generateCsrfToken();
    await setCsrfTokenInResponse(response, token);
  }
  return response;
}

export async function setCsrfTokenInResponse(response: NextResponse, token: string): Promise<void> {
  response.cookies.set(CSRF_COOKIE_NAME, token, {
    httpOnly: true,
    sameSite: "strict",
    path: "/",
    secure: process.env.NODE_ENV === "production",
    maxAge: 60 * 60 * 24 * 7,
  });
}

export function withCsrf<
  TContext extends { params: Promise<Record<string, string>> } = { params: Promise<Record<string, string>> }
>(
  handler: (req: NextRequest, context: TContext) => Promise<NextResponse>
) {
  return async (req: NextRequest, context: TContext): Promise<NextResponse> => {
    const method = req.method.toUpperCase();
    if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
      if (!(await validateCsrf(req))) {
        return NextResponse.json(
          { detail: "Invalid CSRF token" },
          { status: 403 }
        );
      }
    }
    return handler(req, context);
  };
}