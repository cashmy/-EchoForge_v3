import { useQuery } from "@tanstack/react-query";
import { EntryDetail, fetchEntryDetail } from "../api/entries";

export const useEntryDetail = (entryId?: string) =>
  useQuery<EntryDetail, Error>({
    queryKey: ["entries", "detail", entryId ?? ""],
    queryFn: () => {
      if (!entryId) {
        throw new Error("entryId is required");
      }
      return fetchEntryDetail(entryId);
    },
    enabled: Boolean(entryId),
    staleTime: 5 * 60 * 1000,
  });
