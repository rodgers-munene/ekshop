import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import Link from "next/link";
import { DeliveryAgent } from "@/types/interface";
import AgentHeader from "@/components/agent/AgentHeader";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL;

async function getAgent(): Promise<DeliveryAgent | null> {
  const cookieStore = await cookies();
  const token = cookieStore.get("ekshop_agent_token")?.value;
  if (!token) return null;

  const res = await fetch(`${BASE_URL}/delivery/agents/me`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!res.ok) return null;
  return res.json();
}

export default async function AgentLayout({ children }: { children: React.ReactNode }) {
  const agent = await getAgent();
  if (!agent) redirect("/agent/login");

  return (
    <div className="min-h-screen bg-surface flex flex-col">
      <AgentHeader agent={agent} />
      <main className="flex-1 px-4 md:px-8 py-6 max-w-3xl mx-auto w-full">{children}</main>

      {/* Bottom nav */}
      <nav className="sticky bottom-0 bg-bg/95 backdrop-blur border-t border-border">
        <div className="max-w-3xl mx-auto flex items-center justify-around py-2">
          <NavItem href="/agent" icon="home" label="Home" />
          <NavItem href="/agent/deliveries" icon="deliveries" label="Deliveries" />
          <NavItem href="/agent/route" icon="route" label="Route" />
          <NavItem href="/agent/earnings" icon="earnings" label="Earnings" />
        </div>
      </nav>
    </div>
  );
}

function NavItem({ href, icon, label }: { href: string; icon: string; label: string }) {
  const icons: Record<string, string> = {
    home: "M3 12l9-8 9 8M5 10v10h5v-6h4v6h5V10",
    deliveries: "M4 5h16v13H4zM4 9h16M8 5v4M16 5v4",
    route: "M12 2a10 10 0 100 20 10 10 0 000-20zM12 8v4l3 3",
    earnings: "M12 2v20M17 6H9.5a2.5 2.5 0 000 5h5a2.5 2.5 0 010 5H7",
  };

  return (
    <Link
      href={href}
      className="flex flex-col items-center gap-0.5 px-3 py-1 text-muted hover:text-ink transition-colors"
    >
      <svg width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24">
        <path d={icons[icon]} />
      </svg>
      <span className="text-[10px] font-medium">{label}</span>
    </Link>
  );
}
