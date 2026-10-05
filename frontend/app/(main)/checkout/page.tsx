import { redirect } from "next/navigation";
import { serverFetch } from "@/lib/server-api";
import { UserAddress } from "@/types/interface";
import CheckoutClient from "./CheckoutClient";

export default async function CheckoutPage({
  searchParams,
}: {
  searchParams: Promise<{ buy?: string }>;
}) {
  const { buy } = await searchParams;
  const addresses = await serverFetch<UserAddress[]>("/users/me/addresses")
    .catch(() => null);

  if (addresses === null) redirect(buy === "now" ? "/login?next=/checkout?buy=now" : "/login");

  return <CheckoutClient addresses={addresses} buyNow={buy === "now"} />;
}
