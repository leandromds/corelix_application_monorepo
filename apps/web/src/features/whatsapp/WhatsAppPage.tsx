/**
 * WhatsAppPage — split-pane layout: conversation list (left) + thread (right).
 *
 * State management:
 * - selectedConversationId: which conversation the user clicked
 * - searchQuery: client-side phone filter on the conversation list
 * - useConversations() owns the list query
 * - useMessages(selectedId) fetches the message thread on demand
 * - useHandoff() handles AI → professional escalation
 *
 * Responsiveness:
 * - On narrow screens (<640 px) only one pane is shown at a time.
 *   Back-button logic resets selectedConversationId.
 */

import { useState, useEffect, useRef } from "react";
import posthog from "posthog-js";
import { MessageCircle, Bot, Lock, ExternalLink, Search } from "lucide-react";

import { useConversations } from "./hooks/useConversations";
import { useMessages } from "./hooks/useMessages";
import { useHandoff } from "./hooks/useHandoff";
import { ConversationList } from "./components/ConversationList";
import type { Message, ConversationStatus, ConversationMode } from "./types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatTime(iso: string): string {
  try {
    return new Intl.DateTimeFormat("pt-BR", {
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(iso));
  } catch {
    return "";
  }
}

// ---------------------------------------------------------------------------
// Status badge CSS class
// ---------------------------------------------------------------------------

const STATUS_BADGE_CLASS: Record<ConversationStatus, string> = {
  active: "badge-confirmed",
  resolved: "badge-noshow",
  waiting_professional: "badge-pending",
};

const STATUS_LABEL: Record<ConversationStatus, string> = {
  active: "Ativa",
  resolved: "Resolvida",
  waiting_professional: "Aguardando",
};

// ---------------------------------------------------------------------------
// Avatar color variant (deterministic by phone string)
// ---------------------------------------------------------------------------

const AVATAR_PALETTE = [
  {
    bg: "rgba(99,102,241,0.25)",
    border: "rgba(99,102,241,0.5)",
    color: "#a5b4fc",
  },
  {
    bg: "rgba(34,211,238,0.20)",
    border: "rgba(34,211,238,0.5)",
    color: "#67e8f9",
  },
  {
    bg: "rgba(52,211,153,0.20)",
    border: "rgba(52,211,153,0.5)",
    color: "#6ee7b7",
  },
  {
    bg: "rgba(251,191,36,0.20)",
    border: "rgba(251,191,36,0.5)",
    color: "#fcd34d",
  },
  {
    bg: "rgba(248,113,113,0.20)",
    border: "rgba(248,113,113,0.5)",
    color: "#fca5a5",
  },
] as const;

function getAvatarVariant(phone: string) {
  let h = 0;
  for (const c of phone) h = (h << 5) - h + c.charCodeAt(0);
  return AVATAR_PALETTE[Math.abs(h) % AVATAR_PALETTE.length]!;
}

function phoneInitials(phone: string): string {
  const digits = phone.replace(/\D/g, "");
  return digits.slice(-2);
}

// ---------------------------------------------------------------------------
// MessageBubble
// ---------------------------------------------------------------------------

function MessageBubble({ message }: { message: Message }) {
  const isOutbound = message.direction === "outbound";
  const isAI = message.sender_type === "ai";

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: isOutbound ? "flex-end" : "flex-start",
        marginBottom: 12,
      }}
    >
      {/* AI label */}
      {isAI && (
        <span
          style={{
            fontSize: 10,
            color: "#a78bfa",
            fontWeight: 700,
            marginBottom: 3,
            textTransform: "uppercase",
            letterSpacing: "0.06em",
            display: "flex",
            alignItems: "center",
            gap: 4,
          }}
        >
          <Bot size={10} aria-hidden /> Resposta IA
        </span>
      )}

      {/* Bubble */}
      <div
        style={{
          maxWidth: "70%",
          padding: "10px 14px",
          borderRadius: isOutbound
            ? "14px 14px 4px 14px"
            : "14px 14px 14px 4px",
          background: isAI
            ? "rgba(139,92,246,0.12)"
            : isOutbound
              ? "rgba(99,102,241,0.22)"
              : "var(--bg-elevated, rgba(255,255,255,0.08))",
          border: isAI
            ? "1px solid rgba(139,92,246,0.35)"
            : "1px solid transparent",
          color: "var(--text-primary)",
          fontSize: 13,
          lineHeight: 1.55,
          wordBreak: "break-word",
        }}
      >
        {message.content}
      </div>

      {/* Timestamp */}
      <span
        style={{
          fontSize: 10,
          color: "var(--text-muted)",
          marginTop: 3,
        }}
      >
        {formatTime(message.sent_at)}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// WhatsAppPage
// ---------------------------------------------------------------------------

export function WhatsAppPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const { data: conversations = [], isLoading } = useConversations();

  // Fetch message thread when a conversation is selected
  const { data: messageData, isLoading: messagesLoading } =
    useMessages(selectedId);
  const handoff = useHandoff();

  // Fire 'whatsapp_connected' once when conversations first load with data.
  // useRef guard prevents duplicate fires on StrictMode double-invoke.
  const capturedRef = useRef(false);
  useEffect(() => {
    if (!capturedRef.current && !isLoading && conversations.length > 0) {
      capturedRef.current = true;
      posthog.capture("whatsapp_connected", {
        conversation_count: conversations.length,
      });
    }
  }, [isLoading, conversations.length]);

  // ── Derived values ────────────────────────────────────────────────────
  const isConnected = conversations.length > 0;

  const filteredConversations =
    searchQuery.trim() === ""
      ? conversations
      : conversations.filter((c) =>
          c.client_phone.toLowerCase().includes(searchQuery.toLowerCase()),
        );

  // Selected conversation data: prefer detailed response, fall back to list entry
  const selectedConvFromList = conversations.find((c) => c.id === selectedId);
  const conversationDetail = messageData?.conversation;
  const displayConversation = conversationDetail ?? selectedConvFromList;

  const messages = messageData?.messages ?? [];

  const canHandoff =
    (conversationDetail?.mode as ConversationMode) === "ai" &&
    (conversationDetail?.status as ConversationStatus) === "active";

  // ── Responsive ────────────────────────────────────────────────────────
  const isNarrow = typeof window !== "undefined" && window.innerWidth < 640;
  const showList = !isNarrow || selectedId === null;
  const showThread = !isNarrow || selectedId !== null;

  // ── Render ────────────────────────────────────────────────────────────
  return (
    <div
      style={{
        padding: 24,
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        gap: 20,
        opacity: mounted ? 1 : 0,
        transform: mounted ? "translateY(0)" : "translateY(10px)",
        transition: "opacity 0.25s ease, transform 0.25s ease",
      }}
    >
      {/* ── Page header ──────────────────────────────────────────────── */}
      <div
        className="animate-slide-up"
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <div>
          <h2
            style={{
              fontFamily: "var(--font-heading)",
              fontWeight: 700,
              fontSize: 24,
              color: "var(--text-primary)",
              margin: 0,
            }}
          >
            WhatsApp
          </h2>
          <p
            style={{
              fontSize: 14,
              color: "var(--text-muted)",
              margin: "4px 0 0",
            }}
          >
            Monitoramento de conversas via IA
          </p>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {isConnected && (
            <span className="badge-confirmed" style={{ fontSize: 12 }}>
              ● Conectado
            </span>
          )}
          <a
            href="https://web.whatsapp.com"
            target="_blank"
            rel="noopener noreferrer"
            className="btn-secondary"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              textDecoration: "none",
            }}
          >
            Abrir WhatsApp
            <ExternalLink size={13} aria-hidden />
          </a>
        </div>
      </div>

      {/* ── Two-pane layout ───────────────────────────────────────────── */}
      <div
        className="animate-slide-up animate-delay-1"
        style={{
          display: "grid",
          gridTemplateColumns: isNarrow ? "1fr" : "300px 1fr",
          gap: 16,
          flex: 1,
          minHeight: 0,
        }}
      >
        {/* ── Left: conversation list ──────────────────────────────── */}
        {showList && (
          <div
            className="glass-card"
            style={{
              padding: 0,
              overflow: "hidden",
              display: "flex",
              flexDirection: "column",
            }}
          >
            {/* Search input */}
            <div
              style={{
                padding: "12px 16px",
                borderBottom: "1px solid var(--border-default)",
                flexShrink: 0,
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  background: "var(--bg-elevated, rgba(255,255,255,0.08))",
                  borderRadius: 8,
                  border: "1px solid var(--border-default)",
                  padding: "6px 10px",
                }}
              >
                <Search
                  size={13}
                  aria-hidden
                  style={{ color: "var(--text-muted)", flexShrink: 0 }}
                />
                <input
                  type="text"
                  placeholder="Buscar conversa…"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  aria-label="Buscar conversa"
                  style={{
                    flex: 1,
                    background: "none",
                    border: "none",
                    outline: "none",
                    fontSize: 13,
                    color: "var(--text-primary)",
                  }}
                />
              </div>
            </div>

            {/* Back button (mobile only) */}
            {isNarrow && selectedId && (
              <button
                onClick={() => setSelectedId(null)}
                style={{
                  display: "block",
                  width: "100%",
                  padding: "10px 16px",
                  textAlign: "left",
                  fontSize: 13,
                  fontWeight: 600,
                  color: "rgba(139,92,246,0.9)",
                  background: "none",
                  border: "none",
                  borderBottom: "1px solid var(--border-default)",
                  cursor: "pointer",
                }}
              >
                ← Voltar
              </button>
            )}

            {/* Conversation list */}
            <div style={{ overflowY: "auto", flex: 1 }}>
              <ConversationList
                conversations={filteredConversations}
                isLoading={isLoading}
                selectedId={selectedId}
                onSelect={setSelectedId}
              />
            </div>
          </div>
        )}

        {/* ── Right: message thread ────────────────────────────────── */}
        {showThread && (
          <div
            className="glass-card bordered"
            style={{
              display: "flex",
              flexDirection: "column",
              padding: 0,
              overflow: "hidden",
            }}
          >
            {!selectedId ? (
              /* Empty state */
              <div className="empty-state" style={{ flex: 1 }}>
                <div className="empty-icon">
                  <MessageCircle size={40} aria-hidden />
                </div>
                <p className="empty-title">
                  Selecione uma conversa para ver o histórico.
                </p>
                <p className="empty-desc">
                  {conversations.length === 0
                    ? "Conecte seu WhatsApp para começar"
                    : "Escolha uma conversa à esquerda"}
                </p>
              </div>
            ) : (
              <>
                {/* Header */}
                {displayConversation && (
                  <div
                    style={{
                      padding: "14px 20px",
                      borderBottom: "1px solid var(--border-default)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: 12,
                      flexShrink: 0,
                    }}
                  >
                    <div
                      style={{ display: "flex", alignItems: "center", gap: 12 }}
                    >
                      {/* Avatar */}
                      {(() => {
                        const av = getAvatarVariant(
                          displayConversation.client_phone,
                        );
                        return (
                          <div
                            style={{
                              width: 40,
                              height: 40,
                              borderRadius: "50%",
                              background: av.bg,
                              border: `1px solid ${av.border}`,
                              color: av.color,
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              fontSize: 12,
                              fontWeight: 700,
                              flexShrink: 0,
                            }}
                          >
                            {phoneInitials(displayConversation.client_phone)}
                          </div>
                        );
                      })()}

                      <div>
                        <p
                          style={{
                            margin: 0,
                            fontWeight: 600,
                            color: "var(--text-primary)",
                            fontSize: 14,
                          }}
                        >
                          {displayConversation.client_phone}
                        </p>
                        <p
                          style={{
                            margin: 0,
                            fontSize: 11,
                            color: "var(--text-muted)",
                          }}
                        >
                          {displayConversation.client_phone}
                        </p>
                      </div>
                    </div>

                    <div
                      style={{ display: "flex", alignItems: "center", gap: 8 }}
                    >
                      <span
                        className={
                          STATUS_BADGE_CLASS[displayConversation.status]
                        }
                      >
                        {STATUS_LABEL[displayConversation.status]}
                      </span>
                      <a
                        href={`https://wa.me/${displayConversation.client_phone.replace(/\D/g, "")}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="btn-secondary"
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 5,
                          textDecoration: "none",
                          fontSize: 12,
                          padding: "4px 10px",
                        }}
                      >
                        Abrir no WhatsApp
                        <ExternalLink size={11} aria-hidden />
                      </a>
                    </div>
                  </div>
                )}

                {/* AI mode alert */}
                {displayConversation?.mode === "ai" &&
                  displayConversation?.status === "active" && (
                    <div
                      className="alert alert-info"
                      style={{ margin: "12px 16px 0", flexShrink: 0 }}
                    >
                      <Bot
                        size={13}
                        aria-hidden
                        style={{ marginRight: 6, verticalAlign: "middle" }}
                      />
                      IA detectou esta conversa e está respondendo
                      automaticamente.
                    </div>
                  )}

                {/* Messages scrollable area */}
                <div
                  style={{
                    flex: 1,
                    overflowY: "auto",
                    padding: "16px 20px",
                  }}
                >
                  {messagesLoading ? (
                    <div>
                      {Array.from({ length: 4 }).map((_, i) => (
                        <div
                          key={i}
                          className="animate-pulse"
                          style={{
                            marginBottom: 16,
                            display: "flex",
                            flexDirection: "column",
                            alignItems: i % 2 === 0 ? "flex-start" : "flex-end",
                          }}
                        >
                          <div
                            style={{
                              height: 36,
                              width: `${40 + (i % 3) * 15}%`,
                              borderRadius: 12,
                              background: "rgba(255,255,255,0.06)",
                            }}
                          />
                        </div>
                      ))}
                    </div>
                  ) : messages.length === 0 ? (
                    <p
                      style={{
                        textAlign: "center",
                        color: "var(--text-muted)",
                        fontSize: 13,
                      }}
                    >
                      Nenhuma mensagem nesta conversa.
                    </p>
                  ) : (
                    messages.map((msg) => (
                      <MessageBubble key={msg.id} message={msg} />
                    ))
                  )}
                </div>

                {/* Footer — locked notice + optional handoff button */}
                <div
                  style={{
                    padding: "10px 20px",
                    borderTop: "1px solid var(--border-default)",
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    flexShrink: 0,
                    flexWrap: "wrap",
                  }}
                >
                  <Lock
                    size={13}
                    aria-hidden
                    style={{ color: "var(--text-subtle)", flexShrink: 0 }}
                  />
                  <span
                    style={{
                      fontSize: 12,
                      color: "var(--text-subtle)",
                      flex: 1,
                    }}
                  >
                    Apenas monitoramento — respostas automáticas gerenciadas
                    pela IA
                  </span>
                  {canHandoff && (
                    <button
                      className="btn-primary"
                      style={{ fontSize: 12, padding: "4px 12px" }}
                      onClick={() => selectedId && handoff.mutate(selectedId)}
                      disabled={handoff.isPending}
                      aria-label="Assumir conversa"
                    >
                      {handoff.isPending ? "Assumindo…" : "Assumir conversa"}
                    </button>
                  )}
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
