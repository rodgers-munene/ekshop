import FulfillmentDetailClient from "./FulfillmentDetailClient";

export default async function FulfillmentDetailPage({
  params,
}: {
  params: Promise<{ fulfillmentId: string }>;
}) {
  const { fulfillmentId } = await params;
  return <FulfillmentDetailClient key={fulfillmentId} />;
}