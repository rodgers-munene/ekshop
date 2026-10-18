/**
 * Reading a JWT's claims without verifying it.
 *
 * Verification belongs to the backend: every protected call still carries the
 * raw token and is refused if it is not genuine. These helpers exist so the
 * proxy and the session probe can answer "is this cookie still alive, and whose
 * is it?" before spending a backend round-trip on a request that cannot succeed.
 */
export type JwtClaims = {
  exp?: number;
  role?: string;
  sub?: string;
};

export function decodeJwtClaims(token: string | null | undefined): JwtClaims | null {
  if (!token) return null;
  try {
    const payload = token.split(".")[1];
    if (!payload) return null;
    return JSON.parse(Buffer.from(payload, "base64url").toString("utf-8")) as JwtClaims;
  } catch {
    return null;
  }
}

export function isExpired(claims: JwtClaims | null): boolean {
  return !claims || typeof claims.exp !== "number" || claims.exp * 1000 <= Date.now();
}

export function isExpiringSoon(claims: JwtClaims | null, skewMs = 60_000): boolean {
  return !claims || typeof claims.exp !== "number" || claims.exp * 1000 < Date.now() + skewMs;
}
