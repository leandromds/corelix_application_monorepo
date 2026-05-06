/**
 * WhatsAppPage — split-pane layout: conversation list (left) + thread (right).
 *
 * State management:
 * - selectedConversationId: which conversation the user clicked
 * - useConversations() owns the list query (no status filter on this page — show all)
 *
 * Responsiveness:
 * - On narrow screens (<640 px) the split is hidden and only the list is shown
 *   until a conversation is selected, at which point only the thread is shown.
 *   Back-button logic uses selectedConversationId reset.
 */

import { useState, useEffect, useRef } from "react";
import posthog from "posthog-js";

import { useConversations } from "./hooks/useConversations";
import { ConversationList } from "./components/ConversationList";
import { MessageThread } from "./components/MessageThread";

export function WhatsAppPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const { data: conversations = [], isLoading } = useConversations();

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

  // ── Responsive: detect narrow viewport ──────────────────────────────────
  // We avoid a media-query hook import — just use a simple window check.
  const isNarrow = typeof window !== "undefined" && window.innerWidth < 640;

  // In narrow mode, show only the list when nothing is selected,
  // and only the thread when a conversation is selected.
  const showList = !isNarrow || selectedId === null;
  const showThread = !isNarrow || selectedId !== null;

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <div
      style={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        opacity: mounted ? 1 : 0,
        transform: mounted ? "translateY(0)" : "translateY(10px)",
        transition: "opacity 0.25s ease, transform 0.25s ease",
      }}
    >
      {/* ── Page header ── */}
      <div
        style={{
          padding: "20px 24px 16px",
          borderBottom: "1px solid var(--border-default)",
          flexShrink: 0,
        }}
      >
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
          {conversations.length}{" "}
          {conversations.length === 1 ? "conversa" : "conversas"}
        </p>
      </div>

      {/* ── Split pane ── */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {/* Left — conversation list */}
        {showList && (
          <div
            style={{
              width: 320,
              minWidth: 280,
              borderRight: "1px solid var(--border-default)",
              overflowY: "auto",
              backgroundColor: "var(--bg-surface)",
              flexShrink: 0,
            }}
          >
            {/* Back button — mobile only */}
            {isNarrow && selectedId && (
              <button
                onClick={() => setSelectedId(null)}
                style={{
                  display: "block",
                  width: "100%",
                  padding: "12px 16px",
                  textAlign: "left",
                  fontSize: 13,
                  fontWeight: 600,
                  color: "var(--color-primary)",
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  borderBottom: "1px solid var(--border-default)",
                }}
              >
                ← Voltar
              </button>
            )}

            <ConversationList
              conversations={conversations}
              isLoading={isLoading}
              selectedId={selectedId}
              onSelect={setSelectedId}
            />
          </div>
        )}

        {/* Right — message thread */}
        {showThread && (
          <div
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
              backgroundColor: "var(--bg-surface-card)",
            }}
          >
            <MessageThread conversationId={selectedId} />
          </div>
        )}
      </div>
    </div>
  );
}
