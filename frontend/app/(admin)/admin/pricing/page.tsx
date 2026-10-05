"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { AlertTriangle, Loader2, Save } from "lucide-react";
import {
  PricingParameterListResponse,
  PricingParameterRead,
} from "@/types/interface";

/**
 * The pricing parameters an admin can change without a deployment (§15).
 *
 * Two things this screen does deliberately, because they are what stops a
 * placeholder being mistaken for an agreed number:
 *
 * - It shows `placeholder_count` from the API as a banner. Three seeded values are
 *   explicitly unverified: the payment-processing rate, the failure probability
 *   and the average failure cost. The specification says to measure all three, and
 *   until someone does, every margin on the platform rests on invented numbers.
 * - It marks the commercial decisions separately from the rates. Q23 -- whether
 *   the customer pays for the rider's trip to the merchant -- is not a rate to be
 *   tuned, it is a pricing policy that decides whether short deliveries make money
 *   at all. It is flagged so nobody flips it casually.
 *
 * Values are validated on the backend before saving, so a typo is rejected here
 * rather than becoming a pricing failure on the next quote.
 */

export default function AdminPricingParametersPage() {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [savingKey, setSavingKey] = useState<string | null>(null);

  const { data, isPending, isError } = useQuery({
    queryKey: ["admin", "pricing-parameters"],
    queryFn: async () => {
      const res = await fetch("/api/pricing");
      if (!res.ok) throw new Error();
      return (await res.json()) as PricingParameterListResponse;
    },
  });

  const update = useMutation({
    mutationFn: async ({ key, value }: { key: string; value: string }) => {
      const res = await fetch(`/api/pricing/parameters/${key}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value, reason: "Changed from the admin pricing screen" }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.detail ?? "Could not save that value");
      return body as PricingParameterRead;
    },
    onSuccess: (saved) => {
      queryClient.invalidateQueries({ queryKey: ["admin", "pricing-parameters"] });
      setDraft((d) => {
        const next = { ...d };
        delete next[saved.key];
        return next;
      });
      toast.success(`Saved ${saved.key}`);
    },
    onError: (error: Error) => toast.error(error.message),
    onSettled: () => setSavingKey(null),
  });

  if (isPending) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="animate-spin text-gold" size={24} />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="card flex flex-col items-center justify-center py-16 text-center">
        <p className="font-bold mb-1">Could not load pricing parameters</p>
        <p className="text-sm text-muted">Please refresh and try again.</p>
      </div>
    );
  }

  const parameters = data.items;
  const rates = parameters.filter((p) => !p.is_commercial_decision);
  const decisions = parameters.filter((p) => p.is_commercial_decision);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Delivery pricing</h1>
        <p className="text-sm text-muted mt-1">
          Rates used by the pricing engine. Changes take effect on the next quote
          and do not alter orders already priced.
        </p>
      </div>

      {data.placeholder_count > 0 && (
        <div className="card p-4 border-amber">
          <div className="flex items-start gap-3">
            <AlertTriangle size={18} className="text-gold mt-0.5 shrink-0" />
            <div>
              <p className="font-bold text-sm">
                {data.placeholder_count} values are placeholders, not agreed
                figures
              </p>
              <p className="text-xs text-muted mt-1">
                The specification says to seed the payment-processing rate and the
                failure figures from measured data. Until that is done, every
                margin figure the platform reports rests on invented numbers.
                They are marked below.
              </p>
            </div>
          </div>
        </div>
      )}

      <ParameterTable
        title="Rates"
        subtitle="Tuned by finance as real costs become known."
        parameters={rates}
        draft={draft}
        setDraft={setDraft}
        onSave={(key, value) => {
          setSavingKey(key);
          update.mutate({ key, value });
        }}
        savingKey={savingKey}
      />

      <ParameterTable
        title="Commercial decisions"
        subtitle="Not rates. Each of these decides how the platform makes money and needs a decision, not a tweak."
        parameters={decisions}
        draft={draft}
        setDraft={setDraft}
        onSave={(key, value) => {
          setSavingKey(key);
          update.mutate({ key, value });
        }}
        savingKey={savingKey}
        highlight
      />

      <p className="text-xs text-muted">
        Pricing version <span className="font-mono">{data.pricing_version}</span>.
        Every calculation is stored against the version it used, so changing a rate
        here never rewrites the economics of an order that has already been quoted.
      </p>
    </div>
  );
}

function ParameterTable({
  title,
  subtitle,
  parameters,
  draft,
  setDraft,
  onSave,
  savingKey,
  highlight,
}: {
  title: string;
  subtitle: string;
  parameters: PricingParameterRead[];
  draft: Record<string, string>;
  setDraft: (fn: (d: Record<string, string>) => Record<string, string>) => void;
  onSave: (key: string, value: string) => void;
  savingKey: string | null;
  highlight?: boolean;
}) {
  if (parameters.length === 0) return null;

  return (
    <div>
      <h2 className="text-sm font-bold">{title}</h2>
      <p className="text-xs text-muted mt-0.5 mb-3">{subtitle}</p>
      <div className="card overflow-hidden overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs text-muted">
              <th className="px-4 py-3 font-medium">Parameter</th>
              <th className="px-4 py-3 font-medium">Value</th>
              <th className="px-4 py-3 font-medium">Notes</th>
              <th className="px-4 py-3 font-medium"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {parameters.map((parameter) => {
              const current = draft[parameter.key] ?? parameter.value;
              const isPlaceholder = (parameter.description ?? "").includes("PLACEHOLDER");
              const dirty = draft[parameter.key] !== undefined &&
                draft[parameter.key] !== parameter.value;
              const step =
                parameter.value_type === "rate"
                  ? "0.01"
                  : parameter.value_type === "money"
                    ? "0.01"
                    : parameter.value_type === "integer"
                      ? "1"
                      : undefined;

              return (
                <tr key={parameter.key} className={highlight ? "bg-amber/5" : undefined}>
                  <td className="px-4 py-3">
                    <span className="font-mono text-xs">{parameter.key}</span>
                    {parameter.spec_reference && (
                      <span className="block text-xs text-muted mt-0.5">
                        {parameter.spec_reference}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {parameter.value_type === "boolean" ? (
                      <select
                        value={current}
                        onChange={(e) =>
                          setDraft((d) => ({ ...d, [parameter.key]: e.target.value }))
                        }
                        className="input-field"
                      >
                        <option value="true">On</option>
                        <option value="false">Off</option>
                      </select>
                    ) : (
                      <input
                        type="number"
                        step={step}
                        value={current}
                        onChange={(e) =>
                          setDraft((d) => ({ ...d, [parameter.key]: e.target.value }))
                        }
                        className="input-field"
                      />
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-muted max-w-xs">
                    {parameter.description}
                    {isPlaceholder && (
                      <span className="block mt-1 text-gold font-medium">
                        Placeholder — needs real data
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {dirty && (
                      <button
                        onClick={() => onSave(parameter.key, current)}
                        disabled={savingKey === parameter.key}
                        className="btn-accent px-3 py-1.5 rounded-lg text-xs font-medium inline-flex items-center gap-1.5 disabled:opacity-50"
                      >
                        {savingKey === parameter.key ? (
                          <Loader2 size={12} className="animate-spin" />
                        ) : (
                          <Save size={12} />
                        )}
                        Save
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}