import { serverFetch } from "@/lib/server-api";
import { Category } from "@/types/interface";
import ProductForm from "@/components/dashboard/ProductForm";

export default async function NewProductPage() {
  const categories = await serverFetch<Category[]>("/categories/").catch(() => []);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Add product</h1>
      <ProductForm mode="create" categories={categories} />
    </div>
  );
}
