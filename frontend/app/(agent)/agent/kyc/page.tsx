import KycForm from "./KycForm";

export default function AgentKycPage() {
  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Your details</h1>
        <p className="text-sm text-muted mt-1">
          An admin checks these before you can start taking deliveries.
        </p>
      </div>
      <KycForm />
    </div>
  );
}