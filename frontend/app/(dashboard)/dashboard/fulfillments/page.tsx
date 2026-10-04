import FulfillmentList from "./FulfillmentList";

export default function DashboardFulfillmentsPage() {
  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Deliveries</h1>
        <p className="text-sm text-muted mt-1">
          Every delivery for your shop, with its attempts and history.
        </p>
      </div>
      <FulfillmentList />
    </div>
  );
}