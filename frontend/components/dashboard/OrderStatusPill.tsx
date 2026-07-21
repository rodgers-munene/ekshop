const STATUS_STYLE: Record<string, string> = {
  pending: "bg-amber/15 text-amber",
  confirmed: "bg-info/10 text-info",
  processing: "bg-info/10 text-info",
  shipped: "bg-progress/10 text-progress",
  delivered: "bg-success/10 text-success",
  cancelled: "bg-danger/10 text-danger",
  refunded: "bg-danger/10 text-danger",
};

export default function OrderStatusPill({ status }: { status: string }) {
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full capitalize ${STATUS_STYLE[status] ?? "bg-ink/10 text-ink"}`}>
      {status}
    </span>
  );
}
