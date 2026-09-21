import Script from "next/script";

// Google Analytics 4. Renders nothing unless NEXT_PUBLIC_GA_ID is set, so local
// dev and preview builds stay out of the property unless you opt them in.
// Mounted on the storefront and auth layouts only — the seller dashboard, admin
// and agent areas are staff tools and would skew the e-commerce reports.
const GA_ID = process.env.NEXT_PUBLIC_GA_ID;

export default function Analytics() {
  if (!GA_ID) return null;

  return (
    <>
      <Script
        src={`https://www.googletagmanager.com/gtag/js?id=${GA_ID}`}
        strategy="afterInteractive"
      />
      <Script id="gtag-init" strategy="afterInteractive">
        {`window.dataLayer = window.dataLayer || [];
function gtag(){dataLayer.push(arguments);}
gtag('js', new Date());
gtag('config', '${GA_ID}');`}
      </Script>
    </>
  );
}
