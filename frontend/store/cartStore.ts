import { create } from "zustand"
import { persist } from "zustand/middleware"

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
    addItem: (item: CartItem) => void;
    removeItem: (product_id: string, variant_id?: string) => void;
    updateQuantity: (product_id: string, quantity: number, variant_id: string) => void;
    clearCart: () => void;
    totalItems: () => number;
    totalPrice: () => number;
}

export const useCartStore = create<CartState>()(
    persist(
        (set, get) => ({
            items: [],

            addItem: (item) =>
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
                }),

            removeItem: (product_id, variant_id) => {
                set((state) => {
                    return {
                        items: state.items.filter((i) => !(i.product_id !== product_id && i.variant_id !== variant_id))
                    }
                });
            },

            updateQuantity: (product_id, quantity, variant_id) =>
                set((state) => ({
                    items: state.items.map((i) =>
                        i.product_id === product_id && i.variant_id === variant_id
                            ? { ...i, quantity }
                            : i
                    ),
                })),

            clearCart: () => set({ items: [] }),

            totalItems: () => get().items.reduce((sum, i) => sum + i.quantity, 0),
            totalPrice: () => get().items.reduce((sum, i) => sum + i.unit_price * i.quantity, 0),

        }),
        {
            name: "ekshop_user_cart"
        }
    )
)