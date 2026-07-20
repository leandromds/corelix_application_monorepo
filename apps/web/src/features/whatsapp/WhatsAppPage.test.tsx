/**
 * WhatsAppPage integration tests.
 *
 * Strategy:
 * - MSW intercepts GET /whatsapp/conversations and GET /whatsapp/conversations/{id}
 * - Tests verify the list → detail interaction flow
 * - No fake timers needed
 */

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import { http, HttpResponse } from "msw";
import userEvent from "@testing-library/user-event";

import { server, BASE_URL } from "@/test/server";
import { renderWithProviders, screen } from "@/test/utils";
import { WhatsAppPage } from "./WhatsAppPage";
import type { Conversation, ConversationWithMessages } from "./types";

// ---------------------------------------------------------------------------
// Factories
// ---------------------------------------------------------------------------

function makeConversation(overrides: Partial<Conversation> = {}): Conversation {
  return {
    id: "conv-1",
    client_phone: "+5511999999999",
    client_id: "client-1",
    status: "active",
    mode: "ai",
    started_at: "2024-01-01T10:00:00Z",
    last_message_at: "2024-01-01T10:30:00Z",
    ended_at: null,
    ...overrides,
  };
}

function makeDetail(conversationId = "conv-1"): ConversationWithMessages {
  return {
    conversation: makeConversation({ id: conversationId }),
    messages: [
      {
        id: "msg-1",
        direction: "inbound",
        sender_type: "client",
        content: "Mensagem do cliente",
        sent_at: "2024-01-01T10:00:00Z",
      },
      {
        id: "msg-2",
        direction: "outbound",
        sender_type: "ai",
        content: "Resposta da IA",
        sent_at: "2024-01-01T10:00:30Z",
      },
    ],
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("WhatsAppPage", () => {
  it("renderiza o título da página", () => {
    server.use(
      http.get(BASE_URL + "/whatsapp/conversations", () =>
        HttpResponse.json([]),
      ),
    );

    renderWithProviders(<WhatsAppPage />);
    expect(screen.getByText("WhatsApp")).toBeInTheDocument();
  });

  it("exibe estado vazio quando não há conversas", async () => {
    server.use(
      http.get(BASE_URL + "/whatsapp/conversations", () =>
        HttpResponse.json([]),
      ),
    );

    renderWithProviders(<WhatsAppPage />);

    expect(await screen.findByText(/nenhuma conversa/i)).toBeInTheDocument();
  });

  it("exibe a lista de conversas após o fetch", async () => {
    const conversations = [
      makeConversation({ id: "conv-1", client_phone: "+5511111111111" }),
      makeConversation({ id: "conv-2", client_phone: "+5522222222222" }),
    ];

    server.use(
      http.get(BASE_URL + "/whatsapp/conversations", () =>
        HttpResponse.json(conversations),
      ),
    );

    renderWithProviders(<WhatsAppPage />);

    expect(await screen.findByText("+5511111111111")).toBeInTheDocument();
    expect(screen.getByText("+5522222222222")).toBeInTheDocument();
  });

  it("exibe estado vazio de thread antes de selecionar uma conversa", async () => {
    server.use(
      http.get(BASE_URL + "/whatsapp/conversations", () =>
        HttpResponse.json([makeConversation()]),
      ),
    );

    renderWithProviders(<WhatsAppPage />);

    // Thread panel shows empty state
    expect(
      await screen.findByText(/selecione uma conversa/i),
    ).toBeInTheDocument();
  });

  it("clicar em uma conversa carrega o histórico de mensagens", async () => {
    const user = userEvent.setup();

    server.use(
      http.get(BASE_URL + "/whatsapp/conversations", () =>
        HttpResponse.json([makeConversation()]),
      ),
      http.get(BASE_URL + "/whatsapp/conversations/conv-1", () =>
        HttpResponse.json(makeDetail()),
      ),
    );

    renderWithProviders(<WhatsAppPage />);

    const convBtn = await screen.findByRole("button", {
      name: /\+5511999999999/i,
    });
    await user.click(convBtn);

    expect(await screen.findByText("Mensagem do cliente")).toBeInTheDocument();
    expect(screen.getByText("Resposta da IA")).toBeInTheDocument();
  });
});
