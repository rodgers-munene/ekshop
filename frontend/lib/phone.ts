/**
 * Kenyan mobile number normalisation, mirroring `app/core/validators.py`
 * on the backend. Kept in step with it deliberately: the client gives the
 * seller an inline error as they type, the server is what actually enforces.
 */

/**
 * Normalise to `2547XXXXXXXX` / `2541XXXXXXXX`, or return null if the input
 * isn't a Kenyan mobile line.
 *
 * Accepts `0712345678`, `712345678`, `+254 712 345 678`, `254-712-345-678`,
 * and `2540712345678` (a country code glued onto a number that still had its
 * leading 0).
 */
export function normalizeKenyanPhone(value: string): string | null {
  let digits = (value ?? "").replace(/\D/g, "");

  if (digits.startsWith("254")) digits = digits.slice(3);
  if (digits.startsWith("0")) digits = digits.slice(1);

  if (digits.length !== 9 || (digits[0] !== "7" && digits[0] !== "1")) return null;

  return `254${digits}`;
}

export function isValidKenyanPhone(value: string): boolean {
  return normalizeKenyanPhone(value) !== null;
}
