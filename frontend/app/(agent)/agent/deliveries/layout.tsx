import { cookies } from "next/headers";
import { redirect } from "next/navigation";
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

export default async function AgentDeliveriesLayout({ children }: { children: React.ReactNode }) {
  const agent = await getAgent();
  if (!agent) redirect("/agent/login");

  return (
    <div className="min-h-screen bg-surface flex flex-col">
      <AgentHeader agent={agent} />
      <main className="flex-1 px-4 md:px-8 py-6 max-w-3xl mx-auto w-full">{children}</main>
    </div>
  );
}
