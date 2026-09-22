"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { formatKES } from "@/lib/utils";

interface InvoiceItem {
  name: string;
  qty: number;
  unit_price: string;
  subtotal: string;
}

interface Invoice {
  invoice_id: string;
  order_id: string;
  created_at: string;
  customer_name: string;
  delivery_address: string;
  payment_reference: string | null;
  payment_status: string;
  items: InvoiceItem[];
  subtotal: string;
  delivery_fee: string;
  total: string;
  currency: string;
}

export default function CustomerInvoicePage() {
  const params = useParams();
  const orderId = params?.orderId as string;
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!orderId) return;
    setLoading(true);
    fetch(`/api/invoices/${orderId}`)
      .then((r) => {
        if (!r.ok) throw new Error("Failed to load invoice");
        return r.json();
      })
      .then(setInvoice)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [orderId]);

  const printInvoice = () => {
    window.print();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber" />
      </div>
    );
  }

  if (error || !invoice) {
    return (
      <div className="card p-6 text-center">
        <p className="font-bold mb-1">Invoice unavailable</p>
        <p className="text-sm text-muted">{error || "We could not load this invoice."}</p>
      </div>
    );
  }

  const subtotal = Number(invoice.subtotal || "0");
  const deliveryFee = Number(invoice.delivery_fee || "0");
  const total = Number(invoice.total || "0");

  return (
    <div className="max-w-2xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Invoice</h1>
          <p className="text-sm text-muted">{invoice.invoice_id}</p>
        </div>
        <button onClick={printInvoice} className="btn-accent text-sm">
          Download / Print
        </button>
      </div>

      <div className="card p-6 space-y-4">
        <div className="flex items-start justify-between">
          <div>
            <p className="font-bold">Ekshop Kenya</p>
            <p className="text-xs text-muted">Hyperlocal Marketplace</p>
          </div>
          <div className="text-right">
            <p className="text-xs text-muted">Date</p>
            <p className="text-sm font-medium">{new Date(invoice.created_at).toLocaleDateString("en-KE")}</p>
          </div>
        </div>

        <div className="border-t border-border pt-4 space-y-1">
          <p className="text-xs text-muted">Customer</p>
          <p className="font-medium">{invoice.customer_name}</p>
          <p className="text-sm text-muted">{invoice.delivery_address}</p>
        </div>

        <div className="border-t border-border pt-4">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-xs text-muted border-b">
                <tr>
                  <th className="text-left py-2">Item</th>
                  <th className="text-right py-2">Qty</th>
                  <th className="text-right py-2">Unit Price</th>
                  <th className="text-right py-2">Subtotal</th>
                </tr>
              </thead>
              <tbody>
                {invoice.items.map((item, idx) => (
                  <tr key={idx} className="border-b last:border-0">
                    <td className="py-2">{item.name}</td>
                    <td className="py-2 text-right tabular-nums">{item.qty}</td>
                    <td className="py-2 text-right tabular-nums">{formatKES(Number(item.unit_price))}</td>
                    <td className="py-2 text-right tabular-nums">{formatKES(Number(item.subtotal))}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="border-t border-border pt-4 space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-muted">Subtotal</span>
            <span className="tabular-nums">{formatKES(subtotal)}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-muted">Delivery fee</span>
            <span className="tabular-nums">{formatKES(deliveryFee)}</span>
          </div>
          <div className="flex justify-between font-bold text-base">
            <span>Total paid</span>
            <span className="tabular-nums">{formatKES(total)}</span>
          </div>
        </div>

        <div className="border-t border-border pt-4 space-y-1">
          <p className="text-xs text-muted">Payment</p>
          <p className="text-sm">Status: <span className="font-medium capitalize">{invoice.payment_status}</span></p>
          {invoice.payment_reference && (
            <p className="text-xs text-muted">Reference: {invoice.payment_reference}</p>
          )}
        </div>
      </div>
    </div>
  );
}
