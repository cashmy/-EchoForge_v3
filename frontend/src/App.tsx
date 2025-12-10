import { useEffect } from "react";
import { useHealthcheck } from "./hooks/useHealthcheck";
import { useAppStore } from "./state/useAppStore";
import { ShellLayout } from "./components/ShellLayout";
import { DashboardPage } from "./pages/DashboardPage";
import { shouldShowTaxonomyConsole } from "./types/backend";
import { useTaxonomyStore } from "./state/useTaxonomyStore";

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

  const showTaxonomyConsole = shouldShowTaxonomyConsole(data);

  return (
    <ShellLayout>
      {isLoading ? (
        "Connecting…"
      ) : (
        <DashboardPage showTaxonomyConsole={showTaxonomyConsole} />
      )}
    </ShellLayout>
  );
};

export default App;
