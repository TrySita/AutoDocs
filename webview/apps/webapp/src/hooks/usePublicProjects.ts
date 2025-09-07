import { useTRPC } from "@/lib/trpc/client";
import { useQuery } from "@tanstack/react-query";

export const usePublicProjects = (limit: number = 5) => {
  const trpc = useTRPC();

  const { data: publicProjects, isLoading } = useQuery(
    trpc.projects.getPublicProjects.queryOptions({
      limit,
    }),
  );

  return {
    publicProjects: publicProjects,
    isLoading,
  };
};
