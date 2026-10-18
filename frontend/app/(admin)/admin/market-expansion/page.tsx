import { serverFetch, ServerFetchError } from "@/lib/server-api";
import { MarketExpansionReport } from "@/types/interface";
import MarketExpansionClient from "./MarketExpansionClient";

export default async function MarketExpansionPage() {
  let report: MarketExpansionReport | null = null;
  let error: string | null = null;
  try {
    report = await serverFetch<MarketExpansionReport>("/admin/metrics/market-expansion");
  } catch (err) {
    // A missing study bundle answers 503; that is a setup step, not a bug, so
    // the message is shown instead of an error page.
    error = err instanceof ServerFetchError ? err.message : null;
  }

  return <MarketExpansionClient report={report} error={error} />;
}
