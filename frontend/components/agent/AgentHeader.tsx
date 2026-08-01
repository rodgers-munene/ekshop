"use client";

import { useRouter } from "next/navigation";
import { Truck } from "lucide-react";
import { DeliveryAgent } from "@/types/interface";

export default function AgentHeader({ agent }: { agent: DeliveryAgent }) {
  const router = useRouter();

  async function handleLogout() {
    await fetch("/api/agent/auth", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "logout" }),
    });
    router.push("/agent/login");
  }

  return (
    <header className="bg-navy text-white sticky top-0 z-50">
      <div className="px-4 md:px-8 h-14 flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <Truck size={18} className="text-amber" />
          <span className="font-bold">
            EK<span className="text-amber">SHOP</span> <span className="text-white/70 font-normal">Agent</span>
          </span>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-sm text-white/80 hidden sm:inline">{agent.name}</span>
          <button onClick={handleLogout} className="text-sm font-medium text-white/80 hover:text-amber transition-colors">
            Logout
          </button>
        </div>
      </div>
    </header>
  );
}
