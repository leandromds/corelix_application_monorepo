import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { Toaster } from "sonner";
import * as Sentry from "@sentry/react";
import posthog from "posthog-js";
import { ThemeProvider } from "@/contexts/ThemeContext";
import "./index.css";
import App from "./App.tsx";

// ---------------------------------------------------------------------------
// Glitchtip / Sentry — error tracking
// Only initialized when VITE_GLITCHTIP_DSN is defined (safe in dev without var)
// ---------------------------------------------------------------------------

const glitchtipDsn = import.meta.env.VITE_GLITCHTIP_DSN as string | undefined;

if (glitchtipDsn) {
  Sentry.init({
    dsn: glitchtipDsn,
    tracesSampleRate: 0.2,
    environment: import.meta.env.VITE_ENVIRONMENT ?? "development",
    integrations: [Sentry.browserTracingIntegration()],
  });
}

// ---------------------------------------------------------------------------
// PostHog — product analytics + session replay
// Only initialized when VITE_POSTHOG_KEY is defined (safe in dev without var)
// ---------------------------------------------------------------------------

const posthogKey = import.meta.env.VITE_POSTHOG_KEY as string | undefined;
const posthogHost =
  (import.meta.env.VITE_POSTHOG_HOST as string | undefined) ??
  "https://app.posthog.com";

if (posthogKey) {
  posthog.init(posthogKey, {
    api_host: posthogHost,
    session_recording: {
      maskAllInputs: true, // privacy: mask form inputs in recordings
    },
    autocapture: true,
    capture_pageview: true,
  });
}

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

// Sentry.ErrorBoundary wraps the entire app so any uncaught React error
// is captured and sent to Glitchtip. Falls back gracefully when DSN not set.
createRoot(rootElement).render(
  <StrictMode>
    <Sentry.ErrorBoundary
      fallback={<p>Algo deu errado. Por favor, recarregue a página.</p>}
    >
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
    </Sentry.ErrorBoundary>
  </StrictMode>,
);
