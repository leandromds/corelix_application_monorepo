import { http, HttpResponse } from "msw";
import userEvent from "@testing-library/user-event";

import { server, BASE_URL } from "@/test/server";
import { renderWithProviders, screen, waitFor } from "@/test/utils";
import { ClientForm } from "@/features/clients/components/ClientForm";
import type { Client } from "@/features/clients/types";

// ---------------------------------------------------------------------------
// Hoist mock before any imports resolve
// ---------------------------------------------------------------------------

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

function makeClient(overrides: Partial<Client> = {}): Client {
  return {
    id: "client-1",
    full_name: "Ana Lima",
    phone: "+5511999999999",
    email: "ana@example.com",
    notes: "Notas da Ana",
    is_active: true,
    whatsapp_opt_in: true,
    email_opt_in: false,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ClientForm", () => {
  it("não renderiza conteúdo do formulário quando open=false", () => {
    renderWithProviders(<ClientForm open={false} onOpenChange={vi.fn()} />);

    // Radix Dialog unmounts content when open=false (no forceMount)
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.queryByText("Novo Cliente")).not.toBeInTheDocument();
    expect(
      screen.queryByPlaceholderText("Nome do cliente"),
    ).not.toBeInTheDocument();
  });

  it('renderiza formulário com título "Novo Cliente" quando open=true sem client', () => {
    renderWithProviders(<ClientForm open={true} onOpenChange={vi.fn()} />);

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Novo Cliente")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Nome do cliente")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("+5511999999999")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Salvar" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Cancelar" }),
    ).toBeInTheDocument();
  });

  it('renderiza com título "Editar Cliente" e campos pré-preenchidos em modo edição', () => {
    const client = makeClient();

    renderWithProviders(
      <ClientForm open={true} onOpenChange={vi.fn()} client={client} />,
    );

    expect(screen.getByText("Editar Cliente")).toBeInTheDocument();

    const nameInput = screen.getByPlaceholderText(
      "Nome do cliente",
    ) as HTMLInputElement;
    expect(nameInput.value).toBe("Ana Lima");

    const phoneInput = screen.getByPlaceholderText(
      "+5511999999999",
    ) as HTMLInputElement;
    expect(phoneInput.value).toBe("+5511999999999");

    const emailInput = screen.getByPlaceholderText(
      "email@exemplo.com",
    ) as HTMLInputElement;
    expect(emailInput.value).toBe("ana@example.com");

    // whatsapp_opt_in=true → first checkbox should be checked.
    // The form uses a plain <Label> (not FormLabel) without htmlFor, so the
    // Radix Checkbox <button role="checkbox"> has no accessible name.
    // TODO: review — adding htmlFor to the label would allow name-based queries
    const [whatsappCheckbox] = screen.getAllByRole("checkbox");
    expect(whatsappCheckbox).toBeChecked();
  });

  it("exibe mensagem de erro quando full_name tem menos de 2 caracteres", async () => {
    const user = userEvent.setup();

    renderWithProviders(<ClientForm open={true} onOpenChange={vi.fn()} />);

    // Type a single-char name (fails min(2) validation)
    await user.type(screen.getByPlaceholderText("Nome do cliente"), "A");

    // Submit
    await user.click(screen.getByRole("button", { name: "Salvar" }));

    await screen.findByText("Nome deve ter pelo menos 2 caracteres");
  });

  it("exibe mensagem de erro quando telefone tem formato inválido", async () => {
    const user = userEvent.setup();

    renderWithProviders(<ClientForm open={true} onOpenChange={vi.fn()} />);

    await user.type(screen.getByPlaceholderText("Nome do cliente"), "Ana Lima");
    // Missing +55 prefix
    await user.type(
      screen.getByPlaceholderText("+5511999999999"),
      "11999999999",
    );

    await user.click(screen.getByRole("button", { name: "Salvar" }));

    await screen.findByText("Formato: +5511999999999");
  });

  it("chama onOpenChange(false) após criação bem-sucedida", async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();

    server.use(
      // Needed because invalidateQueries will refetch after create
      http.get(BASE_URL + "/clients", () => HttpResponse.json([])),
      http.post(BASE_URL + "/clients", () =>
        HttpResponse.json(makeClient(), { status: 201 }),
      ),
    );

    renderWithProviders(<ClientForm open={true} onOpenChange={onOpenChange} />);

    await user.type(screen.getByPlaceholderText("Nome do cliente"), "Ana Lima");
    await user.type(
      screen.getByPlaceholderText("+5511999999999"),
      "+5511999999999",
    );
    await user.click(screen.getByRole("button", { name: "Salvar" }));

    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
  });

  it("botão Cancelar chama onOpenChange(false) imediatamente", async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();

    renderWithProviders(<ClientForm open={true} onOpenChange={onOpenChange} />);

    await user.click(screen.getByRole("button", { name: "Cancelar" }));

    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
