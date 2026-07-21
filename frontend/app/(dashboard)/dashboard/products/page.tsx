import Link from "next/link";
import { serverFetch } from "@/lib/server-api";
import { Shop, ProductListResponse } from "@/types/interface";
import { formatKES, resolveImageUrl } from "@/lib/utils";

export default async function DashboardProductsPage() {
  const shop = await serverFetch<Shop>("/shops/me").catch(() => null);
  const productsRes = shop
    ? await serverFetch<ProductListResponse>(`/shops/${shop.slug}/products?limit=100`).catch(() => null)
    : null;
  const products = productsRes?.results ?? [];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Products</h1>
        <Link href="/dashboard/products/new" className="btn-accent">Add product</Link>
      </div>

      {products.length === 0 ? (
        <div className="card flex flex-col items-center justify-center py-20 text-center">
          <p className="font-bold mb-2">No products yet</p>
          <p className="text-muted text-sm mb-6">List your first product to start selling.</p>
          <Link href="/dashboard/products/new" className="btn-accent">Add product</Link>
        </div>
      ) : (
        <div className="card overflow-hidden overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted">
                <th className="px-4 py-3 font-medium">Product</th>
                <th className="px-4 py-3 font-medium">Price</th>
                <th className="px-4 py-3 font-medium">Stock</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {products.map((product) => (
                <tr key={product.id}>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded bg-surface overflow-hidden shrink-0">
                        {product.images[0] && (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img
                            src={resolveImageUrl(product.images[0].url)}
                            alt=""
                            className="w-full h-full object-cover"
                          />
                        )}
                      </div>
                      <span className="font-medium">{product.name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3">{formatKES(product.price)}</td>
                  <td className="px-4 py-3">{product.stock_qty}</td>
                  <td className="px-4 py-3">
                    <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-surface capitalize">
                      {product.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Link href={`/dashboard/products/${product.slug}/edit`} className="text-amber text-sm underline underline-offset-2">
                      Edit
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
