import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";


export function formatKES(amount: number | string): string {
    const num = typeof amount === "string" ? parseFloat(amount): amount
    return new Intl.NumberFormat("en-KE", {
        style: "currency",
        currency: "KES",
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    }).format(num);
}

// Deterministic per-day randomness: same seed string (e.g. today's date)
// always yields the same shuffle, so a page reload doesn't reshuffle content,
// but the picks change once the seed rolls over to a new day.
function hashSeed(seed: string): number {
  let h = 0;
  for (let i = 0; i < seed.length; i++) {
    h = (Math.imul(31, h) + seed.charCodeAt(i)) | 0;
  }
  return h >>> 0;
}

function mulberry32(seed: number): () => number {
  let a = seed;
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function seededShuffle<T>(items: T[], seed: string): T[] {
  const random = mulberry32(hashSeed(seed));
  const result = [...items];
  for (let i = result.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    [result[i], result[j]] = [result[j], result[i]];
  }
  return result;
}

export function todaysSeed(): string {
  return new Date().toISOString().slice(0, 10);
}

export function truncate(str: string, length: number): string {
    if (str.length <= length) return str;
    return str.slice(0, length).trimEnd() + "...";
}

const HTML_NAMED_ENTITIES: Record<string, string> = {
    amp: "&",
    lt: "<",
    gt: ">",
    quot: '"',
    apos: "'",
    nbsp: " ",
};

export function decodeHtml(str: string): string {
    if (!str) return str;
    return str.replace(/&(#x[0-9a-fA-F]+|#\d+|[a-zA-Z]+);/g, (match, entity: string) => {
        if (entity[0] === "#") {
            const code = entity[1] === "x" || entity[1] === "X"
                ? parseInt(entity.slice(2), 16)
                : parseInt(entity.slice(1), 10);
            return Number.isNaN(code) ? match : String.fromCodePoint(code);
        }
        return HTML_NAMED_ENTITIES[entity] ?? match;
    });
}

const LEGACY_BASE = "https://ekshop.store";

export function resolveImageUrl(src?: string | null): string {
    if (!src) return "";
    if (src.startsWith("http://") || src.startsWith("https://")) return src;
    return `${LEGACY_BASE}${src}`;
}
