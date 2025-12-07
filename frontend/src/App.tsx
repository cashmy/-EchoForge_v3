import { useEffect } from "react";
import { useHealthcheck } from "./hooks/useHealthcheck";
import { useAppStore } from "./state/useAppStore";
import { ShellLayout } from "./components/ShellLayout";
import { DashboardPage } from "./pages/DashboardPage";

const App = () => {
  const { data, isLoading } = useHealthcheck();
  const setBackendStatus = useAppStore((state) => state.setBackendStatus);

  useEffect(() => {
    if (data) {
      setBackendStatus(data);
    }
  }, [data, setBackendStatus]);

  return (
    <ShellLayout>{isLoading ? "Connecting…" : <DashboardPage />}</ShellLayout>
  );
};

export default App;
