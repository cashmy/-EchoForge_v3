import { apiClient } from "./client";

export type CaptureMode = "text" | "file_ref";

export interface CaptureRequestPayload {
  mode: CaptureMode;
  source_channel?: string;
  display_title?: string;
  content?: string;
  file_path?: string;
  metadata?: Record<string, unknown>;
}

export interface CaptureResponse {
  entry_id: string;
  ingest_state: string;
}

export const submitCapture = async (
  payload: CaptureRequestPayload
): Promise<CaptureResponse> => {
  const response = await apiClient.post<CaptureResponse>("/capture", payload);
  return response.data;
};
