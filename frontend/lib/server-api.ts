import { cookies } from "next/headers";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL

export class ServerFetchError extends Error {
    status: number;
    constructor(message: string, status: number) {
        super(message);
        this.status = status;
    }
}

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
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...options.headers,
        },
        cache: "no-store",
        redirect: "follow",
    });

    if (!res.ok) {
        const error = await res.json().catch(() => ({detail: "Request failed"}));
        throw new ServerFetchError(error.detail ?? `HTTP ${res.status}`, res.status);
    }

    return res.json();
}