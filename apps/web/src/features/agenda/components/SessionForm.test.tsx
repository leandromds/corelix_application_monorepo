/**
 * Tests for SessionForm component.
 *
 * SessionForm always calls useClients (hook is unconditional), so the
 * /clients endpoint is mocked in every test even when open=false.
 *
 * sonner is mocked because SessionForm uses useCreateSession and
 * useUpdateSession internally (both call toast on settle).
 */

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import { http, HttpResponse } from "msw";
import { server, BASE_URL } from "@/test/server";
import { renderWithProviders, screen } from "@/test/utils";
import userEvent from "@testing-library/user-event";
import { SessionForm } from "./SessionForm";
import type { Session } from "../types";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

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

const mockSession: Session = {
  id: "session-1",
  client_id: "client-1",
  client_name: "Ana Lima",
  scheduled_at: "2025-07-21T10:00:00.000Z",
  duration_minutes: 50,
  price: "150.00",
  status: "scheduled",
  notes: null,
  is_active: true,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Register default MSW handlers for every SessionForm test. */
function setupClientsMock() {
  server.use(
    http.get(BASE_URL + "/clients", () => HttpResponse.json([mockClient])),
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("SessionForm", () => {
  it("não renderiza o conteúdo do diálogo quando open=false", () => {
    setupClientsMock();

    renderWithProviders(<SessionForm open={false} onOpenChange={vi.fn()} />);

    // Radix Dialog unmounts DialogContent when open=false
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it('renderiza o formulário com título "Nova Sessão" quando open=true', async () => {
    setupClientsMock();

    renderWithProviders(<SessionForm open={true} onOpenChange={vi.fn()} />);

    // Dialog mounts immediately when open=true
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Nova Sessão" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Agendar" })).toBeInTheDocument();
  });

  it('renderiza com título "Editar Sessão" quando uma sessão é passada', async () => {
    setupClientsMock();

    renderWithProviders(
      <SessionForm open={true} onOpenChange={vi.fn()} session={mockSession} />,
    );

    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Editar Sessão" }),
    ).toBeInTheDocument();
    // Edit mode uses "Salvar", not "Agendar"
    expect(screen.getByRole("button", { name: "Salvar" })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Agendar" }),
    ).not.toBeInTheDocument();
  });

  it("exibe mensagem de erro de validação para client_id vazio ao submeter", async () => {
    setupClientsMock();
    const user = userEvent.setup();

    renderWithProviders(<SessionForm open={true} onOpenChange={vi.fn()} />);

    await screen.findByRole("dialog");

    // Submit the form without selecting a client — validation fires
    await user.click(screen.getByRole("button", { name: "Agendar" }));

    // React Hook Form renders the error message as a <p> element.
    // The Select placeholder also contains 'Selecione um cliente' (inside a <span>),
    // so we scope to selector 'p' to avoid "Found multiple elements" error.
    expect(
      await screen.findByText("Selecione um cliente", { selector: "p" }),
    ).toBeInTheDocument();
  });

  it("botão Cancelar chama onOpenChange(false)", async () => {
    setupClientsMock();
    const onOpenChange = vi.fn();
    const user = userEvent.setup();

    renderWithProviders(
      <SessionForm open={true} onOpenChange={onOpenChange} />,
    );

    await screen.findByRole("dialog");

    await user.click(screen.getByRole("button", { name: "Cancelar" }));

    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
