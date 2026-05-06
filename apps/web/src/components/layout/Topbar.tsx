/**
 * Topbar — application header bar.
 *
 * Responsibilities:
 *  - Sidebar toggle (hamburger)
 *  - Breadcrumb showing current page title
 *  - Current date (center, hidden on mobile)
 *  - Search + Bell+notif-dot icon buttons
 *  - "+ Nova Sessão" primary CTA → navigates to /agenda
 *  - User avatar (derived from professional name)
 *
 * Dark-only: theme toggle removed (ThemeContext is now dark-only).
 */

import { Bell, Menu, Plus, Search } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Avatar, getInitials } from "@/components/shared/Avatar";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface TopbarProps {
  onToggleSidebar: () => void;
  title: string;
  professional: { full_name: string } | null;
}

// ---------------------------------------------------------------------------
// Topbar
// ---------------------------------------------------------------------------

export function Topbar({ onToggleSidebar, title, professional }: TopbarProps) {
  const navigate = useNavigate();
  const initials = professional ? getInitials(professional.full_name) : "?";

  const dateString = new Date().toLocaleDateString("pt-BR", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  return (
    <header
      className="flex items-center gap-[12px] flex-shrink-0 px-[20px] z-[30]"
      style={{
        height: "var(--topbar-height)",
        minHeight: "var(--topbar-height)",
        background: "rgba(15, 15, 25, 0.80)",
        backdropFilter: "blur(20px)",
        WebkitBackdropFilter: "blur(20px)",
        borderBottom: "1px solid var(--border-default)",
      }}
    >
      {/* ── Left — hamburger + breadcrumb ── */}
      <button
        type="button"
        onClick={onToggleSidebar}
        aria-label="Alternar menu"
        className="icon-btn"
      >
        <Menu size={16} />
      </button>

      <span
        className="flex-shrink-0"
        style={{
          fontFamily: "var(--font-heading)",
          fontSize: "14px",
          fontWeight: 700,
          color: "var(--text-primary)",
        }}
      >
        {title}
      </span>

      {/* ── Center — current date (hidden on mobile) ── */}
      <span
        className="hidden md:block mx-auto truncate"
        style={{ fontSize: "12px", color: "var(--text-muted)" }}
      >
        {dateString}
      </span>

      {/* ── Right — action cluster ── */}
      <div className="flex items-center gap-[4px] ml-auto md:ml-0">
        {/* Search */}
        <button type="button" aria-label="Pesquisar" className="icon-btn">
          <Search size={15} />
        </button>

        {/* Notifications with red dot */}
        <div className="relative">
          <button type="button" aria-label="Notificações" className="icon-btn">
            <Bell size={15} />
          </button>
          {/* Red badge dot */}
          <span
            className="absolute top-[6px] right-[6px] w-[7px] h-[7px] rounded-full pointer-events-none"
            style={{
              background: "var(--danger)",
              border: "1.5px solid var(--bg-page)",
            }}
            aria-hidden="true"
          />
        </div>

        {/* "+ Nova Sessão" primary CTA */}
        <button
          type="button"
          onClick={() => navigate("/agenda")}
          className="btn-primary ml-[6px]"
        >
          <Plus size={13} />
          Nova Sessão
        </button>

        {/* User avatar */}
        {professional && (
          <Avatar
            initials={initials}
            size="sm"
            className="cursor-pointer hover:opacity-80 transition-opacity duration-200 ml-[4px]"
          />
        )}
      </div>
    </header>
  );
}
