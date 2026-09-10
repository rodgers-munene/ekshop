import { create } from "zustand"
import { persist } from "zustand/middleware"

export interface AuthUser{
    id: string;
    email: string;
    first_name: string;
    last_name: string;
    role: "buyer" | "seller" | "admin";
    // "pending" for a seller who hasn't completed their first subscription
    // payment yet -- the dashboard renders locked for them.
    status: string;
    phone?: string;
    avatar_url?:  string
}

interface AuthState {
    user: AuthUser | null;
    isAuthenticated: boolean;
    setUser: (user: AuthUser) => void;
    clearUser: () => void;
}

export const useAuthStore = create<AuthState>()(
    persist(
        (set) => ({
            user: null,
            isAuthenticated: false,

            setUser: (user) => set({user, isAuthenticated: true}),

            clearUser: () => set({ user: null, isAuthenticated: false}),
        }),
        {
            name: "ekshop_user",
        }        
    )
);