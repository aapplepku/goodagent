import { ManagerWorkspace } from "@/components/manager-workspace";
import { getMeta } from "@/lib/server-api";
import { StoreAccess } from "@/components/store-setup";

export const dynamic = "force-dynamic";

export default async function ManagerPage() {
  const meta = await getMeta();
  return (
    <StoreAccess>
      <ManagerWorkspace initialMeta={meta} />
    </StoreAccess>
  );
}
