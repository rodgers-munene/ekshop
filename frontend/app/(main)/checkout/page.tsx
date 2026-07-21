import { redirect } from "next/navigation";
import { serverFetch } from "@/lib/server-api";
import { UserAddress } from "@/types/interface";
import CheckoutClient from "./CheckoutClient";

export default async function CheckoutPage() {
  const addresses = await serverFetch<UserAddress[]>("/users/me/addresses")
    .catch(() => null);

  if (addresses === null) redirect("/login");

  return <CheckoutClient addresses={addresses} />;
}
