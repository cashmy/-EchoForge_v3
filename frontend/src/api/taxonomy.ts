import { apiClient } from "./client";

export interface TaxonomyRecord {
  id: string;
  name: string;
  label: string;
  description?: string | null;
  active: boolean;
  sort_order: number;
  metadata?: Record<string, unknown> | null;
  deletion_warning?: boolean | null;
  referenced_entries?: number | null;
}

export interface TaxonomyListResponse {
  items: TaxonomyRecord[];
  page: number;
  page_size: number;
  total_items: number;
  last_updated_cursor?: string | null;
}

export interface FetchTaxonomyOptions {
  includeInactive?: boolean;
  pageSize?: number;
  sortBy?: "sort_order" | "label" | "created_at";
  sortDir?: "asc" | "desc";
}

export interface TaxonomyCreatePayload {
  id: string;
  label: string;
  name?: string;
  description?: string | null;
  sort_order?: number;
  metadata?: Record<string, unknown> | null;
  active?: boolean;
}

export type TaxonomyUpdatePayload = Partial<
  Omit<TaxonomyCreatePayload, "id"> & { active: boolean }
>;

export const fetchTaxonomyList = async (
  kind: "types" | "domains",
  options: FetchTaxonomyOptions = {}
): Promise<TaxonomyListResponse> => {
  const params = new URLSearchParams();
  params.set("page", "1");
  params.set("page_size", String(options.pageSize ?? 200));
  params.set("sort_dir", options.sortDir ?? "asc");
  params.set("sort_by", options.sortBy ?? "sort_order");

  if (options.includeInactive === false) {
    params.set("active", "true");
  }

  const response = await apiClient.get<TaxonomyListResponse>(
    `/${kind}?${params.toString()}`
  );
  return response.data;
};

export const createTaxonomyRecord = async (
  kind: "types" | "domains",
  payload: TaxonomyCreatePayload
): Promise<TaxonomyRecord> => {
  const response = await apiClient.post<TaxonomyRecord>(`/${kind}`, payload);
  return response.data;
};

export const updateTaxonomyRecord = async (
  kind: "types" | "domains",
  id: string,
  payload: TaxonomyUpdatePayload
): Promise<TaxonomyRecord> => {
  const response = await apiClient.patch<TaxonomyRecord>(
    `/${kind}/${id}`,
    payload
  );
  return response.data;
};

export const deleteTaxonomyRecord = async (
  kind: "types" | "domains",
  id: string
) => {
  await apiClient.delete(`/${kind}/${id}`);
};
