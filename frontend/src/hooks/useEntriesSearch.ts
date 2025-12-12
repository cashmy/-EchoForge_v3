import { useQuery } from "@tanstack/react-query";
import {
  EntryListResponse,
  EntrySearchParams,
  fetchEntries,
} from "../api/entries";

const buildQueryKey = (params: EntrySearchParams) => [
  "entries",
  "search",
  params.q ?? "",
  (params.typeIds ?? []).join("|"),
  (params.domainIds ?? []).join("|"),
  (params.pipelineStatuses ?? []).join("|"),
  (params.sourceChannels ?? []).join("|"),
  params.createdFrom ?? "",
  params.createdTo ?? "",
  params.includeArchived ?? false,
  params.page ?? 1,
  params.pageSize ?? 20,
  params.sortBy ?? "updated_at",
  params.sortDir ?? "desc",
];

export const useEntriesSearch = (params: EntrySearchParams) =>
  useQuery<EntryListResponse, Error>({
    queryKey: buildQueryKey(params),
    queryFn: () => fetchEntries(params),
    placeholderData: (previousData) => previousData,
  });
