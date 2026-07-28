import type { Metadata } from "next";
import { Fraunces, DM_Sans } from "next/font/google";
import { Toaster } from "sonner";
import QueryProvider from "@/lib/query-provider";
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
  title: {
    default: "Ekshop - Kenya's Marketplace",
    template: "%s | Ekshop",
  },
  description: "Shop from thousands of sellers across Kenya.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${fraunces.variable} ${dmSans.variable}`}>
      <body className="min-h-screen flex flex-col antialiased">
        <QueryProvider>{children}</QueryProvider>
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
