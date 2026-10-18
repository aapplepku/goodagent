import { ManagerCatalog } from "@/components/manager-catalog";
import { StoreAccess } from "@/components/store-setup";

export const dynamic = "force-dynamic";

export default function CatalogPage() {
  return <StoreAccess initialView="workspace"><ManagerCatalog /></StoreAccess>;
}
