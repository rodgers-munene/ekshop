import type { Key } from "react";
import { formatKES } from "@/lib/utils";
import type { DrillColumn } from "@/components/admin/StatDrillDown";

export interface DrillSpec {
  title: string;
  subtitle?: string;
  queryUrl?: string;
  rows?: any[];
  columns: DrillColumn[];
  rowKey: (row: any, index: number) => Key;
  emptyText?: string;
  href?: string;
  hrefLabel?: string;
}

const shortDate = (v: string) =>
  new Date(v).toLocaleDateString("en-KE", { day: "numeric", month: "short", year: "numeric" });

export const orderColumns: DrillColumn[] = [
  {
    key: "created",
    label: "Placed",
    render: (r) => <span className="whitespace-nowrap">{shortDate(r.created_at)}</span>,
  },
  { key: "id", label: "Order", render: (r) => <span className="font-mono text-xs">{r.short_id}</span> },
  { key: "buyer", label: "Buyer", render: (r) => r.buyer_name },
  { key: "shops", label: "Shops", align: "right", render: (r) => r.shop_count },
  { key: "items", label: "Items", align: "right", render: (r) => r.item_count },
  { key: "total", label: "Total", align: "right", render: (r) => <strong>{formatKES(r.total)}</strong> },
];

export const userColumns: DrillColumn[] = [
  { key: "name", label: "Name", render: (r) => `${r.first_name} ${r.last_name}` },
  { key: "email", label: "Email", render: (r) => <span className="text-xs">{r.email}</span> },
  { key: "role", label: "Role", render: (r) => r.role },
  { key: "status", label: "Status", render: (r) => r.status },
  { key: "joined", label: "Joined", align: "right", render: (r) => <span className="whitespace-nowrap">{shortDate(r.created_at)}</span> },
];

export const shopColumns: DrillColumn[] = [
  { key: "name", label: "Shop", render: (r) => <span className="font-medium">{r.name}</span> },
  {
    key: "location",
    label: "Location",
    render: (r) => [r.town, r.subcounty, r.county].filter(Boolean).join(", ") || "—",
  },
  { key: "status", label: "Status", render: (r) => r.status },
  { key: "created", label: "Joined", align: "right", render: (r) => <span className="whitespace-nowrap">{shortDate(r.created_at)}</span> },
];

export const productColumns: DrillColumn[] = [
  { key: "name", label: "Product", render: (r) => <span className="font-medium">{r.name}</span> },
  { key: "shop", label: "Shop", render: (r) => r.shop_name || "—" },
  { key: "price", label: "Price", align: "right", render: (r) => formatKES(r.price) },
  { key: "status", label: "Status", render: (r) => r.status },
  { key: "created", label: "Added", align: "right", render: (r) => <span className="whitespace-nowrap">{shortDate(r.created_at)}</span> },
];

export function ordersSpec(period?: string): DrillSpec {
  const qs = period ? `?period=${period}` : "";
  return {
    title: "Paid orders",
    subtitle: "Recent paid order groups" + (period ? ` in the selected window` : " — all time"),
    queryUrl: `/api/admin/orders${qs}`,
    columns: orderColumns,
    rowKey: (r) => r.id,
    emptyText: "No paid orders matched this window.",
  };
}

export function usersSpec(role?: "buyer" | "seller", title?: string): DrillSpec {
  const qs = role ? `?role=${role}&page=1&limit=50` : `?page=1&limit=50`;
  return {
    title: title ?? (role ? `${role[0].toUpperCase()}${role.slice(1)}s` : "Users"),
    subtitle: "Latest signups",
    queryUrl: `/api/admin/users${qs}`,
    columns: userColumns,
    rowKey: (r) => r.id,
    emptyText: "No users found.",
    href: "/admin/users",
    hrefLabel: "Open Users page",
  };
}

export function shopsSpec(status?: "pending" | "active" | "suspended", title?: string): DrillSpec {
  const qs = status ? `?status=${status}&page=1&limit=50` : `?page=1&limit=50`;
  return {
    title: title ?? "Shops",
    subtitle: "Latest shops" + (status ? ` — ${status} status` : ""),
    queryUrl: `/api/admin/shops${qs}`,
    columns: shopColumns,
    rowKey: (r) => r.id,
    emptyText: `No shops with ${status ?? "any"} status found.`,
    href: "/admin/sellers",
    hrefLabel: "Open Sellers page",
  };
}

export function productsSpec(): DrillSpec {
  return {
    title: "Products",
    subtitle: "Latest products across all shops",
    queryUrl: `/api/admin/products?page=1&limit=50`,
    columns: productColumns,
    rowKey: (r) => r.id,
    emptyText: "No products found.",
  };
}

/** Pass-through that keeps a DrillSpec's columns/keys but overrides just the
 * rows and title — used by Analytics sections that already have the matrix
 * loaded (e.g. merchant cards → merchant-master rows). */
export function rowsSpec(base: DrillSpec, rows: any[]): DrillSpec {
  return { ...base, rows, queryUrl: undefined };
}

const fmtDateTime = (v?: string | null) =>
  v ? new Date(v).toLocaleString("en-KE", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "—";

export const merchantMasterColumns: DrillColumn[] = [
  { key: "merchant", label: "Merchant", render: (r) => <span className="font-medium">{r.merchant}</span> },
  { key: "location", label: "Location", render: (r) => r.location || "—" },
  { key: "stage", label: "Stage", render: (r) => r.stage },
  { key: "health", label: "Health", align: "right", render: (r) => <strong>{r.health}</strong> },
  { key: "tier", label: "Tier", render: (r) => r.health_tier },
  { key: "orders", label: "Orders 30d", align: "right", render: (r) => r.orders_30d },
  { key: "last", label: "Last login", render: (r) => <span className="text-xs">{fmtDateTime(r.last_login)}</span> },
  { key: "next", label: "Next action", render: (r) => r.next_action },
  { key: "owner", label: "Owner", render: (r) => r.owner },
];

export const orderTowerColumns: DrillColumn[] = [
  { key: "id", label: "Order", render: (r) => <span className="font-mono text-xs">{r.order_id.slice(0, 8)}</span> },
  { key: "received", label: "Received", render: (r) => <span className="whitespace-nowrap text-xs">{fmtDateTime(r.received)}</span> },
  { key: "merchant", label: "Merchant", render: (r) => r.merchant },
  { key: "customer", label: "Customer", render: (r) => r.customer },
  { key: "status", label: "Status", render: (r) => r.status },
  { key: "dispatch", label: "Dispatch h", align: "right", render: (r) => r.dispatch_hrs },
  { key: "delivery", label: "Delivery h", align: "right", render: (r) => r.delivery_hrs },
  { key: "exception", label: "Exception / owner", render: (r) => r.exception_owner || "—" },
];

export const customerRecoveryColumns: DrillColumn[] = [
  { key: "customer", label: "Customer", render: (r) => <span className="font-medium">{r.customer}</span> },
  { key: "segment", label: "Segment", render: (r) => r.segment },
  { key: "value", label: "Cart value", align: "right", render: (r) => formatKES(r.cart_value) },
  { key: "channel", label: "Channel", render: (r) => r.channel || "—" },
  { key: "response", label: "Response", render: (r) => r.response || "—" },
  { key: "recovered", label: "Recovered?", render: (r) => (r.recovered_order ? "Yes" : "No") },
  { key: "next", label: "Next action", render: (r) => r.next_action },
];

export const abandonedProductColumns: DrillColumn[] = [
  { key: "name", label: "Product", render: (r) => <span className="font-medium">{r.name}</span> },
  { key: "units", label: "Units", align: "right", render: (r) => r.units },
  { key: "value", label: "At-risk value", align: "right", render: (r) => formatKES(r.at_risk_revenue) },
];

export const topProductColumns: DrillColumn[] = [
  { key: "name", label: "Product", render: (r) => <span className="font-medium">{r.name}</span> },
  { key: "units", label: "Units", align: "right", render: (r) => r.units },
  { key: "revenue", label: "Revenue", align: "right", render: (r) => formatKES(r.revenue) },
];

export const merchantMasterSpec = (rows: any[]) =>
  rowsSpec({ title: "Merchant health", subtitle: "Merchant Master matrix for the selected window", rows, columns: merchantMasterColumns, rowKey: (r, i) => `${r.merchant}-${i}`, emptyText: "No merchant rows for this window." }, rows);

export const orderTowerSpec = (rows: any[]) =>
  rowsSpec({ title: "Order control tower", subtitle: "Order-by-order dispatch & delivery timeline", rows, columns: orderTowerColumns, rowKey: (r) => r.order_id, emptyText: "No orders for this window." }, rows);

export const customerRecoverySpec = (rows: any[]) =>
  rowsSpec({ title: "Customer recovery", subtitle: "Customers needing follow-up in this window", rows, columns: customerRecoveryColumns, rowKey: (r, i) => `${r.customer}-${i}`, emptyText: "No customers matched." }, rows);

export const abandonedSpec = (rows: any[], title = "Abandoned products") =>
  rowsSpec({ title, subtitle: "Items sitting in abandoned carts", rows, columns: abandonedProductColumns, rowKey: (r, i) => `${r.name}-${i}`, emptyText: "No abandoned products." }, rows);

export const topProductsSpec = (rows: any[], title = "Top purchased products") =>
  rowsSpec({ title, subtitle: "Best sellers in this window", rows, columns: topProductColumns, rowKey: (r, i) => `${r.name}-${i}`, emptyText: "No purchases." }, rows);