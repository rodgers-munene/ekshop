import OfferInbox from "./OfferInbox";

export default function AgentOffersPage() {
  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Offers</h1>
        <p className="text-sm text-muted mt-1">
          Jobs offered to you. Accept one to start it.
        </p>
      </div>
      <OfferInbox />
    </div>
  );
}