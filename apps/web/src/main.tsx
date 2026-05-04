import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { Toaster } from "sonner";
import { ThemeProvider } from "@/contexts/ThemeContext";
import "./index.css";
import App from "./App.tsx";

// ---------------------------------------------------------------------------
// Query client — 5 min stale time, 1 retry, no focus refetch in dev
// ---------------------------------------------------------------------------

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("Root element not found. Check your index.html.");
}

createRoot(rootElement).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <App />
        <Toaster
          richColors
          position="top-right"
          toastOptions={{
            style: { fontFamily: "var(--font-body)", fontSize: 13 },
          }}
        />
        {import.meta.env.DEV && <ReactQueryDevtools initialIsOpen={false} />}
      </ThemeProvider>
    </QueryClientProvider>
  </StrictMode>,
);
