import { redirect } from "next/navigation";

/**
 * `/agent/job/[id]` used to be a second, simpler copy of the delivery detail
 * screen. It had drifted: it offered "Mark Delivered" with no way to enter the
 * customer's code, so the backend rejected every attempt with a 400. Two screens
 * for one job is how that happened, and nothing linked here.
 *
 * It now forwards to the canonical page at `/agent/deliveries/[id]`, which
 * collects the delivery code and surfaces the backend's own error message. Old
 * links keep working and there is one implementation to keep correct.
 */
export default async function AgentJobRedirect({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  redirect(`/agent/deliveries/${id}`);
}