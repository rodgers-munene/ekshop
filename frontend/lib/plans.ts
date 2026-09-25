export const SELLER_PLANS = [
  {
    code: "duka_starter",
    name: "Duka Starter",
    price: 500,
    tagline: "Get your shop online.",
    features: [
      "Online storefront",
      "Up to 20 products",
      "Order management",
      "Delivery coordination",
    ],
    highlight: false,
  },
  {
    code: "duka_premium",
    name: "Duka Premium",
    price: 9999,
    tagline: "Get seen. Get more customers.",
    features: [
      "Online storefront",
      "Unlimited products",
      "Order management",
      "Delivery coordination",
      "Featured placement on the Ekshop homepage",
      "Access to Tara POS",
    ],
    highlight: true,
  },
] as const;

export type SellerPlan = (typeof SELLER_PLANS)[number];

export function getSellerPlan(code: string | null): SellerPlan | undefined {
  return SELLER_PLANS.find((plan) => plan.code === code);
}
