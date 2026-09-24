import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { serverFetch } from "@/lib/server-api";
import { Category } from "@/types/interface";
import BulkImportWizard from "@/components/dashboard/BulkImportWizard";

export default async function BulkImportPage() {
  const categories = await serverFetch<Category[]>("/categories/").catch(() => []);

  return (
    <div>
      <Link
        href="/dashboard/products"
        className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink mb-4"
      >
        <ArrowLeft size={15} /> Products
      </Link>

      <h1 className="text-2xl font-bold mb-1">Import products</h1>
      <p className="text-muted text-sm mb-6 max-w-prose">
        Upload a stock spreadsheet and every row becomes a draft product. Nothing reaches your shop
        until you review the drafts and publish them.
      </p>

      <BulkImportWizard categories={categories} />
    </div>
  );
}
