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
