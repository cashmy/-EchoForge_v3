import { useEffect } from "react";
import { RouterProvider } from "react-router-dom";
import { useHealthcheck } from "./hooks/useHealthcheck";
import { useAppStore } from "./state/useAppStore";
import { useTaxonomyStore } from "./state/useTaxonomyStore";
import { appRouter } from "./routes/router";

const App = () => {
  const { data, isLoading } = useHealthcheck();
  const setBackendStatus = useAppStore((state) => state.setBackendStatus);
  const loadTaxonomy = useTaxonomyStore((state) => state.loadTaxonomy);
  const setTaxonomyFlag = useTaxonomyStore((state) => state.setFeatureEnabled);

  useEffect(() => {
    if (data) {
      setBackendStatus(data);
      const taxonomyEnabled =
        data.featureFlags?.enable_taxonomy_refs_in_capture ?? false;
      setTaxonomyFlag(taxonomyEnabled);
      if (taxonomyEnabled) {
        loadTaxonomy();
      }
    }
  }, [data, loadTaxonomy, setBackendStatus, setTaxonomyFlag]);

  if (isLoading && !data) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-200">
        Connecting to EchoForge backend…
      </div>
    );
  }

  return <RouterProvider router={appRouter} />;
};

export default App;
