/**
 * Tests for WeekView component.
 *
 * vi.useFakeTimers() controls Date.now() so isToday() returns a
 * deterministic value (July 21, 2025 = Monday is "today").
 *
 * Sessions are passed as props — no HTTP mocking needed.
 * UTC timestamps are used for getSessionTop() determinism.
 */

import { renderWithProviders, screen, fireEvent } from "@/test/utils";
import { WeekView } from "./WeekView";
import type { Session } from "../types";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

// Use local-midnight / local-time constants so that isSameDay, startOfWeek,
// and getSessionTop behave identically regardless of the host machine's timezone.
// These are evaluated at module level before any fake timers are installed,
// ensuring the REAL Date constructor is used.
const MONDAY_JULY_21 = new Date(2025, 6, 21); // local midnight July 21, 2025

// Local 10:00 → getHours()=10 → slot=(10-8)*2=4 → top=192px (8:00–19:00 range)
const SESSION_SCHEDULED_AT = new Date(2025, 6, 21, 10, 0, 0).toISOString();

const mockSession: Session = {
  id: "session-1",
  client_id: "client-1",
  client_name: "Ana Lima",
  scheduled_at: SESSION_SCHEDULED_AT,
  duration_minutes: 50,
  price: "150.00",
  status: "scheduled",
  notes: null,
  is_active: true,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

// ---------------------------------------------------------------------------
// Timer helpers
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.useFakeTimers();
  // Set fake "today" to local noon on July 21 so isToday() highlights Monday.
  // new Date(year, month, day, hours) with explicit args works with fake timers.
  vi.setSystemTime(new Date(2025, 6, 21, 12, 0, 0));
});

afterEach(() => {
  vi.useRealTimers();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("WeekView", () => {
  it("renderiza os 5 cabeçalhos de dias da semana (seg–sex em ptBR)", () => {
    renderWithProviders(
      <WeekView
        sessions={[]}
        currentWeek={MONDAY_JULY_21}
        onSessionClick={vi.fn()}
        onNewSession={vi.fn()}
      />,
    );

    // date-fns v3 EEE with ptBR locale renders the Portuguese weekday
    // abbreviations as full short forms: "segunda", "terça", "quarta", "quinta", "sexta".
    // CSS `uppercase` class is visual only — text content remains as rendered.
    const expectedLabels = ["segunda", "terça", "quarta", "quinta", "sexta"];
    for (const label of expectedLabels) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it("renderiza o nome do cliente no bloco da sessão correspondente", () => {
    renderWithProviders(
      <WeekView
        sessions={[mockSession]}
        currentWeek={MONDAY_JULY_21}
        onSessionClick={vi.fn()}
        onNewSession={vi.fn()}
      />,
    );

    // The session block renders the client name as visible text
    expect(screen.getByText("Ana Lima")).toBeInTheDocument();
  });

  it("clicar em um bloco de sessão chama onSessionClick com a sessão correta", () => {
    const onSessionClick = vi.fn();
    const onNewSession = vi.fn();

    renderWithProviders(
      <WeekView
        sessions={[mockSession]}
        currentWeek={MONDAY_JULY_21}
        onSessionClick={onSessionClick}
        onNewSession={onNewSession}
      />,
    );

    // fireEvent bypasses userEvent's pointer-event/geometry checks,
    // which fail in jsdom where all elements have zero bounding rects.
    fireEvent.click(screen.getByText("Ana Lima"));

    expect(onSessionClick).toHaveBeenCalledTimes(1);
    expect(onSessionClick).toHaveBeenCalledWith(mockSession);
    // stopPropagation on session block — column click must NOT fire
    expect(onNewSession).not.toHaveBeenCalled();
  });

  it("sessão de outra semana não aparece na semana atual", () => {
    const nextWeekSession: Session = {
      ...mockSession,
      id: "session-next",
      client_name: "Bruno Costa",
      // July 28 — next week's Monday, outside the July 21–25 local range
      scheduled_at: new Date(2025, 6, 28, 10, 0, 0).toISOString(),
    };

    renderWithProviders(
      <WeekView
        sessions={[nextWeekSession]}
        currentWeek={MONDAY_JULY_21}
        onSessionClick={vi.fn()}
        onNewSession={vi.fn()}
      />,
    );

    // No session block for the next week's session
    expect(screen.queryByText("Bruno Costa")).not.toBeInTheDocument();
  });
});
