import { cookies } from "next/headers";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL;
const CSRF_COOKIE_NAME = "ekshop_admin_csrf";
const CSRF_HEADER_NAME = "x-csrf-token";

export class ServerFetchError extends Error {
    status: number;
    constructor(message: string, status: number) {
        super(message);
        this.status = status;
    }
}

async function getCsrfToken(): Promise<string | undefined> {
    const cookieStore = await cookies();
    return cookieStore.get(CSRF_COOKIE_NAME)?.value;
}

export async function serverFetch<T>(
    path: string,
    options: RequestInit = {}
): Promise<T> {
    const cookieStore = await cookies();
    const token = cookieStore.get("ekshop_token")?.value;
    const method = (options.method || "GET").toUpperCase();

    const headers: Record<string, string> = {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(options.headers as Record<string, string> | undefined),
    };

    // Add CSRF token for mutating requests
    if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
        const csrfToken = await getCsrfToken();
        if (csrfToken) {
            headers[CSRF_HEADER_NAME] = csrfToken;
        }
    }

    const res = await fetch(`${BASE_URL}${path}`, {
        ...options,
        headers,
        cache: "no-store",
        redirect: "follow",
    });

    if (!res.ok) {
        const error = await res.json().catch(() => ({ detail: "Request failed" }));
        throw new ServerFetchError(error.detail ?? `HTTP ${res.status}`, res.status);
    }

    return res.json();
}