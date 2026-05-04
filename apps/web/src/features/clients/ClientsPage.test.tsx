import { http, HttpResponse } from "msw";
import userEvent from "@testing-library/user-event";

import { server, BASE_URL } from "@/test/server";
import { renderWithProviders, screen, waitFor } from "@/test/utils";
import { ClientsPage } from "@/features/clients/ClientsPage";
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

describe("ClientsPage", () => {
  it("mostra skeleton de carregamento antes dos dados chegarem", () => {
    // Handler registered but never resolved synchronously → first render is isLoading=true
    server.use(http.get(BASE_URL + "/clients", () => HttpResponse.json([])));

    renderWithProviders(<ClientsPage />);

    // SkeletonRows are mounted synchronously during the first render (isLoading=true)
    const pulsingEls = document.querySelectorAll(".animate-pulse");
    expect(pulsingEls.length).toBeGreaterThan(0);
  });

  it("exibe a lista de clientes após o fetch completar", async () => {
    const clients = [
      makeClient({ id: "1", full_name: "Ana Lima" }),
      makeClient({ id: "2", full_name: "João Silva" }),
    ];

    server.use(
      http.get(BASE_URL + "/clients", () => HttpResponse.json(clients)),
    );

    renderWithProviders(<ClientsPage />);

    // findBy* waits for the async data to appear
    expect(await screen.findByText("Ana Lima")).toBeInTheDocument();
    expect(screen.getByText("João Silva")).toBeInTheDocument();
  });

  it('abre o dialog "Novo Cliente" ao clicar no botão correspondente', async () => {
    const user = userEvent.setup();

    server.use(http.get(BASE_URL + "/clients", () => HttpResponse.json([])));

    renderWithProviders(<ClientsPage />);

    // Dialog should not be open yet
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    // The button with text "Novo Cliente" is always visible in the toolbar
    await user.click(screen.getByRole("button", { name: /novo cliente/i }));

    // After click the Radix Dialog mounts its content (role="dialog")
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    // The dialog title should match create mode
    expect(
      screen.getByText("Preencha os dados do novo cliente."),
    ).toBeInTheDocument();
  });

  it("busca filtra a lista após o debounce de 300 ms", async () => {
    const user = userEvent.setup();

    const anaClient = makeClient({ id: "1", full_name: "Ana Lima" });
    const joaoClient = makeClient({ id: "2", full_name: "João Silva" });

    server.use(
      http.get(BASE_URL + "/clients", ({ request }) => {
        const url = new URL(request.url);
        const search = url.searchParams.get("search");
        // Simulate server-side filter
        if (search === "Ana") return HttpResponse.json([anaClient]);
        return HttpResponse.json([anaClient, joaoClient]);
      }),
    );

    renderWithProviders(<ClientsPage />);

    // Wait for both clients to appear (initial fetch with no search)
    await screen.findByText("João Silva");
    await screen.findByText("Ana Lima");

    // Type in the search input (aria-label set on the Input)
    const searchInput = screen.getByRole("searchbox", {
      name: /buscar cliente/i,
    });
    await user.type(searchInput, "Ana");

    // After the 300 ms debounce + re-fetch the filtered results must be stable:
    // both assertions must hold simultaneously. Using two separate assertions
    // (check João gone THEN check Ana present) would wrongly succeed during the
    // isLoading=true gap when the new query key triggers a fresh fetch and
    // temporarily clears all client rows.
    await waitFor(
      () => {
        expect(screen.getByText("Ana Lima")).toBeInTheDocument();
        expect(screen.queryByText("João Silva")).not.toBeInTheDocument();
      },
      { timeout: 2000 },
    );
  });

  it('toggle "Mostrar inativos" envia is_active=undefined (omite o parâmetro)', async () => {
    const user = userEvent.setup();
    const requestUrls: string[] = [];

    server.use(
      http.get(BASE_URL + "/clients", ({ request }) => {
        requestUrls.push(request.url);
        return HttpResponse.json([]);
      }),
    );

    renderWithProviders(<ClientsPage />);

    // Wait for initial request (should contain is_active=true)
    await waitFor(() => expect(requestUrls.length).toBeGreaterThan(0));
    expect(requestUrls[0]).toContain("is_active=true");

    // Toggle "Mostrar inativos" checkbox
    await user.click(
      screen.getByRole("checkbox", { name: /mostrar inativos/i }),
    );

    // A new request should be made — axios omits undefined params, so is_active absent
    await waitFor(() => expect(requestUrls.length).toBeGreaterThan(1));
    const lastUrl = requestUrls[requestUrls.length - 1]!;
    expect(lastUrl).not.toContain("is_active");
  });
});
