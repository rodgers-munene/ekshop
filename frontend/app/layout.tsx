import type { Metadata, Viewport } from "next";
import { Fraunces, DM_Sans } from "next/font/google";
import { Toaster } from "sonner";
import QueryProvider from "@/lib/query-provider";
import PwaHelper from "@/components/PwaHelper";
import "./globals.css";

const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-fraunces",
  display: "swap",
});

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-dm-sans",
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL!),
  title: {
    default: "Ekshop - Kenya's Marketplace",
    template: "%s | Ekshop",
  },
  description: "Shop from thousands of sellers across Kenya.",
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    title: "Ekshop",
    statusBarStyle: "default",
  },
  icons: {
    icon: ["/icons/icon-192x192.png", "/icons/icon-512x512.png"],
    apple: [{ url: "/icons/apple-touch-icon.png", sizes: "180x180", type: "image/png" }],
  },
};

export const viewport: Viewport = {
  themeColor: "#0E3D2B",
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${fraunces.variable} ${dmSans.variable}`}>
      <body className="min-h-screen flex flex-col antialiased">
        <QueryProvider>{children}</QueryProvider>
        <PwaHelper />
        <Toaster
          position="bottom-right"
          toastOptions={{
            style: {
              background: "#0E3D2B",
              color: "#FFFFFF",
              border: "1px solid #1B5940",
              borderRadius: "0.5rem",
            },
          }}
        />
      </body>
    </html>
  );
}
