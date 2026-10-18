import { OpenCommerceClient, type MetaResponse } from "@open-commerce/sdk-typescript";
import { serverApiUrl } from "./runtime-proxy";

export async function getMeta(): Promise<MetaResponse | null> {
  try {
    return await new OpenCommerceClient({
      baseUrl: serverApiUrl(),
      fetcher: (input, init) => fetch(input, { ...init, cache: "no-store" }),
    }).meta();
  } catch {
    return null;
  }
}
