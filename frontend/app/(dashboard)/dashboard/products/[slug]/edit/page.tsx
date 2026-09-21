import { notFound } from "next/navigation";
import { serverFetch } from "@/lib/server-api";
import { Product } from "@/types/interface";
import ProductForm from "@/components/dashboard/ProductForm";

interface Props {
  params: Promise<{ slug: string }>;
}

export default async function EditProductPage({ params }: Props) {
  const { slug } = await params;

  // `/shops/me/products/{slug}` rather than the public `/products/{slug}`: the
  // public one serves only active products on an active shop, so following the
  // edit link from the Products page 404'd on the seller's own draft or paused
  // product. The endpoint is already scoped to the caller's shop, which is what
  // makes the ownership check here unnecessary.
  const product = await serverFetch<Product>(`/shops/me/products/${slug}`).catch(
    () => null
  );

  if (!product) notFound();

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Edit product</h1>
      <ProductForm mode="edit" product={product} />
    </div>
  );
}
