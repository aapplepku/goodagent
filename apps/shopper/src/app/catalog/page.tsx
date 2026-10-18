import { ShopperApp } from "@/components/shopper-app";

export const dynamic = "force-dynamic";

export default function CatalogPage() {
  return <ShopperApp initialView="catalog" />;
}
