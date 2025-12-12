import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  FetchTaxonomyOptions,
  TaxonomyListResponse,
  TaxonomyCreatePayload,
  TaxonomyRecord,
  TaxonomyUpdatePayload,
  createTaxonomyRecord,
  deleteTaxonomyRecord,
  fetchTaxonomyList,
  updateTaxonomyRecord,
} from "../api/taxonomy";

const taxonomyKeys = {
  list: (kind: "types" | "domains", opts: FetchTaxonomyOptions) => [
    "taxonomy",
    kind,
    opts.includeInactive ?? false,
    opts.pageSize ?? 200,
    opts.sortBy ?? "sort_order",
    opts.sortDir ?? "asc",
  ],
};

interface UseTaxonomyManagementOptions {
  includeInactive: boolean;
}

export const useTaxonomyManagement = (
  kind: "types" | "domains",
  { includeInactive }: UseTaxonomyManagementOptions
) => {
  const queryClient = useQueryClient();
  const queryOptions: FetchTaxonomyOptions = {
    includeInactive: includeInactive ? true : false,
    pageSize: 200,
    sortBy: "sort_order",
    sortDir: "asc",
  };

  const query = useQuery<TaxonomyListResponse>({
    queryKey: taxonomyKeys.list(kind, queryOptions),
    queryFn: () => fetchTaxonomyList(kind, queryOptions),
  });

  const invalidate = () =>
    queryClient.invalidateQueries({
      queryKey: taxonomyKeys.list(kind, queryOptions),
    });

  const createMutation = useMutation({
    mutationFn: (payload: TaxonomyCreatePayload) =>
      createTaxonomyRecord(kind, payload),
    onSuccess: invalidate,
  });
  const updateMutation = useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: string;
      payload: TaxonomyUpdatePayload;
    }) => updateTaxonomyRecord(kind, id, payload),
    onSuccess: invalidate,
  });
  const deleteMutation = useMutation({
    mutationFn: (taxonomyId: string) => deleteTaxonomyRecord(kind, taxonomyId),
    onSuccess: invalidate,
  });

  return {
    records: (query.data?.items as TaxonomyRecord[]) ?? [],
    isLoading: query.isLoading,
    isError: query.isError,
    refetch: query.refetch,
    createRecord: createMutation.mutateAsync,
    updateRecord: ({
      id,
      payload,
    }: {
      id: string;
      payload: TaxonomyUpdatePayload;
    }) => updateMutation.mutateAsync({ id, payload }),
    deleteRecord: deleteMutation.mutateAsync,
    isCreating: createMutation.isPending,
    isUpdating: updateMutation.isPending,
    isDeleting: deleteMutation.isPending,
    error:
      query.error ||
      createMutation.error ||
      updateMutation.error ||
      deleteMutation.error ||
      null,
  };
};
