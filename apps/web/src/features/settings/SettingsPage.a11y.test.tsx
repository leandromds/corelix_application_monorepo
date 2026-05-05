/**
 * Accessibility tests for SettingsPage.
 *
 * Uses vi.mock('@/hooks/useAuth') with a populated professional so the form
 * pre-fills correctly — same pattern as SettingsPage.test.tsx.
 *
 * Rules disabled:
 *   - color-contrast: CSS custom properties aren't computed in jsdom
 *   - region: components rendered in isolation have no landmark wrapper
 */

vi.mock("@/hooks/useAuth");
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import { axe } from "jest-axe";
import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";
import { useAuth } from "@/hooks/useAuth";
import { server, BASE_URL } from "@/test/server";
import { renderWithProviders } from "@/test/utils";
import { SettingsPage } from "./SettingsPage";

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
    http.patch(BASE_URL + "/professionals/me", () =>
      HttpResponse.json(MOCK_PROFESSIONAL),
    ),
  );
});

afterEach(() => {
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("SettingsPage a11y", () => {
  it("não tem violações axe críticas ou sérias", async () => {
    const { container } = renderWithProviders(<SettingsPage />);

    // Wait for RHF to pre-populate fields (useEffect fires after first render)
    await screen.findByDisplayValue("Dr. Ana");

    const results = await axe(container, AXE_CONFIG);
    expect(results).toHaveNoViolations();
  }, 15000);
});
