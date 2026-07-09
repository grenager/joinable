import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import { AdminPage } from "./components/AdminPage.tsx";
import "./index.css";

function useHashRoute(): string {
  const [hash, setHash] = useState<string>(window.location.hash);
  useEffect(() => {
    const onHashChange = (): void => setHash(window.location.hash);
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);
  return hash;
}

function Root() {
  const hash = useHashRoute();
  if (hash.startsWith("#/admin")) {
    return <AdminPage />;
  }
  return <App />;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Root />
  </StrictMode>
);
