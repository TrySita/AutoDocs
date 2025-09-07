import { AppRouter } from "@/lib/trpc/router";
import { inferRouterOutputs } from "@trpc/server";

export type DefinitionResponse = Omit<
  inferRouterOutputs<AppRouter>["analysis"]["definitions"]["byId"],
  "definitionDependents" | "definitionDependencies" | "references"
>;
export type DefinitionDetailResponse =
  inferRouterOutputs<AppRouter>["analysis"]["definitions"]["byId"];
export type FileResponse =
  inferRouterOutputs<AppRouter>["analysis"]["files"]["list"][number];
export type FileDetailResponse =
  inferRouterOutputs<AppRouter>["analysis"]["files"]["byId"];
export type PackageResponse =
  inferRouterOutputs<AppRouter>["analysis"]["packages"]["withReadme"][number];

export type DefinitionMetadata = {
  name: string;
  id: number;
  fileId: number;
  definitionType: string;
  file: {
    id: number;
    filePath: string;
  };
};
