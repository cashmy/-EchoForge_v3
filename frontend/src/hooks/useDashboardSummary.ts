import { useQuery } from "@tanstack/react-query";
import {
  DashboardSummaryParams,
  DashboardSummaryResponse,
  fetchDashboardSummary,
} from "../api/dashboard";

export const DASHBOARD_SUMMARY_QUERY_KEY = ["dashboard", "summary"];

export const useDashboardSummary = (params?: DashboardSummaryParams) =>
  useQuery<DashboardSummaryResponse, Error>({
    queryKey: [
      ...DASHBOARD_SUMMARY_QUERY_KEY,
      params?.timeWindowDays ?? "default",
      params?.includeArchived ?? false,
    ],
    queryFn: () => fetchDashboardSummary(params),
    staleTime: 60_000,
  });
