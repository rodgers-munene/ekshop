import { cookies } from "next/headers";
import { NextResponse } from "next/server";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL;

export async function DELETE(_: Request, { params }: { params: Promise<{ productId: string }> }) {
  const { productId } = await params;
  const cookieStore = await cookies();
  const token = cookieStore.get("ekshop_token")?.value;
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  const res = await fetch(`${BASE_URL}/users/me/wishlist/${productId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });

  return new NextResponse(null, { status: res.status });
}
