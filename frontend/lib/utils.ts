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