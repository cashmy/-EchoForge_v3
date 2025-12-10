import { beforeEach, describe, expect, it, vi } from "vitest";

const CACHE_KEY = "echoforge.taxonomy.cache.v1";

const mockFetch = vi.fn();

vi.mock("../api/taxonomy", () => ({
  fetchTaxonomyList: mockFetch,
}));

describe("useTaxonomyStore", () => {
  beforeEach(() => {
    localStorage.clear();
    mockFetch.mockReset();
    vi.resetModules();
  });

  it("hydrates records from cache when available", async () => {
    localStorage.setItem(
      CACHE_KEY,
      JSON.stringify({
        types: [
          {
            id: "type-1",
            name: "type-one",
            label: "Type One",
            description: null,
            active: true,
            sort_order: 10,
          },
        ],
        domains: [],
        includeInactive: false,
        fetchedAt: Date.now(),
      })
    );

    const { useTaxonomyStore } = await import("./useTaxonomyStore");

    expect(useTaxonomyStore.getState().types).toHaveLength(1);
    expect(useTaxonomyStore.getState().status).toBe("ready");
    expect(useTaxonomyStore.getState().staleReason).toBe("cache");
  });

  it("loads taxonomy lists and persists cache", async () => {
    mockFetch.mockImplementation(async (kind: "types" | "domains") => ({
      items: [
        {
          id: `${kind}-1`,
          name: `${kind}-name`,
          label: `${kind} label`,
          description: null,
          active: true,
          sort_order: 1,
        },
      ],
      page: 1,
      page_size: 50,
      total_items: 1,
    }));

    const { useTaxonomyStore } = await import("./useTaxonomyStore");
    await useTaxonomyStore.getState().loadTaxonomy({ force: true });

    expect(mockFetch).toHaveBeenCalledTimes(2);
    expect(mockFetch.mock.calls[0][0]).toBe("types");
    expect(mockFetch.mock.calls[0][1]).toEqual({ includeInactive: false });
    const cache = JSON.parse(localStorage.getItem(CACHE_KEY) ?? "{}");
    expect(cache.types).toHaveLength(1);
    expect(cache.includeInactive).toBe(false);
  });
});
