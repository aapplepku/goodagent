import { StoreEntry } from "@/components/store-entry";
export default async function StorePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return <StoreEntry key={slug} slug={slug} />;
}
