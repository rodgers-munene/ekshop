import Navbar from "@/components/layout/Navbar";
import CategoryStrip from "@/components/layout/CategoryStrip";
import Footer from "@/components/layout/Footer";
import Analytics from "@/components/Analytics";

export default function MainLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Navbar />
      <CategoryStrip />
      <main className="flex-1">{children}</main>
      <Footer />
      <Analytics />
    </>
  );
}
