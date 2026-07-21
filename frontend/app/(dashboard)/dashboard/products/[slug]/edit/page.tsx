import { notFound } from "next/navigation";
import { serverFetch } from "@/lib/server-api";
import { Product, Shop } from "@/types/interface";
import ProductForm from "@/components/dashboard/ProductForm";

interface Props {
  params: Promise<{ slug: string }>;
}

export default async function EditProductPage({ params }: Props) {
  const { slug } = await params;

  const [product, shop] = await Promise.all([
    serverFetch<Product>(`/products/${slug}`).catch(() => null),
    serverFetch<Shop>("/shops/me").catch(() => null),
  ]);

  if (!product || !shop || product.shop_id !== shop.id) notFound();

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Edit product</h1>
      <ProductForm mode="edit" product={product} />
    </div>
  );
}
