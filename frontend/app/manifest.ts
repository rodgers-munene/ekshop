import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Ekshop - Kenya's Marketplace",
    short_name: "Ekshop",
    description: "Shop from thousands of verified sellers across Kenya.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#F4F4F4",
    theme_color: "#0E3D2B",
    orientation: "portrait",
    categories: ["shopping", "ecommerce", "business"],
    icons: [
      {
        src: "/icons/icon-192x192.png",
        sizes: "192x192",
        type: "image/png",
      },
      {
        src: "/icons/icon-512x512.png",
        sizes: "512x512",
        type: "image/png",
      },
      {
        src: "/icons/icon-maskable-512x512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  };
}