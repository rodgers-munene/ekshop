import { cookies } from "next/headers";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL

export async function serverFetch<T>(
    path: string,
    options: RequestInit= {}
): Promise<T> {
    const cookieStore = await cookies();
    const token = cookieStore.get("ekshop_token")?.value;

    const res = await fetch(`${BASE_URL}${path}`, {
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorisation: `Bearer ${token}`}: {}),
            ...options.headers,
        },
        cache: "no-store",
    });

    if (!res.ok) {
        const error = await res.json().catch(() => ({detail: "Request failed"}));
        throw new Error(error.detail?? `HTTP ${res.status}`);
    }

    return res.json();
}