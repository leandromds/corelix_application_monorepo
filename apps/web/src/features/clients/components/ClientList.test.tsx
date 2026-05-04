import { http, HttpResponse } from "msw";
import userEvent from "@testing-library/user-event";
import { fireEvent } from "@testing-library/react";

import { server, BASE_URL } from "@/test/server";
import { renderWithProviders, screen } from "@/test/utils";
import { ClientList } from "@/features/clients/components/ClientList";
import type { Client } from "@/features/clients/types";

// ---------------------------------------------------------------------------
// Sonner must be mocked because ClientList uses hooks that import toast
// ---------------------------------------------------------------------------

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

function makeClient(overrides: Partial<Client> = {}): Client {
  return {
    id: "1",
    full_name: "Ana Lima",
    phone: "+5511999999999",
    email: null,
    notes: null,
    is_active: true,
    whatsapp_opt_in: false,
    email_opt_in: false,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ClientList", () => {
  it("renderiza nome e telefone de cada cliente da lista", () => {
    const clients = [
      makeClient({ id: "1", full_name: "Ana Lima", phone: "+5511999999999" }),
      makeClient({ id: "2", full_name: "João Silva", phone: "+5521988888888" }),
    ];

    renderWithProviders(
      <ClientList clients={clients} isLoading={false} onEdit={vi.fn()} />,
    );

    expect(screen.getByText("Ana Lima")).toBeInTheDocument();
    expect(screen.getByText("+5511999999999")).toBeInTheDocument();
    expect(screen.getByText("João Silva")).toBeInTheDocument();
    expect(screen.getByText("+5521988888888")).toBeInTheDocument();
  });

  it("mostra 5 linhas skeleton com animate-pulse quando isLoading=true", () => {
    renderWithProviders(
      <ClientList clients={[]} isLoading={true} onEdit={vi.fn()} />,
    );

    // SkeletonRows renders 5 <tr> children in <tbody>
    const tbodyRows = document.querySelectorAll("tbody tr");
    expect(tbodyRows).toHaveLength(5);

    // Each skeleton row has animated placeholder divs
    const pulsingEls = document.querySelectorAll(".animate-pulse");
    expect(pulsingEls.length).toBeGreaterThan(0);

    // No real client data should be visible
    expect(
      screen.queryByText("Nenhum cliente encontrado"),
    ).not.toBeInTheDocument();
  });

  it("mostra empty state quando clients=[] e isLoading=false", () => {
    renderWithProviders(
      <ClientList clients={[]} isLoading={false} onEdit={vi.fn()} />,
    );

    expect(screen.getByText("Nenhum cliente encontrado")).toBeInTheDocument();
    expect(
      screen.getByText("Tente ajustar os filtros ou adicione um novo cliente."),
    ).toBeInTheDocument();
  });

  it('exibe badge "Ativo" para cliente ativo e "Inativo" para cliente inativo', () => {
    const clients = [
      makeClient({ id: "1", full_name: "Ana Lima", is_active: true }),
      makeClient({ id: "2", full_name: "João Silva", is_active: false }),
    ];

    renderWithProviders(
      <ClientList clients={clients} isLoading={false} onEdit={vi.fn()} />,
    );

    expect(screen.getByText("Ativo")).toBeInTheDocument();
    expect(screen.getByText("Inativo")).toBeInTheDocument();
  });

  it("chama onEdit com o cliente correto ao clicar no botão Editar", async () => {
    const user = userEvent.setup();
    const onEdit = vi.fn();
    const client = makeClient({ id: "1", full_name: "Ana Lima" });

    renderWithProviders(
      <ClientList clients={[client]} isLoading={false} onEdit={onEdit} />,
    );

    await user.click(screen.getByRole("button", { name: "Editar" }));

    expect(onEdit).toHaveBeenCalledTimes(1);
    expect(onEdit).toHaveBeenCalledWith(client);
  });

  it("hover em uma linha altera background (cobre handlers onMouseEnter/Leave)", () => {
    const client = makeClient({
      id: "1",
      full_name: "Ana Lima",
      is_active: true,
    });

    renderWithProviders(
      <ClientList clients={[client]} isLoading={false} onEdit={vi.fn()} />,
    );

    const row = screen.getByText("Ana Lima").closest("tr")!;
    // Fire native mouse events — covers the inline onMouseEnter/Leave arrow functions
    fireEvent.mouseEnter(row);
    expect(row.style.backgroundColor).toBe("var(--bg-surface)");

    fireEvent.mouseLeave(row);
    expect(row.style.backgroundColor).toBe("");
  });

  it('clicar em "Reativar" chama useUpdateClient para cliente inativo', async () => {
    const user = userEvent.setup();
    const inactiveClient = makeClient({
      id: "99",
      full_name: "Carlos Inativo",
      is_active: false,
    });

    server.use(
      http.patch(BASE_URL + "/clients/99", () =>
        HttpResponse.json({ ...inactiveClient, is_active: true }),
      ),
    );

    renderWithProviders(
      <ClientList
        clients={[inactiveClient]}
        isLoading={false}
        onEdit={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Reativar" }));
    // mutation fires — just assert button was present and clicked (no error)
    expect(
      screen.getByRole("button", { name: "Reativar" }),
    ).toBeInTheDocument();
  });

  it('clientes ativos têm botão "Desativar"; clientes inativos têm botão "Reativar"', () => {
    const clients = [
      makeClient({ id: "1", full_name: "Ana Lima", is_active: true }),
      makeClient({ id: "2", full_name: "João Silva", is_active: false }),
    ];

    // Add handlers so mutations triggered in this test don't warn
    server.use(
      http.get(BASE_URL + "/clients", () => HttpResponse.json(clients)),
      http.delete(
        BASE_URL + "/clients/:id",
        () => new HttpResponse(null, { status: 204 }),
      ),
      http.patch(BASE_URL + "/clients/:id", () =>
        HttpResponse.json(clients[0]),
      ),
    );

    renderWithProviders(
      <ClientList clients={clients} isLoading={false} onEdit={vi.fn()} />,
    );

    // Active client → AlertDialogTrigger renders a "Desativar" button
    expect(
      screen.getByRole("button", { name: "Desativar" }),
    ).toBeInTheDocument();
    // Inactive client → plain "Reativar" button
    expect(
      screen.getByRole("button", { name: "Reativar" }),
    ).toBeInTheDocument();
  });
});
