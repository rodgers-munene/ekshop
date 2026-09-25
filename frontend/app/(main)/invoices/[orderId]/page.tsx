"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { formatKES } from "@/lib/utils";
import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";

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

  const downloadPdf = () => {
    if (!invoice) return;
    const doc = new jsPDF();
    doc.setFontSize(18);
    doc.text("EKSHOP KENYA", 14, 18);
    doc.setFontSize(10);
    doc.text("Official Purchase Receipt", 14, 24);
    doc.text(`Invoice: ${invoice.invoice_id}`, 14, 30);
    doc.text(`Order:   ${invoice.order_id.slice(0, 8)}`, 14, 36);
    doc.text(`Date:    ${new Date(invoice.created_at).toLocaleDateString("en-KE")}`, 14, 42);

    doc.text("Customer", 14, 52);
    doc.text(invoice.customer_name, 14, 58);
    doc.text(invoice.delivery_address || "—", 14, 64);

    doc.text("Payment", 14, 74);
    doc.text(`Status: ${invoice.payment_status}`, 14, 80);
    doc.text(`Reference: ${invoice.payment_reference || "—"}`, 14, 86);

    const rows = invoice.items.map((it) => [
      it.name,
      String(it.qty),
      `KES ${Number(it.unit_price).toFixed(2)}`,
      `KES ${Number(it.subtotal).toFixed(2)}`,
    ]);
    autoTable(doc, {
      startY: 94,
      head: [["Item", "Qty", "Unit price", "Subtotal"]],
      body: rows,
      theme: "grid",
      headStyles: { fillColor: [15, 23, 42] },
    });

    const finalY = (doc as unknown as { lastAutoTable: { finalY: number } }).lastAutoTable.finalY + 10;
    doc.text(`Subtotal:      KES ${Number(invoice.subtotal).toFixed(2)}`, 14, finalY);
    doc.text(`Delivery fee:  KES ${Number(invoice.delivery_fee).toFixed(2)}`, 14, finalY + 6);
    doc.text(`Total paid:    KES ${Number(invoice.total).toFixed(2)}`, 14, finalY + 14);
    doc.save(`ekshop-invoice-${invoice.order_id.slice(0, 8)}.pdf`);
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

  return (
    <div className="max-w-2xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Invoice</h1>
          <p className="text-sm text-muted">{invoice.invoice_id}</p>
        </div>
        <button onClick={downloadPdf} className="btn-accent text-sm">
          Download PDF
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
            <span className="tabular-nums">{formatKES(Number(invoice.subtotal))}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-muted">Delivery fee</span>
            <span className="tabular-nums">{formatKES(Number(invoice.delivery_fee))}</span>
          </div>
          <div className="flex justify-between font-bold text-base">
            <span>Total paid</span>
            <span className="tabular-nums">{formatKES(Number(invoice.total))}</span>
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
