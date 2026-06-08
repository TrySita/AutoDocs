export type TRPCBatchResult<T> = ReadonlyArray<{
  id: number;
  result: { data: { json: T } };
}>;

export interface PublicProject {
  id: string;
  name: string;
  slug: string;
  repositoryUrl: string | null;
  isActive: boolean;
  sortOrder: number;
  createdAt: string;
  updatedAt: string;
  dbUrl: string | null;
  dbKey: string | null;
  latestJobId: string | null;
  latestJobStatus: string | null;
  description: string | null;
  logoUrl: string | null;
}

export function encodeTRPCResponse<T>(id: number, payload: T): string {
  const resp: TRPCBatchResult<T> = [
    { id, result: { data: { json: payload } } },
  ];
  return JSON.stringify(resp);
}

