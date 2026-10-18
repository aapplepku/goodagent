import { DemoWorkspace } from "@/components/demo-workspace";
import { getMeta } from "@/lib/server-api";
import { StoreAccess } from "@/components/store-setup";

export const dynamic = "force-dynamic";

export default async function Lab() {
  const meta = await getMeta();

  return (
    <StoreAccess initialView="workspace"><main className="page">
      <DemoWorkspace initialMeta={meta} />
    </main></StoreAccess>
  );
}
