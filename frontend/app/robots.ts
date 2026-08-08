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
      ],
    },
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
