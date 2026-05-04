/**
 * Topbar — application header bar.
 *
 * Responsibilities:
 *  - Sidebar toggle (hamburger)
 *  - Breadcrumb showing current page title
 *  - Current date (center, hidden on mobile)
 *  - Search, Notification, Theme-toggle icon buttons
 *  - "Nova Sessão" primary CTA → navigates to /agenda
 *  - User avatar (derived from professional name)
 */

import type { ReactNode } from "react";
import { Bell, Menu, Moon, Search, Sun } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { cn } from "@/lib/utils";
import { useTheme } from "@/contexts/ThemeContext";
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
// Sub-components
// ---------------------------------------------------------------------------

/** Minimal icon button that matches the wireframe `.icon-btn` style. */
interface IconButtonProps {
  onClick?: () => void;
  label: string;
  children: ReactNode;
  className?: string;
}

function IconButton({ onClick, label, children, className }: IconButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      className={cn(
        "flex items-center justify-center w-[34px] h-[34px] flex-shrink-0 cursor-pointer",
        "rounded-[var(--radius-md)] bg-transparent transition-all duration-200",
        "border border-transparent",
        "hover:bg-[rgba(0,0,0,0.06)] hover:border-[var(--border-default)]",
        className,
      )}
      style={{ color: "var(--text-muted)" }}
    >
      {children}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Topbar
// ---------------------------------------------------------------------------

export function Topbar({ onToggleSidebar, title, professional }: TopbarProps) {
  const navigate = useNavigate();
  const { resolvedTheme, setTheme } = useTheme();

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
        background: "var(--bg-surface)",
        backdropFilter: "blur(16px)",
        WebkitBackdropFilter: "blur(16px)",
        borderBottom: "1px solid var(--border-default)",
      }}
    >
      {/* ── Left — hamburger + breadcrumb ── */}
      <IconButton label="Alternar menu" onClick={onToggleSidebar}>
        <Menu size={16} />
      </IconButton>

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
        <IconButton label="Pesquisar">
          <Search size={15} />
        </IconButton>

        {/* Notifications with red dot */}
        <div className="relative">
          <IconButton label="Notificações">
            <Bell size={15} />
          </IconButton>
          {/* Red badge dot */}
          <span
            className="absolute top-[6px] right-[6px] w-[7px] h-[7px] rounded-full pointer-events-none"
            style={{
              background: "var(--danger, #f87171)",
              border: "1.5px solid var(--bg-page)",
            }}
            aria-hidden="true"
          />
        </div>

        {/* Theme toggle — Sun in dark mode, Moon in light mode */}
        <IconButton
          label={
            resolvedTheme === "dark"
              ? "Ativar modo claro"
              : "Ativar modo escuro"
          }
          onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
        >
          {resolvedTheme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
        </IconButton>

        {/* Nova Sessão — primary CTA */}
        <button
          type="button"
          onClick={() => navigate("/agenda")}
          className={cn(
            "flex items-center justify-center flex-shrink-0 rounded-full cursor-pointer",
            "transition-all duration-200 text-[12px] font-semibold px-[14px] py-[6px]",
            "hover:opacity-90 active:scale-[0.97]",
          )}
          style={{
            background: "var(--color-primary)",
            color: "white",
          }}
        >
          Nova Sessão
        </button>

        {/* User avatar */}
        {professional && (
          <Avatar
            initials={initials}
            size="sm"
            className="cursor-pointer hover:opacity-80 transition-opacity duration-200"
          />
        )}
      </div>
    </header>
  );
}
