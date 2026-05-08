/**
 * Topbar — application header bar.
 *
 * Responsibilities:
 *  - Sidebar toggle (hamburger)
 *  - Breadcrumb showing current page title (.topbar-breadcrumb)
 *  - Current date in center (.topbar-date — hidden on mobile via CSS)
 *  - Search + Bell+notif-dot icon buttons (.icon-btn)
 *  - "+ Nova Sessão" primary CTA → navigates to /agenda
 *  - User avatar (.avatar.avatar-sm derived from professional name)
 *
 * Layout: .topbar class handles display:flex, gap, height, backdrop.
 * .topbar-date uses margin:0 auto (CSS) to push itself to center.
 * Icons: Font Awesome 6 via <i className="fas fa-...">
 */

import { useNavigate } from "react-router-dom";
import { getInitials } from "@/components/shared/Avatar";

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
    <header className="topbar">
      {/* ── Hamburger ── */}
      <button
        type="button"
        onClick={onToggleSidebar}
        aria-label="Alternar menu"
        className="icon-btn"
      >
        <i className="fas fa-bars" />
      </button>

      {/* ── Breadcrumb ── */}
      <span className="topbar-breadcrumb">{title}</span>

      {/* ── Current date — hidden on mobile via .topbar-date CSS ── */}
      <span className="topbar-date">{dateString}</span>

      {/* ── Search ── */}
      <button type="button" aria-label="Pesquisar" className="icon-btn">
        <i className="fas fa-magnifying-glass" />
      </button>

      {/* ── Notifications with red dot ── */}
      <button
        type="button"
        aria-label="Notificações"
        className="icon-btn"
        style={{ position: "relative" }}
      >
        <i className="fas fa-bell" />
        <span className="notif-badge" aria-hidden="true" />
      </button>

      {/* ── "+ Nova Sessão" primary CTA ── */}
      <button
        type="button"
        onClick={() => navigate("/agenda")}
        className="btn-primary"
      >
        <i className="fas fa-plus" /> Nova Sessão
      </button>

      {/* ── User avatar ── */}
      {professional && (
        <div
          className="avatar avatar-sm"
          style={{ marginLeft: 4, fontSize: 10 }}
        >
          {initials}
        </div>
      )}
    </header>
  );
}
