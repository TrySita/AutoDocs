import { analysisRouter } from "./analysis";
import { router } from "./init";
import { chatRouter } from "./routes/chat";
import { projectRouter } from "./routes/openSource";
import { ingestionRouter } from "./routes/ingestion";

const appRouter = router({
  projects: projectRouter,
  analysis: analysisRouter,
  chat: chatRouter,
  ingestion: ingestionRouter,
});

export type AppRouter = typeof appRouter;
export { appRouter };
