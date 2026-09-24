import { cookies } from "next/headers";
import { NextResponse } from "next/server";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL;

/** A static segment, so Next resolves it ahead of [importId] — which would
    otherwise try to JSON-parse a spreadsheet. */
export async function GET() {
  const cookieStore = await cookies();
  const token = cookieStore.get("ekshop_token")?.value;
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  const res = await fetch(`${BASE_URL}/product-imports/template`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    return NextResponse.json(
      { detail: data.detail ?? "Could not build the template" },
      { status: res.status },
    );
  }

  // Passed through as bytes: turning it into JSON would corrupt the workbook.
  return new NextResponse(await res.arrayBuffer(), {
    status: 200,
    headers: {
      "Content-Type":
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      "Content-Disposition": 'attachment; filename="ekshop-product-template.xlsx"',
    },
  });
}
