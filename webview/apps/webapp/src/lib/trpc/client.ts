import { createTRPCContext } from "@trpc/tanstack-react-query";
import type { AppRouter } from "./router";

export const { TRPCProvider, useTRPC, useTRPCClient } =
  createTRPCContext<AppRouter>();
