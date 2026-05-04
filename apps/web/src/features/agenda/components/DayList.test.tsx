/**
 * Tests for DayList component.
 *
 * DayList uses useUpdateSession internally (for quick status changes),
 * so sonner is mocked to prevent side effects from the mutation hook.
 *
 * Important: timestamps are UTC-based ('2025-07-21T10:00:00.000Z') so that
 * isSameDay + format('HH:mm') behave deterministically in the UTC jsdom
 * environment regardless of the developer's local timezone.
 */

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import { http, HttpResponse } from "msw";
import { server, BASE_URL } from "@/test/server";
import { renderWithProviders, screen } from "@/test/utils";
import userEvent from "@testing-library/user-event";
import { DayList } from "./DayList";
import type { Session } from "../types";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

// Use local-midnight / local-time constants so that isSameDay behaves
// identically regardless of the host machine's timezone.
// These are evaluated at module level before any fake timers are installed.
const JULY_21 = new Date(2025, 6, 21); // local midnight July 21, 2025

// Local 10:00 in any timezone → format('HH:mm') always = '10:00'
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
// Tests
// ---------------------------------------------------------------------------

describe("DayList", () => {
  it('mostra "Carregando sessões…" quando isLoading=true', () => {
    renderWithProviders(
      <DayList
        sessions={[]}
        date={JULY_21}
        onSessionClick={vi.fn()}
        isLoading
      />,
    );
    expect(screen.getByText("Carregando sessões…")).toBeInTheDocument();
  });

  it('mostra "Nenhuma sessão neste dia" quando não há sessões para a data', () => {
    renderWithProviders(
      <DayList sessions={[]} date={JULY_21} onSessionClick={vi.fn()} />,
    );
    expect(screen.getByText("Nenhuma sessão neste dia")).toBeInTheDocument();
  });

  it("renderiza horário (HH:mm) e nome do cliente para sessão do dia", () => {
    renderWithProviders(
      <DayList
        sessions={[mockSession]}
        date={JULY_21}
        onSessionClick={vi.fn()}
      />,
    );

    // Local time 10:00 renders as '10:00' in any timezone
    expect(screen.getByText("10:00")).toBeInTheDocument();
    expect(screen.getByText("Ana Lima")).toBeInTheDocument();
  });

  it("sessões de outras datas não aparecem — filtro por data", () => {
    const sessionOnJuly22: Session = {
      ...mockSession,
      id: "session-2",
      client_name: "Carlos Souza",
      scheduled_at: new Date(2025, 6, 22, 10, 0, 0).toISOString(), // July 22 local — different day
    };

    renderWithProviders(
      <DayList
        sessions={[sessionOnJuly22]}
        date={JULY_21} // Viewing July 21
        onSessionClick={vi.fn()}
      />,
    );

    // July 22 session must not appear; empty state is shown instead
    expect(screen.queryByText("Carlos Souza")).not.toBeInTheDocument();
    expect(screen.getByText("Nenhuma sessão neste dia")).toBeInTheDocument();
  });

  it("clicar na linha de uma sessão expande os botões de alteração de status", async () => {
    const user = userEvent.setup();

    renderWithProviders(
      <DayList
        sessions={[mockSession]}
        date={JULY_21}
        onSessionClick={vi.fn()}
      />,
    );

    // Status change panel is initially hidden
    expect(screen.queryByText("Alterar status:")).not.toBeInTheDocument();

    // Click on the client name row (not the "Editar" button which stops propagation)
    await user.click(screen.getByText("Ana Lima"));

    // Quick status panel should now be visible with all status labels
    expect(screen.getByText("Alterar status:")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Agendada" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Realizada" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Cancelada" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Faltou" })).toBeInTheDocument();
  });

  it('botão "Editar" chama onSessionClick com a sessão correta', async () => {
    const user = userEvent.setup();
    const onSessionClick = vi.fn();

    // Mock PATCH in case the update mutation fires (it doesn't here, but defensive)
    server.use(
      http.patch(BASE_URL + "/agenda/sessions/:id", () =>
        HttpResponse.json(mockSession),
      ),
    );

    renderWithProviders(
      <DayList
        sessions={[mockSession]}
        date={JULY_21}
        onSessionClick={onSessionClick}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Editar" }));

    expect(onSessionClick).toHaveBeenCalledTimes(1);
    expect(onSessionClick).toHaveBeenCalledWith(mockSession);
  });
});
