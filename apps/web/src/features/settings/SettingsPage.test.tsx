/**
 * Integration tests for SettingsPage.
 *
 * Strategy: mock useAuth() so the component receives a pre-populated
 * professional without needing a real AuthProvider in the render tree.
 * MSW intercepts the PATCH /professionals/me request.
 *
 * Patterns:
 * - vi.mock('@/hooks/useAuth') → vi.mocked(useAuth).mockReturnValue(...)
 * - No fake timers needed (no date logic in this page)
 */

vi.mock("@/hooks/useAuth");
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import { http, HttpResponse } from "msw";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";

import { server, BASE_URL } from "@/test/server";
import { renderWithProviders, screen, waitFor } from "@/test/utils";
import { useAuth } from "@/hooks/useAuth";
import { settingsSchema } from "./schemas/settingsSchema";
import { SettingsPage } from "./SettingsPage";

import type { ProfessionalResponse } from "@/types/auth";
// ---------------------------------------------------------------------------

const MOCK_PROFESSIONAL: ProfessionalResponse = {
  id: "prof-1",
  email: "ana@example.com",
  full_name: "Ana Silva",
  specialty: "Psicologia",
  bio: "Psicóloga clínica com 10 anos de experiência.",
  phone: "+5511999999999",
  session_duration: 50,
  session_price: "200.00",
  is_active: true,
  created_at: "2025-01-01T00:00:00.000Z",
};

const mockRefreshProfile = vi.fn().mockResolvedValue(undefined);

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.mocked(useAuth).mockReturnValue({
    professional: MOCK_PROFESSIONAL,
    refreshProfile: mockRefreshProfile,
    isLoading: false,
    isAuthenticated: true,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  });

  server.use(
    http.patch(BASE_URL + "/professionals/me", () =>
      HttpResponse.json({ ...MOCK_PROFESSIONAL, full_name: "Ana Lima" }),
    ),
  );
});

afterEach(() => {
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("SettingsPage", () => {
  // ── Render básico ────────────────────────────────────────────────────────

  it('renderiza o heading "Configurações"', () => {
    renderWithProviders(<SettingsPage />);
    expect(
      screen.getByRole("heading", { name: /configurações/i }),
    ).toBeInTheDocument();
  });

  it("exibe o e-mail do profissional como informação somente leitura", () => {
    renderWithProviders(<SettingsPage />);
    // Email is displayed as text, not an editable input
    expect(screen.getByText("ana@example.com")).toBeInTheDocument();
    // The email field must NOT be an editable input
    expect(
      screen.queryByRole("textbox", { name: /e-mail/i }),
    ).not.toBeInTheDocument();
  });

  // ── Pré-população ────────────────────────────────────────────────────────

  it("pré-popula os campos com os dados do profissional do AuthContext", async () => {
    const user = userEvent.setup();
    renderWithProviders(<SettingsPage />);

    // Perfil tab fields
    expect(await screen.findByDisplayValue("Ana Silva")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Psicologia")).toBeInTheDocument();
    expect(screen.getByDisplayValue("+5511999999999")).toBeInTheDocument();

    // Valores tab fields — navigate first
    await user.click(screen.getByRole("button", { name: /valores/i }));
    expect(screen.getByDisplayValue("50")).toBeInTheDocument();
    expect(screen.getByDisplayValue("200")).toBeInTheDocument();
  });

  // ── Submissão bem-sucedida ───────────────────────────────────────────────

  it('chama PATCH /professionals/me ao clicar em "Salvar alterações"', async () => {
    const user = userEvent.setup();
    const requestBodies: unknown[] = [];

    server.use(
      http.patch(BASE_URL + "/professionals/me", async ({ request }) => {
        requestBodies.push(await request.json());
        return HttpResponse.json({ ...MOCK_PROFESSIONAL });
      }),
    );

    renderWithProviders(<SettingsPage />);
    await screen.findByDisplayValue("Ana Silva");

    await user.click(
      screen.getByRole("button", { name: /salvar alterações/i }),
    );

    await waitFor(() => expect(requestBodies.length).toBeGreaterThan(0));
    expect(requestBodies[0]).toMatchObject({ full_name: "Ana Silva" });
  });

  it("exibe toast de sucesso e chama refreshProfile após salvar", async () => {
    const user = userEvent.setup();
    renderWithProviders(<SettingsPage />);

    await screen.findByDisplayValue("Ana Silva");
    await user.click(
      screen.getByRole("button", { name: /salvar alterações/i }),
    );

    await waitFor(() => {
      expect(toast.success).toHaveBeenCalledWith("Perfil atualizado");
      expect(mockRefreshProfile).toHaveBeenCalled();
    });
  });

  // ── Erro da API ──────────────────────────────────────────────────────────

  it("exibe toast de erro quando o PATCH retorna 500", async () => {
    server.use(
      http.patch(BASE_URL + "/professionals/me", () =>
        HttpResponse.json(
          { message: "Internal Server Error" },
          { status: 500 },
        ),
      ),
    );

    const user = userEvent.setup();
    renderWithProviders(<SettingsPage />);

    await screen.findByDisplayValue("Ana Silva");
    await user.click(
      screen.getByRole("button", { name: /salvar alterações/i }),
    );

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("Erro ao atualizar perfil");
    });
  });

  // ── Validação ────────────────────────────────────────────────────────────

  it("exibe erro de validação ao tentar salvar full_name com menos de 2 caracteres", async () => {
    const user = userEvent.setup();
    renderWithProviders(<SettingsPage />);

    await screen.findByDisplayValue("Ana Silva");

    // Find by display value — FormControl wraps <input> in a <div> with the
    // generated id, so RTL cannot compute accessible name from the label.
    const fullNameInput = screen.getByDisplayValue("Ana Silva");
    await user.clear(fullNameInput);
    await user.type(fullNameInput, "A");

    await user.click(
      screen.getByRole("button", { name: /salvar alterações/i }),
    );

    await waitFor(() => {
      expect(screen.getByText(/pelo menos 2 caracteres/i)).toBeInTheDocument();
    });
  });

  it("schema rejeita session_duration menor que 15 e retorna mensagem correta", () => {
    // Testing the Zod schema directly is more reliable than simulating
    // a number input in JSDOM (fireEvent/userEvent do not consistently
    // update RHF state for type="number" inputs due to React's synthetic
    // event system in the test environment).
    // The full_name test above already proves that FormMessage renders
    // Zod errors — this test proves the constraint is defined.
    const result = settingsSchema.safeParse({
      full_name: "Ana Silva",
      specialty: "",
      bio: "",
      phone: "",
      session_duration: 10, // < 15 → should fail
      session_price: 200,
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      const durationError = result.error.issues.find((e) =>
        e.path.includes("session_duration"),
      );
      expect(durationError?.message).toMatch(/mínima: 15 minutos/i);
    }
  });

  // ── Estado de carregamento ───────────────────────────────────────────────

  it('desabilita o botão "Salvar alterações" durante o envio', async () => {
    // Handler that never resolves → mutation stays in isPending=true
    server.use(
      http.patch(BASE_URL + "/professionals/me", async () => {
        await new Promise(() => {});
        return HttpResponse.json({});
      }),
    );

    const user = userEvent.setup();
    renderWithProviders(<SettingsPage />);

    await screen.findByDisplayValue("Ana Silva");
    await user.click(
      screen.getByRole("button", { name: /salvar alterações/i }),
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /salvando/i })).toBeDisabled();
    });
  });
});
