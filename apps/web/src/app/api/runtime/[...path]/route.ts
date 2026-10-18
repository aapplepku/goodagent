import { proxyRuntime } from "@/lib/runtime-proxy";

type Context = { params: Promise<{ path: string[] }> };
async function handle(request: Request, context: Context): Promise<Response> {
  return proxyRuntime(request, (await context.params).path);
}

export {
  handle as GET,
  handle as POST,
  handle as PATCH,
  handle as PUT,
  handle as DELETE,
};
