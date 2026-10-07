"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Loader2, ShieldCheck, Upload, X } from "lucide-react";
import { toast } from "sonner";

import type { KYCDocument, RiderKYC } from "@/types/interface";

const VEHICLES = [
  { value: "bicycle", label: "Bicycle" },
  { value: "motorcycle", label: "Motorcycle" },
  { value: "pickup_van", label: "Pickup van" },
  { value: "refrigerated_van", label: "Refrigerated van" },
  { value: "refrigerated_truck", label: "Refrigerated truck" },
] as const;

const ACCEPT = "image/jpeg,image/png,image/webp,application/pdf";
const MAX_BYTES = 10 * 1024 * 1024;

type Uploaded = KYCDocument & { filename: string };

/**
 * A rider's KYC submission.
 *
 * This screen did not exist: the backend endpoint and the data model were both
 * complete, but nothing in the portal called them, so a rider could not get
 * through onboarding on their own. Uploads go to a separate multipart endpoint
 * and return storage keys; the submission sends those keys. Uploading first is
 * what lets a failed scan be retried without re-sending everything else.
 *
 * Identity and equipment are approved separately by an admin, so the status
 * shown here reports both halves rather than one verdict.
 */
export default function RiderKycForm() {
  const queryClient = useQueryClient();

  const { data, isPending, isError } = useQuery({
    queryKey: ["agent-kyc"],
    queryFn: async () => {
      const res = await fetch("/api/agent/kyc");
      if (!res.ok) throw new Error();
      return (await res.json()) as RiderKYC;
    },
  });

  const [vehicleType, setVehicleType] = useState("");
  const [nationalId, setNationalId] = useState("");
  const [licence, setLicence] = useState("");
  const [documents, setDocuments] = useState<Uploaded[]>([]);
  const [equipmentPhoto, setEquipmentPhoto] = useState<Uploaded | null>(null);
  const [uploading, setUploading] = useState<string | null>(null);

  // Pre-fill from the server so a returning rider sees their existing values.
  useEffect(() => {
    if (!data) return;
    setVehicleType(data.vehicle_type ?? "");
    setNationalId(data.national_id_number ?? "");
    setLicence(data.license_number ?? "");
    setDocuments(
      (data.kyc_documents ?? []).map((doc) => ({
        type: doc.type,
        key: doc.key,
        url: doc.url,
        filename: doc.type,
      })),
    );
  }, [data]);

  async function upload(file: File, kind: string): Promise<Uploaded | null> {
    if (file.size > MAX_BYTES) {
      toast.error(`${file.name} is over 10MB. Try a smaller photo.`);
      return null;
    }
    const body = new FormData();
    body.append("file", file);
    body.append("kind", kind);
    const res = await fetch("/api/agent/kyc/upload", { method: "POST", body });
    const json = await res.json().catch(() => ({}));
    if (!res.ok) {
      toast.error(json.detail ?? `Could not upload ${file.name}`);
      return null;
    }
    return { type: kind, key: json.key, url: null, filename: file.name };
  }

  async function onPickDocuments(files: FileList | null) {
    if (!files?.length) return;
    setUploading("documents");
    try {
      const done: Uploaded[] = [];
      for (const file of Array.from(files)) {
        const uploaded = await upload(file, "identity");
        if (uploaded) done.push(uploaded);
      }
      if (done.length) setDocuments((prev) => [...prev, ...done]);
      if (done.length < files.length) {
        toast.error(`${files.length - done.length} of ${files.length} did not upload`);
      }
    } finally {
      setUploading(null);
    }
  }

  async function onPickEquipment(file: File | null) {
    if (!file) return;
    setUploading("equipment");
    try {
      const uploaded = await upload(file, "equipment");
      if (uploaded) setEquipmentPhoto(uploaded);
    } finally {
      setUploading(null);
    }
  }

  const submit = useMutation({
    mutationFn: async () => {
      const res = await fetch("/api/agent/kyc", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          vehicle_type: vehicleType,
          national_id_number: nationalId.trim(),
          license_number: licence.trim() || null,
          kyc_documents: documents
            .filter((d) => d.key)
            .map((d) => ({ type: d.type, key: d.key })),
          equipment_photo_key: equipmentPhoto?.key ?? null,
        }),
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(json.detail ?? "Could not submit");
      return json as RiderKYC;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agent-kyc"] });
      toast.success("Sent for review. You will be notified once it is approved.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (isPending) {
    return (
      <p className="text-sm text-muted py-8 text-center">Loading your details…</p>
    );
  }

  if (isError) {
    return (
      <p className="text-sm text-danger py-8 text-center">
        Could not load your details. Try signing in again.
      </p>
    );
  }

  const identity = data.kyc_status;
  const readyToSubmit =
    Boolean(vehicleType) && nationalId.trim().length > 0 && documents.length > 0;

  return (
    <div className="space-y-6">
      <StatusPanel data={data} />

      {identity === "approved" && data.equipment_verified && (
        <div className="card p-4 flex items-start gap-3">
          <ShieldCheck size={20} className="text-success shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold text-sm">Your details are approved</p>
            <p className="text-xs text-muted mt-0.5">
              You do not need to do anything here. Submitting again takes you off
              the road until an admin re-approves.
            </p>
          </div>
        </div>
      )}

      <section>
        <h2 className="text-sm font-bold mb-3">Your vehicle</h2>
        <label className="block text-xs font-semibold mb-1.5">
          What do you ride?
        </label>
        <div className="grid grid-cols-1 gap-2">
          {VEHICLES.map((v) => (
            <label
              key={v.value}
              className={`flex items-center gap-2.5 p-3 rounded-lg border cursor-pointer text-sm ${
                vehicleType === v.value
                  ? "border-gold bg-amber/10"
                  : "border-border"
              }`}
            >
              <input
                type="radio"
                name="vehicle"
                value={v.value}
                checked={vehicleType === v.value}
                onChange={(e) => setVehicleType(e.target.value)}
                className="accent-gold"
              />
              {v.label}
            </label>
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-sm font-bold mb-3">Your details</h2>
        <div className="space-y-3">
          <label className="block">
            <span className="text-xs font-semibold">National ID number</span>
            <input
              value={nationalId}
              onChange={(e) => setNationalId(e.target.value)}
              maxLength={50}
              inputMode="numeric"
              className="input-field w-full mt-1 text-sm"
              placeholder="e.g. 12345678"
            />
          </label>
          <label className="block">
            <span className="text-xs font-semibold">
              Driving licence number
              <span className="font-normal text-muted"> (optional)</span>
            </span>
            <input
              value={licence}
              onChange={(e) => setLicence(e.target.value)}
              maxLength={50}
              className="input-field w-full mt-1 text-sm"
            />
          </label>
        </div>
      </section>

      <DocumentPicker
        label="Photo of your ID"
        hint="A clear photo or a PDF scan. Up to 10MB."
        files={documents}
        uploading={uploading === "documents"}
        onPick={onPickDocuments}
        onRemove={(key) =>
          setDocuments((prev) => prev.filter((d) => d.key !== key))
        }
        accept={ACCEPT}
        multiple
      />

      <DocumentPicker
        label="Photo of your vehicle"
        hint="So an admin can check it is roadworthy."
        files={equipmentPhoto ? [equipmentPhoto] : []}
        uploading={uploading === "equipment"}
        onPick={(files) => onPickEquipment(files?.[0] ?? null)}
        onRemove={() => setEquipmentPhoto(null)}
        accept="image/jpeg,image/png,image/webp"
      />

      <button
        onClick={() => submit.mutate()}
        disabled={!readyToSubmit || submit.isPending || uploading !== null}
        className="btn-accent w-full py-3 rounded-lg font-semibold disabled:opacity-50"
      >
        {submit.isPending ? "Sending…" : "Send for review"}
      </button>
      {!readyToSubmit && (
        <p className="text-xs text-muted text-center -mt-3">
          Choose your vehicle, enter your ID number and add a photo of your ID.
        </p>
      )}
    </div>
  );
}

function StatusPanel({ data }: { data: RiderKYC }) {
  const identity: Record<string, { label: string; cls: string; note: string }> = {
    pending_review: {
      label: "ID under review",
      cls: "bg-amber/15 text-gold",
      note: "An admin is checking your ID.",
    },
    approved: {
      label: "ID approved",
      cls: "bg-success/10 text-success",
      note: "Your identity has been checked.",
    },
    rejected: {
      label: "ID rejected",
      cls: "bg-danger/10 text-danger",
      note: data.kyc_review_notes ?? "Send new details to try again.",
    },
  };
  const id = identity[data.kyc_status] ?? identity.pending_review;

  return (
    <section className="space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-xs font-semibold text-muted w-20">Your ID</span>
        <span className={`text-xs font-medium px-2 py-1 rounded-full ${id.cls}`}>
          {id.label}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-xs font-semibold text-muted w-20">Vehicle</span>
        <span
          className={`text-xs font-medium px-2 py-1 rounded-full ${
            data.equipment_verified
              ? "bg-success/10 text-success"
              : "bg-surface text-muted"
          }`}
        >
          {data.equipment_verified ? "Verified" : "Not yet verified"}
        </span>
      </div>
      <p className="text-xs text-muted pt-1">
        Both are checked separately. You can go online once each is done and your
        location is on.
      </p>
      {data.equipment_review_notes && !data.equipment_verified && (
        <p className="text-xs text-danger">
          Vehicle: {data.equipment_review_notes}
        </p>
      )}
    </section>
  );
}

function DocumentPicker({
  label,
  hint,
  files,
  uploading,
  onPick,
  onRemove,
  accept,
  multiple = false,
}: {
  label: string;
  hint: string;
  files: Uploaded[];
  uploading: boolean;
  onPick: (files: FileList | null) => void;
  onRemove: (key: string | null) => void;
  accept: string;
  multiple?: boolean;
}) {
  const input = useRef<HTMLInputElement>(null);

  return (
    <section>
      <h2 className="text-sm font-bold mb-1">{label}</h2>
      <p className="text-xs text-muted mb-2">{hint}</p>

      {files.length > 0 && (
        <ul className="space-y-1.5 mb-2">
          {files.map((f) => (
            <li
              key={f.key ?? f.filename}
              className="flex items-center justify-between gap-2 text-xs bg-surface-2 rounded-md px-3 py-2"
            >
              <span className="flex items-center gap-1.5 min-w-0">
                <Check size={13} className="text-success shrink-0" />
                <span className="truncate">{f.filename}</span>
              </span>
              <button
                onClick={() => onRemove(f.key)}
                aria-label={`Remove ${f.filename}`}
                className="text-muted hover:text-danger shrink-0"
              >
                <X size={14} />
              </button>
            </li>
          ))}
        </ul>
      )}

      <input
        ref={input}
        type="file"
        accept={accept}
        multiple={multiple}
        className="hidden"
        onChange={(e) => {
          onPick(e.target.files);
          // Clearing the value lets the same file be re-picked after a removal.
          e.target.value = "";
        }}
      />
      <button
        onClick={() => input.current?.click()}
        disabled={uploading}
        className="w-full flex items-center justify-center gap-2 py-3 rounded-lg border border-dashed border-border text-xs font-medium text-muted disabled:opacity-50"
      >
        {uploading ? (
          <>
            <Loader2 size={14} className="animate-spin" /> Uploading…
          </>
        ) : (
          <>
            <Upload size={14} /> {files.length > 0 ? "Add another" : "Choose file"}
          </>
        )}
      </button>
    </section>
  );
}