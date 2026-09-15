"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Crosshair, MapPin } from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { User, UserAddress, County, SubCounty, Ward, GeoSelection } from "@/types/interface";
import { reverseGeocode } from "@/lib/geo";
import LocationPicker from "@/components/geo/LocationPicker";

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
  const blankAddr = {
    label: "",
    first_name: "",
    last_name: "",
    county: "",
    subcounty_id: "",
    ward_id: "",
    exact_location: "",
    areaCode: "+254",
    phoneNumber: "",
    lat: undefined as number | undefined,
    lng: undefined as number | undefined,
    sublocation: "",
  };
  const [newAddr, setNewAddr] = useState(blankAddr);
  const [addingAddr, setAddingAddr] = useState(false);
  const [showAddrForm, setShowAddrForm] = useState(false);
  const [mapOpen, setMapOpen] = useState(false);
  const [detecting, setDetecting] = useState(false);
  const [geoHint, setGeoHint] = useState("");

  const { data: counties } = useQuery({
    queryKey: ["geography", "counties"],
    queryFn: () => fetch("/api/geography/counties").then((r) => r.json()) as Promise<County[]>,
    enabled: showAddrForm,
  });

  const { data: subcounties } = useQuery({
    queryKey: ["geography", "subcounties", newAddr.county],
    queryFn: () =>
      fetch(`/api/geography/counties/${encodeURIComponent(newAddr.county)}/subcounties`).then((r) =>
        r.json()
      ) as Promise<SubCounty[]>,
    enabled: !!newAddr.county,
  });

  const { data: wards } = useQuery({
    queryKey: ["geography", "wards", newAddr.subcounty_id],
    queryFn: () =>
      fetch(`/api/geography/subcounties/${newAddr.subcounty_id}/wards`).then((r) => r.json()) as Promise<Ward[]>,
    enabled: !!newAddr.subcounty_id,
  });

  function setCounty(county: string) {
    setNewAddr((a) => ({ ...a, county, subcounty_id: "", ward_id: "" }));
  }

  function setSubcounty(subcounty_id: string) {
    setNewAddr((a) => ({ ...a, subcounty_id, ward_id: "" }));
  }

  function applyGeo(sel: GeoSelection) {
    setNewAddr((a) => ({
      ...a,
      county: sel.county,
      subcounty_id: sel.subcountyId ?? "",
      ward_id: sel.wardId ?? "",
      exact_location: sel.addressHint,
      lat: sel.lat,
      lng: sel.lng,
      sublocation: sel.sublocation ?? "",
    }));
    setGeoHint(sel.addressHint);
  }

  function detectLocation() {
    if (!navigator.geolocation) {
      toast.error("Location isn't available on this device. Use the map instead.");
      return;
    }
    setDetecting(true);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const data = await reverseGeocode(pos.coords.latitude, pos.coords.longitude);
        setDetecting(false);
        if (!data) {
          toast.error("We couldn't pinpoint your location — use the map instead.");
          return;
        }
        applyGeo({
          lat: data.lat,
          lng: data.lng,
          county: data.county,
          subcounty: data.subcounty,
          ward: data.ward,
          location: data.location,
          sublocation: data.sublocation,
          addressHint: data.address_hint,
          countyId: data.county_id,
          subcountyId: data.subcounty_id,
          wardId: data.ward_id,
        });
      },
      () => {
        setDetecting(false);
        toast.error("Couldn't get your location. Check browser permission or use the map.");
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  }

  async function addAddress() {
    if (!newAddr.ward_id) { toast.error("Please select a subcounty and ward"); return; }
    const subcountyName = subcounties?.find((s) => s.id === newAddr.subcounty_id)?.name ?? "";
    setAddingAddr(true);
    try {
      const res = await fetch("/api/account/addresses", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          label: newAddr.label,
          first_name: newAddr.first_name,
          last_name: newAddr.last_name,
          county: newAddr.county,
          town: subcountyName,
          ward_id: newAddr.ward_id,
          exact_location: newAddr.exact_location,
          phone: `${newAddr.areaCode}${newAddr.phoneNumber}`,
          lat: newAddr.lat,
          lng: newAddr.lng,
          sublocation: newAddr.sublocation,
        }),
      });
      const data = await res.json();
      if (!res.ok) { toast.error(data.detail ?? "Failed to add address"); return; }
      setAddresses((prev) => [...prev, data]);
      setNewAddr(blankAddr);
      setGeoHint("");
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
                  <p className="text-xs text-muted mt-0.5">
                    {[addr.ward?.name, addr.town, addr.county].filter(Boolean).join(", ")}
                  </p>
                  {addr.exact_location && <p className="text-xs text-muted">{addr.exact_location}</p>}
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

                <div className="flex flex-wrap items-center gap-3">
                  <button
                    type="button"
                    onClick={detectLocation}
                    disabled={detecting}
                    className="flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm font-medium hover:border-amber disabled:opacity-50"
                  >
                    <Crosshair size={15} className={detecting ? "animate-spin" : ""} />
                    {detecting ? "Detecting…" : "Use my location"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setMapOpen(true)}
                    className="flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm font-medium hover:border-amber"
                  >
                    <MapPin size={15} />
                    Set pin on map
                  </button>
                  {geoHint && (
                    <p className="text-xs text-ink/70">
                      Detected: <strong>{geoHint}</strong>
                      {!newAddr.ward_id && <span className="ml-1 text-muted">(choose the nearest ward below)</span>}
                    </p>
                  )}
                </div>
                <div>
                  <label className="text-xs font-medium block mb-1">Label (optional)</label>
                  <input value={newAddr.label} onChange={(e) => setNewAddr((a) => ({ ...a, label: e.target.value }))} className="input-field" placeholder="Home / Work" />
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-medium block mb-1">First Name <span className="text-danger">*</span></label>
                    <input value={newAddr.first_name} onChange={(e) => setNewAddr((a) => ({ ...a, first_name: e.target.value }))} className="input-field" required />
                  </div>
                  <div>
                    <label className="text-xs font-medium block mb-1">Last Name <span className="text-danger">*</span></label>
                    <input value={newAddr.last_name} onChange={(e) => setNewAddr((a) => ({ ...a, last_name: e.target.value }))} className="input-field" required />
                  </div>
                </div>

                <div>
                  <label className="text-xs font-medium block mb-1">County <span className="text-danger">*</span></label>
                  <select value={newAddr.county} onChange={(e) => setCounty(e.target.value)} className="input-field" required>
                    <option value="">Select county</option>
                    {counties?.map((c) => (
                      <option key={c.id} value={c.name}>{c.name}</option>
                    ))}
                  </select>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-medium block mb-1">Subcounty <span className="text-danger">*</span></label>
                    <select
                      value={newAddr.subcounty_id}
                      onChange={(e) => setSubcounty(e.target.value)}
                      className="input-field disabled:opacity-50"
                      disabled={!newAddr.county}
                      required
                    >
                      <option value="">Select subcounty</option>
                      {subcounties?.map((s) => (
                        <option key={s.id} value={s.id}>{s.name}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs font-medium block mb-1">Ward <span className="text-danger">*</span></label>
                    <select
                      value={newAddr.ward_id}
                      onChange={(e) => setNewAddr((a) => ({ ...a, ward_id: e.target.value }))}
                      className="input-field disabled:opacity-50"
                      disabled={!newAddr.subcounty_id}
                      required
                    >
                      <option value="">Select ward</option>
                      {wards?.map((w) => (
                        <option key={w.id} value={w.id}>{w.name}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div>
                  <label className="text-xs font-medium block mb-1">Street Address <span className="text-danger">*</span></label>
                  <input
                    value={newAddr.exact_location}
                    onChange={(e) => setNewAddr((a) => ({ ...a, exact_location: e.target.value }))}
                    className="input-field"
                    required
                  />
                  <p className="text-xs text-muted mt-1">Detailed street address can help our rider find you quickly.</p>
                </div>

                <div className="grid grid-cols-[7rem_1fr] gap-3">
                  <div>
                    <label className="text-xs font-medium block mb-1">Area Code <span className="text-danger">*</span></label>
                    <input value={newAddr.areaCode} disabled className="input-field opacity-50 cursor-not-allowed" />
                  </div>
                  <div>
                    <label className="text-xs font-medium block mb-1">Phone Number <span className="text-danger">*</span></label>
                    <input
                      value={newAddr.phoneNumber}
                      onChange={(e) => setNewAddr((a) => ({ ...a, phoneNumber: e.target.value.replace(/\D/g, "") }))}
                      className="input-field"
                      placeholder="712345678"
                      required
                    />
                  </div>
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

        {mapOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={() => setMapOpen(false)}>
            <div className="w-full max-w-2xl" onClick={(e) => e.stopPropagation()}>
              <p className="mb-2 text-center text-sm font-medium text-white">
                Drop the pin where you want delivery
              </p>
              <LocationPicker
                initial={newAddr.lat != null && newAddr.lng != null ? { lat: newAddr.lat, lng: newAddr.lng } : undefined}
                onCancel={() => setMapOpen(false)}
                onConfirm={(sel) => {
                  applyGeo(sel);
                  setMapOpen(false);
                  toast.success("Location pinned");
                }}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
