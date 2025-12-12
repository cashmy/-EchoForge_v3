import { apiClient } from "./client";

export interface EntryListItem {
  entry_id: string;
  display_title?: string | null;
  summary?: string | null;
  summary_preview?: string | null;
  verbatim_preview?: string | null;
  pipeline_status: string;
  cognitive_status: string;
  ingest_state?: string | null;
  type_id?: string | null;
  type_label?: string | null;
  domain_id?: string | null;
  domain_label?: string | null;
  source_type: string;
  source_channel: string;
  created_at: string;
  updated_at: string;
  semantic_tags?: string[] | null;
}

export interface PaginationMeta {
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
}

export interface EntryListResponse {
  items: EntryListItem[];
  pagination: PaginationMeta;
  filters: Record<string, unknown>;
  search_applied: boolean;
}

export interface EntryDetail extends EntryListItem {
  summary_model?: string | null;
  source_path?: string | null;
  metadata: Record<string, unknown>;
  content_lang?: string | null;
  transcription_text?: string | null;
  transcription_metadata?: Record<string, unknown> | null;
  extracted_text?: string | null;
  extraction_metadata?: Record<string, unknown> | null;
  normalized_text?: string | null;
  normalization_metadata?: Record<string, unknown> | null;
}

export interface TaxonomyDimensionPatchPayload {
  id?: string;
  label?: string;
  clear?: boolean;
}

export interface EntryPatchRequest {
  taxonomy: {
    type?: TaxonomyDimensionPatchPayload;
    domain?: TaxonomyDimensionPatchPayload;
  };
}

export interface TaxonomyDimensionState {
  id?: string | null;
  label?: string | null;
  pending_reconciliation: boolean;
}

export interface EntryPatchResponse {
  entry_id: string;
  taxonomy: {
    type: TaxonomyDimensionState;
    domain: TaxonomyDimensionState;
  };
  taxonomy_no_change?: boolean;
}

export interface EntrySearchParams {
  q?: string;
  typeIds?: string[];
  domainIds?: string[];
  pipelineStatuses?: string[];
  sourceChannels?: string[];
  createdFrom?: string;
  createdTo?: string;
  includeArchived?: boolean;
  page?: number;
  pageSize?: number;
  sortBy?: string;
  sortDir?: "asc" | "desc";
}

const joinValues = (values?: string[]): string | undefined => {
  if (!values || values.length === 0) {
    return undefined;
  }
  return values.join(",");
};

const normalizeSearchParams = (params: EntrySearchParams) => ({
  q: params.q?.trim() || undefined,
  type_id: joinValues(params.typeIds),
  domain_id: joinValues(params.domainIds),
  pipeline_status: joinValues(params.pipelineStatuses),
  source_channel: joinValues(params.sourceChannels),
  created_from: params.createdFrom,
  created_to: params.createdTo,
  include_archived: params.includeArchived ?? false,
  page: params.page ?? 1,
  page_size: params.pageSize ?? 20,
  sort_by: params.sortBy ?? "updated_at",
  sort_dir: params.sortDir ?? "desc",
});

export const fetchEntries = async (
  params: EntrySearchParams = {}
): Promise<EntryListResponse> => {
  const response = await apiClient.get<EntryListResponse>("/entries", {
    params: normalizeSearchParams(params),
  });
  return response.data;
};

export const fetchEntryDetail = async (
  entryId: string
): Promise<EntryDetail> => {
  const response = await apiClient.get<EntryDetail>(`/entries/${entryId}`);
  return response.data;
};

export const patchEntryTaxonomy = async (
  entryId: string,
  payload: EntryPatchRequest
): Promise<EntryPatchResponse> => {
  const response = await apiClient.patch<EntryPatchResponse>(
    `/entries/${entryId}`,
    payload
  );
  return response.data;
};
