import { create } from "zustand";
import { BackendStatus } from "../types/backend";

interface AppState {
  backendStatus?: BackendStatus;
  setBackendStatus: (status: BackendStatus) => void;
}

export const useAppStore = create<AppState>((set) => ({
  backendStatus: undefined,
  setBackendStatus: (status) => set({ backendStatus: status }),
}));
