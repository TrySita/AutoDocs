import { supabaseDb } from "@sita/shared";
import { initTRPC } from "@trpc/server";
import SuperJSON from "superjson";

export const createContext = async ({ req: request }: { req: Request }) => {
  return {
    request,
    supabaseDb,
  };
};

export const t = initTRPC.context<typeof createContext>().create({
  transformer: SuperJSON,
});

export const router = t.router;

export const publicProcedure = t.procedure;
