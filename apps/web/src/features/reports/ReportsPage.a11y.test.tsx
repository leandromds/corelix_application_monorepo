/**
 * Accessibility tests for ReportsPage.
 *
 * MSW intercepts GET /reports/summary to return a minimal summary object,
 * allowing the KPI cards to render in their loaded state.
 *
 * Rules disabled:
 *   - color-contrast: CSS custom properties aren't computed in jsdom
 *   - region: components rendered in isolation have no landmark wrapper
 */

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import { axe } from "jest-axe";
import { http, HttpResponse } from "msw";
import { waitFor } from "@testing-library/react";
import { server, BASE_URL } from "@/test/server";
import { renderWithProviders } from "@/test/utils";
import { ReportsPage } from "./ReportsPage";
import type { PeriodSummary } from "./types";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const AXE_CONFIG = {
  rules: {
    "color-contrast": { enabled: false },
    region: { enabled: false },
  },
};

const MOCK_SUMMARY: PeriodSummary = {
  period_start: "2025-06-01",
  period_end: "2025-07-01",
  total_sessions: 0,
  total_amount: "0",
  status_filter: ["completed"],
};

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  server.use(
    http.get(BASE_URL + "/reports/summary", () =>
      HttpResponse.json(MOCK_SUMMARY),
    ),
  );
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ReportsPage a11y", () => {
  // ReportsPage fires a summary query on mount. We wait for loading skeletons
  // to clear before auditing. axe on complex components can take a while —
  // increase timeout to 15 s.
  it("não tem violações axe críticas ou sérias", async () => {
    const { container } = renderWithProviders(<ReportsPage />);

    // Wait for summary query to settle (loading skeletons disappear)
    await waitFor(
      () => {
        expect(container.querySelector(".animate-pulse")).toBeNull();
      },
      { timeout: 10000 },
    );

    const results = await axe(container, AXE_CONFIG);
    expect(results).toHaveNoViolations();
  }, 15000);
});
