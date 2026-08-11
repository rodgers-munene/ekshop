import type { MetadataRoute } from "next";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL!;

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: [
        "/admin",
        "/agent",
        "/dashboard",
        "/api",
        "/account",
        "/checkout",
        "/cart",
        "/messages",
        "/orders",
        "/ir-f1c04c9098",
      ],
    },
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
