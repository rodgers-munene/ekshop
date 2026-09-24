"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  FileSpreadsheet,
  Loader2,
  RefreshCw,
  Upload,
} from "lucide-react";
import {
  Category,
  DuplicateAction,
  ImportCommitResult,
  ImportPreview,
  ProductImportRow,
} from "@/types/interface";
import { formatKES } from "@/lib/utils";

/** Rows per commit call. 500 is the backend's default and its sweet spot: big
    enough that 9,000 rows is 19 requests, small enough that each one returns
    fast and a failure loses little. */
const BATCH_SIZE = 500;

const DUPLICATE_OPTIONS: { value: DuplicateAction; label: string; hint: string }[] = [
  {
    value: "update_stock_price",
    label: "Update stock and price",
    hint: "Keeps the name, photos and description you already have.",
  },
  {
    value: "skip",
    label: "Leave them alone",
    hint: "Only brand-new codes are added.",
  },
  {
    value: "create_new",
    label: "Add as separate products",
    hint: "You'll end up with two of each. Rarely what you want.",
  },
];

function flattenCategories(categories: Category[], depth = 0): { id: string; label: string }[] {
  return categories.flatMap((c) => [
    { id: c.id, label: `${"  ".repeat(depth)}${depth > 0 ? "› " : ""}${c.name}` },
    ...flattenCategories(c.children ?? [], depth + 1),
  ]);
}

function Counter({
  value,
  label,
  tone = "plain",
}: {
  value: number;
  label: string;
  tone?: "plain" | "good" | "warn" | "bad";
}) {
  const tones = {
    plain: "text-ink",
    good: "text-success",
    warn: "text-amber",
    bad: "text-danger",
  };
  return (
    <div className="rounded-lg bg-surface px-3 py-2.5">
      <p className={`text-xl font-bold ${tones[tone]}`}>{value.toLocaleString()}</p>
      <p className="text-[11px] text-muted leading-tight mt-0.5">{label}</p>
    </div>
  );
}

function RowTable({ rows, showError }: { rows: ProductImportRow[]; showError?: boolean }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs text-muted">
            <th className="px-3 py-2 font-medium">Row</th>
            <th className="px-3 py-2 font-medium">Code</th>
            <th className="px-3 py-2 font-medium">Name</th>
            <th className="px-3 py-2 font-medium">Price</th>
            <th className="px-3 py-2 font-medium">Stock</th>
            <th className="px-3 py-2 font-medium">{showError ? "Problem" : "Brand"}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map((row) => (
            <tr key={row.id}>
              <td className="px-3 py-2 text-muted tabular-nums">{row.row_number}</td>
              <td className="px-3 py-2 font-mono text-xs">{row.sku || "—"}</td>
              <td className="px-3 py-2">
                {row.name || <span className="text-muted">—</span>}
                {row.matched_product_id && (
                  <span className="ml-2 text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-amber/15 text-amber">
                    already listed
                  </span>
                )}
              </td>
              <td className="px-3 py-2 tabular-nums">{row.price ? formatKES(row.price) : "—"}</td>
              <td className="px-3 py-2 tabular-nums">{row.stock_qty ?? "—"}</td>
              <td className={`px-3 py-2 text-xs ${showError ? "text-danger" : "text-muted"}`}>
                {showError ? row.error : row.brand || "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function BulkImportWizard({ categories }: { categories: Category[] }) {
  const router = useRouter();
  const fileInput = useRef<HTMLInputElement>(null);

  const [uploading, setUploading] = useState(false);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [categoryId, setCategoryId] = useState("");
  const [onDuplicate, setOnDuplicate] = useState<DuplicateAction>("update_stock_price");
  const [showProblems, setShowProblems] = useState(false);

  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState<ImportCommitResult | null>(null);
  const [done, setDone] = useState(false);
  const cancelled = useRef(false);

  const flatCategories = flattenCategories(categories);
  // The spreadsheet this was built for is all cosmetics, and it's the common
  // case, so the obvious category is pre-selected rather than left blank. The
  // conjunction is optional because the live catalogue spells it "Health
  // Beauty" — and this is only a default, so a miss costs the seller one click.
  const suggested = flatCategories.find((c) =>
    /health\s*(and\s*|&\s*)?beauty/i.test(c.label),
  );

  async function upload(file: File) {
    if (!/\.xlsx?$/i.test(file.name)) {
      toast.error("Upload a .xlsx spreadsheet");
      return;
    }
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch("/api/dashboard/products/import", {
        method: "POST",
        body: formData,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        toast.error(data.detail ?? "Could not read that spreadsheet");
        return;
      }
      setPreview(data as ImportPreview);
      setCategoryId(suggested?.id ?? "");
      if ((data as ImportPreview).valid_rows === 0) {
        toast.error("Nothing in that file could be imported");
      }
    } catch {
      toast.error("Upload failed. Check your connection and try again.");
    } finally {
      setUploading(false);
    }
  }

  async function discard() {
    if (!preview) return;
    const id = preview.id;
    setPreview(null);
    setProgress(null);
    setDone(false);
    if (fileInput.current) fileInput.current.value = "";
    // Best effort: the staged rows are harmless if this fails, and the seller
    // has already moved on.
    await fetch(`/api/dashboard/products/import/${id}`, { method: "DELETE" }).catch(() => {});
  }

  /** Drives the commit loop. The backend does one batch per call and tells us
      what's left, so progress here is what actually landed, not a guess. */
  async function run() {
    if (!preview) return;
    if (!categoryId) {
      toast.error("Pick a category for these products");
      return;
    }

    cancelled.current = false;
    setRunning(true);
    setDone(false);

    let guard = 0;
    const maxCalls = Math.ceil(preview.valid_rows / BATCH_SIZE) + 5;

    try {
      for (;;) {
        if (cancelled.current) break;
        // A stuck backend that stopped decrementing `remaining` would otherwise
        // spin this loop forever against the API.
        if (guard++ > maxCalls) {
          toast.error("Import stalled. Reopen it from the products page to resume.");
          break;
        }

        const res = await fetch(`/api/dashboard/products/import/${preview.id}/commit`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            category_id: categoryId,
            on_duplicate: onDuplicate,
            limit: BATCH_SIZE,
          }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          toast.error(data.detail ?? "That batch failed. Try again to resume.");
          break;
        }

        const result = data as ImportCommitResult;
        setProgress(result);
        if (result.remaining <= 0) {
          setDone(true);
          break;
        }
      }
    } catch {
      toast.error("Lost connection mid-import. Try again — it picks up where it stopped.");
    } finally {
      setRunning(false);
    }
  }

  // ---- step 1: pick a file -------------------------------------------------
  if (!preview) {
    return (
      <div className="space-y-4">
        <div className="card p-6">
          <input
            ref={fileInput}
            type="file"
            accept=".xlsx,.xls,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) upload(file);
            }}
          />
          <button
            type="button"
            disabled={uploading}
            onClick={() => fileInput.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              const file = e.dataTransfer.files?.[0];
              if (file) upload(file);
            }}
            className="w-full flex flex-col items-center justify-center gap-3 py-12 px-4 rounded-lg border-2 border-dashed border-border hover:border-amber hover:bg-surface/60 transition-colors disabled:opacity-60"
          >
            {uploading ? (
              <>
                <Loader2 size={28} className="text-amber animate-spin" />
                <span className="font-semibold text-sm">Reading your spreadsheet…</span>
                <span className="text-xs text-muted">Large files take a few seconds.</span>
              </>
            ) : (
              <>
                <Upload size={28} className="text-muted" />
                <span className="font-semibold text-sm">Choose a spreadsheet, or drop one here</span>
                <span className="text-xs text-muted">.xlsx, up to 10MB and 20,000 rows</span>
              </>
            )}
          </button>
        </div>

        <div className="card p-5">
          <h2 className="font-semibold text-sm mb-2">What the columns should say</h2>
          <p className="text-sm text-muted mb-3">
            Your sheet needs a <strong className="text-ink">name</strong> column and a{" "}
            <strong className="text-ink">price</strong> column. A code, a stock balance and a brand
            are used if they&apos;re there. Headers are matched loosely, so most stock exports work
            untouched — <em>Description</em>, <em>Balance</em> and <em>SellingPrice</em> are all
            recognised.
          </p>
          {/* A real <a>, not <Link>: this is a route handler that streams a
              file back, so a client-side navigation has nothing to render. */}
          <a
            href="/api/dashboard/products/import/template"
            download
            className="btn-outline text-sm py-2! px-4! inline-flex"
          >
            <Download size={15} /> Download a blank template
          </a>
        </div>
      </div>
    );
  }

  // ---- step 3: importing / done -------------------------------------------
  if (running || done || progress) {
    const total = preview.valid_rows;
    const landed =
      (progress?.created_count ?? 0) +
      (progress?.updated_count ?? 0) +
      (progress?.skipped_count ?? 0) +
      (progress?.failed_count ?? 0);
    const pct = total > 0 ? Math.min(100, Math.round((landed / total) * 100)) : 0;

    return (
      <div className="card p-6">
        <div className="flex items-start gap-3 mb-5">
          {done ? (
            <CheckCircle2 size={22} className="text-success shrink-0 mt-0.5" />
          ) : (
            <Loader2 size={22} className="text-amber shrink-0 mt-0.5 animate-spin" />
          )}
          <div>
            <h2 className="font-bold">
              {done ? "Import finished" : running ? "Importing…" : "Import paused"}
            </h2>
            <p className="text-sm text-muted mt-0.5">
              {done
                ? "Everything landed as a draft. Review them, then publish the ones you want live."
                : running
                  ? "Keep this tab open. Closing it stops the import — it resumes from where it stopped."
                  : "Nothing was lost. Start it again to carry on from here."}
            </p>
          </div>
        </div>

        <div className="h-2 rounded-full bg-surface overflow-hidden mb-2">
          <div
            className={`h-full rounded-full transition-[width] duration-300 ${done ? "bg-success" : "bg-amber"}`}
            style={{ width: `${pct}%` }}
          />
        </div>
        <p className="text-xs text-muted mb-5 tabular-nums">
          {landed.toLocaleString()} of {total.toLocaleString()} rows · {pct}%
        </p>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-6">
          <Counter value={progress?.created_count ?? 0} label="Created as drafts" tone="good" />
          <Counter value={progress?.updated_count ?? 0} label="Stock & price updated" />
          <Counter value={progress?.skipped_count ?? 0} label="Left alone" />
          <Counter
            value={progress?.failed_count ?? 0}
            label="Failed"
            tone={progress?.failed_count ? "bad" : "plain"}
          />
        </div>

        <div className="flex flex-wrap gap-2">
          {done ? (
            <>
              <Link href="/dashboard/products?status=draft" className="btn-accent text-sm py-2! px-4!">
                Review the drafts
              </Link>
              <button
                type="button"
                onClick={() => {
                  setPreview(null);
                  setProgress(null);
                  setDone(false);
                  if (fileInput.current) fileInput.current.value = "";
                  router.refresh();
                }}
                className="btn-outline text-sm py-2! px-4!"
              >
                Import another file
              </button>
            </>
          ) : running ? (
            <button
              type="button"
              onClick={() => {
                cancelled.current = true;
              }}
              className="btn-outline text-sm py-2! px-4!"
            >
              Stop after this batch
            </button>
          ) : (
            <button type="button" onClick={run} className="btn-accent text-sm py-2! px-4!">
              <RefreshCw size={15} /> Carry on
            </button>
          )}
        </div>
      </div>
    );
  }

  // ---- step 2: review -----------------------------------------------------
  const brandNew = Math.max(0, preview.valid_rows - preview.matched_rows);
  const willImport =
    onDuplicate === "skip" ? brandNew : preview.valid_rows;

  return (
    <div className="space-y-4">
      <div className="card p-5">
        <div className="flex items-center gap-2.5 mb-4">
          <FileSpreadsheet size={18} className="text-muted shrink-0" />
          <p className="font-semibold text-sm truncate">{preview.filename}</p>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          <Counter value={preview.total_rows} label="Rows in the file" />
          <Counter value={brandNew} label="New products" tone="good" />
          <Counter
            value={preview.matched_rows}
            label="Codes you already list"
            tone={preview.matched_rows ? "warn" : "plain"}
          />
          <Counter
            value={preview.invalid_rows}
            label="Rows to be skipped"
            tone={preview.invalid_rows ? "bad" : "plain"}
          />
        </div>

        {preview.invalid_rows > 0 && (
          <button
            type="button"
            onClick={() => setShowProblems((s) => !s)}
            className="mt-3 text-xs text-amber underline underline-offset-2"
          >
            {showProblems ? "Hide" : "See"} what&apos;s wrong with the{" "}
            {preview.invalid_rows.toLocaleString()} skipped{" "}
            {preview.invalid_rows === 1 ? "row" : "rows"}
          </button>
        )}
      </div>

      {showProblems && preview.problems.length > 0 && (
        <div className="card overflow-hidden">
          <div className="flex items-start gap-2 px-4 py-3 border-b border-border bg-danger/5">
            <AlertTriangle size={15} className="text-danger shrink-0 mt-0.5" />
            <p className="text-xs text-muted">
              These rows won&apos;t be imported. The rest still will — fix these in the spreadsheet
              and upload it again if you need them.
            </p>
          </div>
          <RowTable rows={preview.problems} showError />
        </div>
      )}

      <div className="card p-5 space-y-5">
        <div>
          <label htmlFor="import-category" className="block text-sm font-medium mb-1.5">
            Category <span className="text-danger">*</span>
          </label>
          <select
            id="import-category"
            value={categoryId}
            onChange={(e) => setCategoryId(e.target.value)}
            className="input-field"
          >
            <option value="">Choose a category…</option>
            {flatCategories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.label}
              </option>
            ))}
          </select>
          <p className="text-xs text-muted mt-1.5">
            Every product in this file goes into one category. You can change individual ones
            afterwards.
          </p>
        </div>

        {preview.matched_rows > 0 && (
          <fieldset>
            <legend className="text-sm font-medium mb-1.5">
              {preview.matched_rows.toLocaleString()}{" "}
              {preview.matched_rows === 1 ? "code is" : "codes are"} already in your shop
            </legend>
            <div className="space-y-2 mt-2">
              {DUPLICATE_OPTIONS.map((opt) => (
                <label
                  key={opt.value}
                  className={`flex items-start gap-2.5 p-3 rounded-lg border cursor-pointer transition-colors ${
                    onDuplicate === opt.value
                      ? "border-amber bg-amber/5"
                      : "border-border hover:bg-surface"
                  }`}
                >
                  <input
                    type="radio"
                    name="on_duplicate"
                    value={opt.value}
                    checked={onDuplicate === opt.value}
                    onChange={() => setOnDuplicate(opt.value)}
                    className="mt-0.5 accent-amber"
                  />
                  <span>
                    <span className="block text-sm font-medium">{opt.label}</span>
                    <span className="block text-xs text-muted mt-0.5">{opt.hint}</span>
                  </span>
                </label>
              ))}
            </div>
          </fieldset>
        )}
      </div>

      {preview.sample.length > 0 && (
        <div className="card overflow-hidden">
          <div className="px-4 py-3 border-b border-border">
            <p className="text-sm font-semibold">
              First {preview.sample.length} of {preview.valid_rows.toLocaleString()} rows
            </p>
            <p className="text-xs text-muted mt-0.5">
              A spot check that the columns lined up. If the names and prices look wrong here,
              they&apos;ll be wrong for all of them.
            </p>
          </div>
          <RowTable rows={preview.sample} />
        </div>
      )}

      <div className="card p-4 flex flex-wrap items-center gap-3 sticky bottom-4">
        <button
          type="button"
          onClick={run}
          disabled={willImport === 0}
          className="btn-accent text-sm py-2.5! px-5! disabled:opacity-50"
        >
          Import {willImport.toLocaleString()}{" "}
          {willImport === 1 ? "product" : "products"} as drafts
        </button>
        <button type="button" onClick={discard} className="btn-outline text-sm py-2.5! px-4!">
          Start over
        </button>
        <p className="text-xs text-muted">Nothing goes live until you publish it.</p>
      </div>
    </div>
  );
}
