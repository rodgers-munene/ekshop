import { create } from "zustand"
import { persist } from "zustand/middleware"
import { useAuthStore } from "./authStore"

export interface CartItem {
    product_id: string;
    product_name: string;
    product_slug: string;
    product_image: string;
    shop_id: string;
    shop_name: string;
    variant_id?: string;
    variant_label?: string; // e.g "500ml", "Red"
    unit_price: number;
    quantity: number;
}

export interface CartState {
    items: CartItem[];
    // Single item bought via "Buy Now". Kept apart from `items` so buying
    // one product straight away leaves the rest of the cart untouched.
    buyNowItem: CartItem | null;
    setBuyNowItem: (item: CartItem) => void;
    clearBuyNow: () => void;
    addItem: (item: CartItem) => void;
    removeItem: (product_id: string, variant_id?: string) => void;
    updateQuantity: (product_id: string, quantity: number, variant_id?: string) => void;
    clearCart: () => void;
    totalItems: () => number;
    totalPrice: () => number;
}

export interface SyncResult {
    ok: boolean;
    detail?: string;
}

/**
 * Mirror the cart onto the server.
 *
 * The cart lives in local storage, but a basket that is filled and then
 * deserted is only visible to the admin "cart abandonment" report if the
 * server has a copy of it. This sends the whole cart as a replace rather than
 * merging deltas, so it is idempotent: whatever the last call sent is the cart.
 * An empty list is meaningful -- it is how the shopper clearing their cart (or
 * finishing an order) is recorded.
 */
export async function syncCartToServer(items: CartItem[]): Promise<SyncResult> {
    try {
        const res = await fetch("/api/cart", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                items: items.map((i) => ({
                    product_id: i.product_id,
                    variant_id: i.variant_id ?? null,
                    quantity: i.quantity,
                })),
            }),
        })
        if (res.ok) return { ok: true }
        const data = await res.json().catch(() => ({}))
        return { ok: false, detail: data?.detail }
    } catch {
        return { ok: false }
    }
}

// Browsers raise a change event per tap, so wait for the shopper to settle
// before writing. Every write carries the whole cart, so the last one wins and
// nothing is lost by collapsing the burst.
const SYNC_DELAY_MS = 400
let syncTimer: ReturnType<typeof setTimeout> | null = null

function scheduleServerSync() {
    if (typeof window === "undefined") return
    if (syncTimer) clearTimeout(syncTimer)
    syncTimer = setTimeout(() => {
        syncTimer = null
        // A signed-out shopper has no server cart to write to; asking anyway
        // would only collect 401s.
        if (!useAuthStore.getState().isAuthenticated) return
        void syncCartToServer(useCartStore.getState().items)
    }, SYNC_DELAY_MS)
}

export const useCartStore = create<CartState>()(
    persist(
        (set, get) => ({
            items: [],
            buyNowItem: null,

            addItem: (item) => {
                set((state) => {
                    const existing = state.items.find(
                        (i) => i.product_id === item.product_id && i.variant_id === item.variant_id
                    );

                    // product already in cart we increment quantity
                    if (existing) {
                        return {
                            items: state.items.map((i) =>
                                i.product_id === item.product_id && i.variant_id == item.variant_id
                                    ? { ...i, quantity: i.quantity + item.quantity }
                                    : i
                            ),
                        };
                    }

                    // product not in cart - add it as a new entry
                    return { items: [...state.items, item] };
                });
                scheduleServerSync();
            },

            removeItem: (product_id, variant_id) => {
                set((state) => {
                    return {
                        items: state.items.filter((i) => !(i.product_id === product_id && i.variant_id === variant_id))
                    }
                });
                scheduleServerSync();
            },

            updateQuantity: (product_id, quantity, variant_id) => {
                set((state) => ({
                    items: state.items.map((i) =>
                        i.product_id === product_id && i.variant_id === variant_id
                            ? { ...i, quantity }
                            : i
                    ),
                }));
                scheduleServerSync();
            },

            clearCart: () => {
                set({ items: [] });
                // Emptied carts are written through too: the backend does not
                // clear the server cart when an order is placed, so without this
                // a paid basket would keep being reported as abandoned.
                scheduleServerSync();
            },

            setBuyNowItem: (item) => set({ buyNowItem: item }),
            clearBuyNow: () => set({ buyNowItem: null }),

            totalItems: () => get().items.reduce((sum, i) => sum + i.quantity, 0),
            totalPrice: () => get().items.reduce((sum, i) => sum + i.unit_price * i.quantity, 0),

        }),
        {
            name: "ekshop_user_cart"
        }
    )
)