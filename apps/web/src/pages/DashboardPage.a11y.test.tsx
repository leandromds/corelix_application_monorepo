/**
 * Accessibility tests for DashboardPage.
 *
 * MSW intercepts the three queries the page fires on mount:
 *   - GET /agenda/sessions/today
 *   - GET /agenda/sessions/upcoming
 *   - GET /clients
 *
 * Rules disabled:
 *   - color-contrast: CSS custom properties aren't computed in jsdom
 *   - region: components rendered in isolation have no landmark wrapper
 */

vi.mock("@/hooks/useAuth");

import { axe } from "jest-axe";
import { http, HttpResponse } from "msw";
import { waitFor } from "@testing-library/react";
import { useAuth } from "@/hooks/useAuth";
import { server, BASE_URL } from "@/test/server";
import { renderWithProviders } from "@/test/utils";
import { DashboardPage } from "./DashboardPage";

import type { ProfessionalResponse } from "@/types/auth";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const AXE_CONFIG = {
  rules: {
    "color-contrast": { enabled: false },
    region: { enabled: false },
  },
};

const MOCK_PROFESSIONAL: ProfessionalResponse = {
  id: "prof-1",
  full_name: "Dr. Ana",
  email: "ana@test.com",
  specialty: null,
  bio: null,
  phone: null,
  session_duration: 50,
  session_price: "150.00",
  is_active: true,
  created_at: "2024-01-01T00:00:00Z",
};

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.mocked(useAuth).mockReturnValue({
    professional: MOCK_PROFESSIONAL,
    isLoading: false,
    isAuthenticated: true,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    refreshProfile: vi.fn(),
  });

  server.use(
    http.get(BASE_URL + "/agenda/sessions/today", () => HttpResponse.json([])),
    http.get(BASE_URL + "/agenda/sessions/upcoming", () =>
      HttpResponse.json([]),
    ),
    http.get(BASE_URL + "/clients", () => HttpResponse.json([])),
  );
});

afterEach(() => {
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("DashboardPage a11y", () => {
  // DashboardPage is a complex component (~600 lines). axe audit on large
  // components can take several seconds — increase timeout to 15 s.
  it("não tem violações axe críticas ou sérias", async () => {
    const { container } = renderWithProviders(<DashboardPage />);

    // Wait for all loading skeletons to disappear (queries settled via MSW)
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
