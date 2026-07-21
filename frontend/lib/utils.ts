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

const LEGACY_BASE = "https://ekshop.store";

export function resolveImageUrl(src?: string | null): string {
    if (!src) return "";
    if (src.startsWith("http://") || src.startsWith("https://")) return src;
    return `${LEGACY_BASE}${src}`;
}
