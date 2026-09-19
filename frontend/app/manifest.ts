import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Ekshop - Kenya's Marketplace",
    short_name: "Ekshop",
    description: "Shop from thousands of sellers across Kenya.",
    start_url: "/",
    display: "standalone",
    background_color: "#ffffff",
    theme_color: "#0E3D2B",
    icons: [
      { src: "/icon.png", sizes: "any", type: "image/png" },
    ],
  };
}