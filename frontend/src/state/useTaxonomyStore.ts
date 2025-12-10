import { create } from "zustand";
import {
  FetchTaxonomyOptions,
  TaxonomyListResponse,
  TaxonomyRecord,
  fetchTaxonomyList,
} from "../api/taxonomy";

export type TaxonomyStatus = "idle" | "loading" | "ready" | "error";
export type TaxonomyStaleness = "cache" | "error" | undefined;

interface TaxonomyCachePayload {
  types: TaxonomyRecord[];
  domains: TaxonomyRecord[];
  fetchedAt: number;
  includeInactive: boolean;
}

export interface LoadOptions
  extends Pick<FetchTaxonomyOptions, "includeInactive"> {
  force?: boolean;
}

interface TaxonomyState {
  types: TaxonomyRecord[];
  domains: TaxonomyRecord[];
  status: TaxonomyStatus;
  staleReason: TaxonomyStaleness;
  lastFetched?: number;
  error?: string;
  includeInactive: boolean;
  featureEnabled: boolean;
  loadTaxonomy: (options?: LoadOptions) => Promise<void>;
  setIncludeInactive: (flag: boolean) => void;
  setFeatureEnabled: (flag: boolean) => void;
  clearError: () => void;
}

export const TAXONOMY_CACHE_KEY = "echoforge.taxonomy.cache.v1";

const sortRecords = (items: TaxonomyRecord[]): TaxonomyRecord[] =>
  [...items].sort((a, b) => {
    if (a.sort_order === b.sort_order) {
      return a.label.localeCompare(b.label);
    }
    return a.sort_order - b.sort_order;
  });

const readCache = (): TaxonomyCachePayload | undefined => {
  if (typeof window === "undefined") {
    return undefined;
  }
  try {
    const raw = window.localStorage.getItem(TAXONOMY_CACHE_KEY);
    if (!raw) {
      return undefined;
    }
    return JSON.parse(raw) as TaxonomyCachePayload;
  } catch {
    return undefined;
  }
};

const persistCache = (payload: TaxonomyCachePayload) => {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.setItem(TAXONOMY_CACHE_KEY, JSON.stringify(payload));
  } catch {
    // Best-effort cache; ignore storage quota errors.
  }
};

const clearCache = () => {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.removeItem(TAXONOMY_CACHE_KEY);
  } catch {
    // ignore
  }
};

const emitTelemetry = (event: string, detail: Record<string, unknown>) => {
  const payload = { event, ...detail };
  if (
    typeof window !== "undefined" &&
    typeof window.dispatchEvent === "function"
  ) {
    const TelemetryEvent =
      typeof window.CustomEvent === "function"
        ? window.CustomEvent
        : CustomEvent;
    window.dispatchEvent(
      new TelemetryEvent("echoforge:telemetry", { detail: payload })
    );
  }
  if (import.meta.env.DEV) {
    // eslint-disable-next-line no-console
    console.info(`[telemetry] ${event}`, detail);
  }
};

const cached = readCache();

export const useTaxonomyStore = create<TaxonomyState>()((set, get) => ({
  types: cached?.types ?? [],
  domains: cached?.domains ?? [],
  status: cached ? "ready" : "idle",
  staleReason: cached ? "cache" : undefined,
  lastFetched: cached?.fetchedAt,
  error: undefined,
  includeInactive: cached?.includeInactive ?? false,
  featureEnabled: true,
  async loadTaxonomy(options?: LoadOptions) {
    if (!get().featureEnabled) {
      return;
    }
    if (get().status === "loading" && !options?.force) {
      return;
    }

    const includeInactive =
      options?.includeInactive ?? get().includeInactive ?? false;

    set({
      status: "loading",
      staleReason: undefined,
      error: undefined,
    });

    emitTelemetry("ui.taxonomy_dropdown_load_start", {
      includeInactive,
    });

    try {
      const [typesResponse, domainsResponse]: [
        TaxonomyListResponse,
        TaxonomyListResponse
      ] = await Promise.all([
        fetchTaxonomyList("types", { includeInactive }),
        fetchTaxonomyList("domains", { includeInactive }),
      ]);

      const sortedTypes = sortRecords(typesResponse.items);
      const sortedDomains = sortRecords(domainsResponse.items);
      const fetchedAt = Date.now();

      set({
        types: sortedTypes,
        domains: sortedDomains,
        status: "ready",
        lastFetched: fetchedAt,
        staleReason: undefined,
        error: undefined,
      });

      persistCache({
        types: sortedTypes,
        domains: sortedDomains,
        fetchedAt,
        includeInactive,
      });

      emitTelemetry("ui.taxonomy_dropdown_load", {
        status: "success",
        includeInactive,
        typeCount: sortedTypes.length,
        domainCount: sortedDomains.length,
      });
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Failed to load taxonomy";
      const hasFallbackData = get().types.length + get().domains.length > 0;
      set({
        status: hasFallbackData ? "ready" : "error",
        error: message,
        staleReason: hasFallbackData ? "cache" : "error",
      });
      if (!hasFallbackData) {
        clearCache();
      }
      emitTelemetry("ui.taxonomy_dropdown_load", {
        status: "failed",
        includeInactive,
        message,
      });
    }
  },
  setIncludeInactive(flag) {
    set({ includeInactive: flag });
    const snapshot = get();
    if (snapshot.types.length || snapshot.domains.length) {
      persistCache({
        types: snapshot.types,
        domains: snapshot.domains,
        fetchedAt: snapshot.lastFetched ?? Date.now(),
        includeInactive: flag,
      });
    }
  },
  setFeatureEnabled(flag) {
    set({ featureEnabled: flag });
    if (!flag) {
      emitTelemetry("ui.taxonomy_dropdown_disabled", {});
    } else {
      emitTelemetry("ui.taxonomy_dropdown_enabled", {});
    }
  },
  clearError() {
    set({ error: undefined, staleReason: undefined });
  },
}));
