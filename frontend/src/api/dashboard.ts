import { apiClient } from "./client";

export interface FailureWindow {
  since: string;
  counts: Record<string, number>;
}

export interface PipelineSection {
  total: number;
  by_ingest_state: Record<string, number>;
  failure_window: FailureWindow;
}

export interface NeedsReviewItem {
  entry_id: string;
  display_title?: string | null;
  pipeline_status: string;
  cognitive_status?: string | null;
  updated_at: string;
}

export interface NeedsReviewSection {
  items: NeedsReviewItem[];
}

export interface CognitiveSection {
  by_status: Record<string, number>;
  needs_review: NeedsReviewSection;
}

export interface DailyCount {
  date: string;
  count: number;
}

export interface SourceMixItem {
  source_channel: string;
  count: number;
}

export interface MomentumSection {
  recent_intake: DailyCount[];
  source_mix: SourceMixItem[];
}

export interface TaxonomyLeaderboardItem {
  id?: string | null;
  label?: string | null;
  count: number;
}

export interface TaxonomySection {
  top_types: TaxonomyLeaderboardItem[];
  top_domains: TaxonomyLeaderboardItem[];
}

export interface RecentItem {
  entry_id: string;
  display_title?: string | null;
  pipeline_status: string;
  updated_at: string;
}

export interface RecentSection {
  processed: RecentItem[];
}

export interface DashboardMeta {
  generated_at: string;
  time_window_days: number;
  failure_window_days: number;
  source_window_days: number;
  include_archived: boolean;
}

export interface DashboardSummaryResponse {
  pipeline: PipelineSection;
  cognitive: CognitiveSection;
  momentum: MomentumSection;
  taxonomy: TaxonomySection;
  recent: RecentSection;
  meta: DashboardMeta;
}

export interface DashboardSummaryParams {
  timeWindowDays?: number;
  includeArchived?: boolean;
}

export const fetchDashboardSummary = async (
  params: DashboardSummaryParams = {}
): Promise<DashboardSummaryResponse> => {
  const response = await apiClient.get<DashboardSummaryResponse>(
    "/dashboard/summary",
    {
      params: {
        time_window_days: params.timeWindowDays,
        include_archived: params.includeArchived ?? false,
      },
    }
  );
  return response.data;
};
