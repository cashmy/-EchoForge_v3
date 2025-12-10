import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../api/client";
import { BackendStatus } from "../types/backend";

export const useHealthcheck = () =>
  useQuery({
    queryKey: ["healthcheck"],
    queryFn: async () => {
      const response = await apiClient.get<BackendStatus>("/healthz");
      return response.data;
    },
    staleTime: 30_000,
  });
