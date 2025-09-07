"use client";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";

export const useCustomSearchParams = (): [
  URLSearchParams | null,
  (
    updater:
      | ((prev: URLSearchParams) => URLSearchParams)
      | Record<string, string>,
    { replace }?: { replace?: boolean },
  ) => void,
] => {
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();

  const setSearchParams = useCallback(
    (
      updater:
        | ((prev: URLSearchParams) => URLSearchParams)
        | Record<string, string>,
      { replace = false } = {},
    ) => {
      let queryString: string;
      if (typeof updater === "function") {
        // If updater is a function, call it with the current search params
        const currentParams = new URLSearchParams(
          (searchParams ?? "").toString(),
        );
        const newParams = updater(currentParams);
        queryString = newParams.toString();
      } else {
        // If updater is an object, convert it to URLSearchParams
        const params = new URLSearchParams(updater);
        queryString = params.toString();
      }

      if (replace) {
        router.replace(`${pathname}?${queryString}`);
      } else {
        router.push(`${pathname}?${queryString}`);
      }
    },
    [pathname, router, searchParams],
  );

  return [searchParams, setSearchParams];
};
