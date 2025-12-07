import { create } from "zustand";

interface BackendStatus {
  status: string;
  entryStore?: string;
  jobQueue?: string;
}

interface AppState {
  backendStatus?: BackendStatus;
  setBackendStatus: (status: BackendStatus) => void;
}

export const useAppStore = create<AppState>((set) => ({
  backendStatus: undefined,
  setBackendStatus: (status) => set({ backendStatus: status }),
}));
