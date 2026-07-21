import Link from "next/link";
import { Menu } from "lucide-react";
import { serverFetch } from "@/lib/server-api";
import { Category } from "@/types/interface";

export default async function CategoryStrip() {
  let categories: Category[] = [];

  try {
    categories = await serverFetch<Category[]>("/categories/");
  } catch {
    return null;
  }

  // Only show parent categories in the strip
  const parents = categories.filter((c) => !c.parent_id && c.is_active);

  if (parents.length === 0) return null;

  return (
    <nav className="bg-navy-light text-white/90">
      <div className="w-full px-4">
        <ul className="flex items-center gap-5 overflow-x-auto scrollbar-hide h-10">
          <li className="shrink-0 flex items-center gap-1.5 font-semibold text-sm pr-4 border-r border-white/15">
            <Menu size={16} />
            All
          </li>
          {parents.map((category) => (
            <li key={category.id} className="shrink-0">
              <Link
                href={`/products?category=${category.slug}`}
                className="text-sm whitespace-nowrap hover:text-amber transition-colors"
              >
                {category.name}
              </Link>
            </li>
          ))}
          <li className="shrink-0 ml-auto text-sm text-white/60 hidden lg:block">
            Pay with M-Pesa · Nationwide delivery
          </li>
        </ul>
      </div>
    </nav>
  );
}
