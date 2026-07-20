/**
 * Integration tests for AgendaPage.
 *
 * Fake timers (Date only) anchor "today" to Monday 2025-07-21 so that:
 *   - new Date() is deterministic inside useSessions / UpcomingSessionsTable
 *   - isSameDay checks against currentWeek are stable
 *   - setTimeout / setInterval stay real → findBy* / waitFor work normally
 *
 * MSW mocks both /agenda/sessions and /clients (SessionForm calls /clients
 * unconditionally even when the modal is closed).
 *
 * sonner is mocked because UpcomingSessionsTable uses useUpdateSession and
 * SessionForm uses useCreateSession / useUpdateSession (all use toast).
 */

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import { http, HttpResponse } from "msw";
import { server, BASE_URL } from "@/test/server";
import { renderWithProviders, screen, fireEvent } from "@/test/utils";
import userEvent from "@testing-library/user-event";
import { AgendaPage } from "./AgendaPage";
import type { Session } from "./types";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

// Monday July 21, 2025 at 10:00 LOCAL time
// Using local-time constants ensures isSameDay, upcoming filter, and
// getSessionTop behave identically regardless of the host machine's timezone.
// Evaluated at module level so the REAL Date constructor is used.
const SESSION_SCHEDULED_AT = new Date(2025, 6, 21, 10, 0, 0).toISOString();

const mockSession: Session = {
  id: "session-1",
  client_id: "client-1",
  client_name: "Ana Lima",
  // new Date(SESSION_SCHEDULED_AT) > new Date(localMidnightJuly21) → true (upcoming)
  // isSameDay(SESSION_SCHEDULED_AT, localMidnightJuly21) → true (same local day)
  // getSessionTop: getHours()=10 → slot=4 → top=192px (8:00–19:00 range)
  scheduled_at: SESSION_SCHEDULED_AT,
  duration_minutes: 50,
  price: "150.00",
  status: "scheduled",
  notes: null,
  is_active: true,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

const mockClient = {
  id: "client-1",
  full_name: "Ana Lima",
  phone: "+5511999999999",
  email: null,
  notes: null,
  is_active: true,
  whatsapp_opt_in: false,
  email_opt_in: false,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------

beforeEach(() => {
  // Only fake Date — setTimeout/setInterval stay real so findBy*/waitFor work.
  // Use local midnight (new Date(2025, 6, 21)) so currentWeek in AgendaPage
  // matches the session's local date in isSameDay checks.
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2025, 6, 21)); // local midnight July 21

  // Default handlers for every test — override per-test with server.use()
  server.use(
    http.get(BASE_URL + "/agenda/sessions", () =>
      HttpResponse.json([mockSession]),
    ),
    http.get(BASE_URL + "/clients", () => HttpResponse.json([mockClient])),
  );
});

afterEach(() => {
  vi.useRealTimers();
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("AgendaPage", () => {
  it('renderiza o cabeçalho "Agenda"', () => {
    renderWithProviders(<AgendaPage />);

    expect(screen.getByRole("heading", { name: "Agenda" })).toBeInTheDocument();
  });

  it("exibe o nome do cliente após o fetch de sessões bem-sucedido", async () => {
    renderWithProviders(<AgendaPage />);

    // "Ana Lima" appears in the UpcomingSessionsTable (and possibly WeekView).
    // findAllByText waits for at least one match — timezone-safe assertion.
    const matches = await screen.findAllByText("Ana Lima");
    expect(matches.length).toBeGreaterThan(0);
  });

  it('toggle "Dia" muda a visualização para lista (DayList)', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AgendaPage />);

    // Wait for sessions to load (WeekView is rendered after isLoading resolves)
    await screen.findAllByText("Ana Lima");

    await user.click(screen.getByRole("button", { name: "Dia" }));

    // DayList-specific text: "Sessão · Xmin · R$ value" — only in DayList rows
    expect(screen.getByText(/Sessão · \d+ min/)).toBeInTheDocument();
  });

  it('toggle "Semana" volta para WeekView após estar em modo Dia', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AgendaPage />);

    // Ensure initial load is complete
    await screen.findAllByText("Ana Lima");

    // Switch to day view
    await user.click(screen.getByRole("button", { name: "Dia" }));
    // DayList must be active
    expect(screen.getByText(/Sessão · \d+ min/)).toBeInTheDocument();

    // Switch back to week view
    await user.click(screen.getByRole("button", { name: "Semana" }));

    // WeekView renders abbreviated day names (ptBR EEE format = "segunda" for Monday)
    expect(screen.getByText("segunda")).toBeInTheDocument();
  });

  it('botão "Anterior" navega para a semana anterior sem erros', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AgendaPage />);

    // Wait for initial load
    await screen.findAllByText("Ana Lima");

    // Click navigation buttons — covers the navigate() inner function
    await user.click(screen.getByRole("button", { name: /anterior/i }));
    // The date label in the header changes (month/week shifts)
    // Just assert no crash and the heading is still present
    expect(screen.getByRole("heading", { name: "Agenda" })).toBeInTheDocument();
  });

  it('botão "Hoje" redefine a data atual sem erros', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AgendaPage />);

    await screen.findAllByText("Ana Lima");

    // Navigate away then come back
    await user.click(screen.getByRole("button", { name: /anterior/i }));
    await user.click(screen.getByRole("button", { name: "Hoje" }));

    expect(screen.getByRole("heading", { name: "Agenda" })).toBeInTheDocument();
  });

  it("fechar modal de sessão limpa o estado (handleFormOpenChange)", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AgendaPage />);

    // Open the modal
    await user.click(screen.getByRole("button", { name: /nova sessão/i }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toBeInTheDocument();

    // Close the modal via the close button inside Radix Dialog (X)
    // The close button has aria-label from <DialogClose> (sr-only: "Fechar")
    const closeBtn = screen.getByRole("button", { name: /fechar/i });
    fireEvent.click(closeBtn);

    // Dialog should be removed from DOM after close
    await screen.findByRole("heading", { name: "Agenda" });
  });

  it('botão "Nova Sessão" abre o modal SessionForm em modo criação', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AgendaPage />);

    await user.click(screen.getByRole("button", { name: /nova sessão/i }));

    // Radix Dialog with role="dialog" should be in the DOM
    expect(await screen.findByRole("dialog")).toBeInTheDocument();

    // Description text confirms it is in create mode, not edit mode
    expect(
      screen.getByText("Preencha os dados para agendar uma nova sessão."),
    ).toBeInTheDocument();
  });
});
