import { createContext } from "@/lib/trpc/init";
import { appRouter } from "@/lib/trpc/router";
import { fetchRequestHandler } from "@trpc/server/adapters/fetch";

export const dynamic = "force-dynamic";

const handler = async (req: Request) => {
  const context = await createContext({ req });

  let cleaned = false;

  const handleCleanup = async () => {
    if (cleaned) return;
    cleaned = true;
    try {
    } catch (error) {
      console.error("Error closing auth connection:", error);
    }
  };

  const res = await fetchRequestHandler({
    endpoint: "/api/trpc",
    req,
    router: appRouter,
    createContext: () => context!,
    onError(props) {
      console.error("TRPC error:", props.error);
    },
  });

  if (!res.body) {
    await handleCleanup();
    return res;
  }

  req.signal?.addEventListener("abort", handleCleanup);

  const { readable, writable } = new TransformStream();
  res.body
    .pipeTo(writable)
    .catch(() => {
      /* swallow cancellation/pipe errors */
    })
    .finally(handleCleanup);

  return new Response(readable, {
    status: res.status,
    statusText: res.statusText,
    headers: res.headers,
  });
};

export { handler as GET, handler as POST };
