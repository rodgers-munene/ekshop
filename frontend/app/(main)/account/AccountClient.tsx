"use client";

import { useState } from "react";
import { toast } from "sonner";
import { useAuthStore } from "@/store/authStore";
import { User, UserAddress } from "@/types/interface";

type Tab = "profile" | "addresses";

export default function AccountClient({ user, addresses: initialAddresses }: { user: User; addresses: UserAddress[] }) {
  const [tab, setTab] = useState<Tab>("profile");
  const [addresses, setAddresses] = useState(initialAddresses);
  const { setUser } = useAuthStore();

  // ── Profile form ───────────────────────────────────────────
  const [profile, setProfile] = useState({ first_name: user.first_name, last_name: user.last_name, phone: user.phone ?? "", county: user.county ?? "" });
  const [savingProfile, setSavingProfile] = useState(false);

  async function saveProfile() {
    setSavingProfile(true);
    try {
      const res = await fetch("/api/account", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(profile),
      });
      const data = await res.json();
      if (!res.ok) { toast.error(data.detail ?? "Update failed"); return; }
      setUser(data);
      toast.success("Profile updated");
    } catch { toast.error("Something went wrong"); }
    finally { setSavingProfile(false); }
  }

  // ── Address form ───────────────────────────────────────────
  const blankAddr = { label: "", first_name: "", last_name: "", phone: "", county: "", town: "", street: "", building: "" };
  const [newAddr, setNewAddr] = useState(blankAddr);
  const [addingAddr, setAddingAddr] = useState(false);
  const [showAddrForm, setShowAddrForm] = useState(false);

  async function addAddress() {
    setAddingAddr(true);
    try {
      const res = await fetch("/api/account/addresses", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newAddr),
      });
      const data = await res.json();
      if (!res.ok) { toast.error(data.detail ?? "Failed to add address"); return; }
      setAddresses((prev) => [...prev, data]);
      setNewAddr(blankAddr);
      setShowAddrForm(false);
      toast.success("Address added");
    } catch { toast.error("Something went wrong"); }
    finally { setAddingAddr(false); }
  }

  async function deleteAddress(id: string) {
    await fetch(`/api/account/addresses/${id}`, { method: "DELETE" });
    setAddresses((prev) => prev.filter((a) => a.id !== id));
    toast.success("Address removed");
  }

  return (
    <div className="w-full max-w-3xl mx-auto px-4 md:px-6 py-6">
      <h1 className="text-2xl font-bold mb-6">My Account</h1>

      <div className="card p-6">
        {/* Tabs */}
        <div className="flex border-b border-border mb-6 -mx-6 px-6">
          {(["profile", "addresses"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-5 py-2.5 text-sm font-medium capitalize transition-colors border-b-2 -mb-px ${tab === t ? "border-amber text-ink" : "border-transparent text-muted hover:text-ink"}`}
            >
              {t}
            </button>
          ))}
        </div>

        {/* Profile tab */}
        {tab === "profile" && (
          <div className="space-y-5 max-w-sm">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-1">First name</label>
                <input value={profile.first_name} onChange={(e) => setProfile((p) => ({ ...p, first_name: e.target.value }))} className="input-field" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Last name</label>
                <input value={profile.last_name} onChange={(e) => setProfile((p) => ({ ...p, last_name: e.target.value }))} className="input-field" />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Email</label>
              <input value={user.email} disabled className="input-field opacity-50 cursor-not-allowed" />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Phone</label>
              <input value={profile.phone} onChange={(e) => setProfile((p) => ({ ...p, phone: e.target.value }))} className="input-field" placeholder="0712 345 678" />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">County</label>
              <input value={profile.county} onChange={(e) => setProfile((p) => ({ ...p, county: e.target.value }))} className="input-field" placeholder="Nairobi" />
            </div>
            <button onClick={saveProfile} disabled={savingProfile} className="btn-accent disabled:opacity-50">
              {savingProfile ? "Saving..." : "Save Changes"}
            </button>
          </div>
        )}

        {/* Addresses tab */}
        {tab === "addresses" && (
          <div className="space-y-4">
            {addresses.map((addr) => (
              <div key={addr.id} className="flex items-start justify-between rounded-lg border border-border p-4">
                <div>
                  <p className="text-sm font-medium">{addr.first_name} {addr.last_name} {addr.label && <span className="text-xs text-muted ml-1">({addr.label})</span>}</p>
                  <p className="text-xs text-muted mt-0.5">{addr.town}, {addr.county}</p>
                  {addr.street && <p className="text-xs text-muted">{addr.street}</p>}
                  <p className="text-xs text-muted">{addr.phone}</p>
                </div>
                <button onClick={() => deleteAddress(addr.id)} className="text-xs text-muted hover:text-danger underline">Remove</button>
              </div>
            ))}

            {!showAddrForm ? (
              <button onClick={() => setShowAddrForm(true)} className="w-full py-3 rounded-lg border-2 border-dashed border-border text-sm text-muted hover:text-amber hover:border-amber transition-colors">
                + Add New Address
              </button>
            ) : (
              <div className="rounded-lg border border-border p-5 space-y-4">
                <h3 className="font-semibold">New Address</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-medium block mb-1">First name</label>
                    <input value={newAddr.first_name} onChange={(e) => setNewAddr((a) => ({ ...a, first_name: e.target.value }))} className="input-field" />
                  </div>
                  <div>
                    <label className="text-xs font-medium block mb-1">Last name</label>
                    <input value={newAddr.last_name} onChange={(e) => setNewAddr((a) => ({ ...a, last_name: e.target.value }))} className="input-field" />
                  </div>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-medium block mb-1">Phone</label>
                    <input value={newAddr.phone} onChange={(e) => setNewAddr((a) => ({ ...a, phone: e.target.value }))} className="input-field" placeholder="0712 345 678" />
                  </div>
                  <div>
                    <label className="text-xs font-medium block mb-1">Label (optional)</label>
                    <input value={newAddr.label} onChange={(e) => setNewAddr((a) => ({ ...a, label: e.target.value }))} className="input-field" placeholder="Home / Work" />
                  </div>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-medium block mb-1">Town</label>
                    <input value={newAddr.town} onChange={(e) => setNewAddr((a) => ({ ...a, town: e.target.value }))} className="input-field" />
                  </div>
                  <div>
                    <label className="text-xs font-medium block mb-1">County</label>
                    <input value={newAddr.county} onChange={(e) => setNewAddr((a) => ({ ...a, county: e.target.value }))} className="input-field" />
                  </div>
                </div>
                <div>
                  <label className="text-xs font-medium block mb-1">Street / Estate</label>
                  <input value={newAddr.street} onChange={(e) => setNewAddr((a) => ({ ...a, street: e.target.value }))} className="input-field" />
                </div>
                <div className="flex gap-3">
                  <button onClick={addAddress} disabled={addingAddr} className="btn-accent px-6 py-2 disabled:opacity-50">
                    {addingAddr ? "Saving..." : "Save Address"}
                  </button>
                  <button onClick={() => setShowAddrForm(false)} className="px-4 py-2 text-sm text-muted hover:text-ink">Cancel</button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
