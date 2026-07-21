import { redirect } from "next/navigation";
import { serverFetch } from "@/lib/server-api";
import { User, UserAddress } from "@/types/interface";
import AccountClient from "./AccountClient";

export default async function AccountPage() {
  const [user, addresses] = await Promise.all([
    serverFetch<User>("/users/me").catch(() => null),
    serverFetch<UserAddress[]>("/users/me/addresses").catch(() => []),
  ]);

  if (!user) redirect("/login");

  return <AccountClient user={user} addresses={addresses as UserAddress[]} />;
}
