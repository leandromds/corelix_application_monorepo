/**
 * Sidebar — collapsible navigation sidebar.
 *
 * Design (dark glass morphism):
 *  - Background: rgba(15,15,25,0.80) + backdrop-filter blur(20px)
 *  - Width transitions between var(--sidebar-width) ↔ var(--sidebar-collapsed)
 *  - Active NavLink: bg-selected + border-purple + purple glow
 *  - Inactive NavLink: text-muted, hover → bg-elevated + text-primary
 *  - Section labels: 10px uppercase, text-subtle
 *  - Footer avatar: purple tinted circle with initials + logout icon
 */

import { NavLink, useNavigate } from "react-router-dom";
import {
  BarChart2,
  CalendarDays,
  Home,
  LogOut,
  MessageCircle,
  Settings,
  Stethoscope,
  Users,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Avatar, getInitials } from "@/components/shared/Avatar";
import { useAuth } from "@/hooks/useAuth";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface NavItem {
  path: string;
  icon: React.ElementType;
  label: string;
  badge?: number;
}

export interface SidebarProps {
  collapsed: boolean;
  professional: { full_name: string; specialty: string | null } | null;
  /** Optional extra class — used by AppShell for responsive hiding */
  className?: string;
}

// ---------------------------------------------------------------------------
// Navigation items
// ---------------------------------------------------------------------------

const NAV_ITEMS: NavItem[] = [
  { path: "/dashboard", icon: Home, label: "Início" },
  { path: "/agenda", icon: CalendarDays, label: "Agenda" },
  { path: "/clients", icon: Users, label: "Clientes" },
  { path: "/whatsapp", icon: MessageCircle, label: "WhatsApp" },
  { path: "/reports", icon: BarChart2, label: "Relatórios" },
];

const ACCOUNT_ITEMS: NavItem[] = [
  { path: "/settings", icon: Settings, label: "Configurações" },
];

// ---------------------------------------------------------------------------
// NavLinkItem
// ---------------------------------------------------------------------------

interface NavLinkItemProps {
  item: NavItem;
  collapsed: boolean;
}

function NavLinkItem({ item, collapsed }: NavLinkItemProps) {
  const Icon = item.icon;

  return (
    <NavLink
      to={item.path}
      title={collapsed ? item.label : undefined}
      className={({ isActive }) =>
        cn(
          "flex items-center no-underline whitespace-nowrap",
          "transition-all duration-200",
          "py-[9px] rounded-[var(--radius-md)]",
          collapsed
            ? "mx-[8px] justify-center px-0"
            : "mx-[8px] gap-[10px] px-[14px]",
          isActive
            ? "font-bold text-[var(--text-primary)]"
            : "font-medium text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[rgba(255,255,255,0.08)]",
        )
      }
      style={({ isActive }) =>
        isActive
          ? {
              fontSize: "13px",
              background: "var(--bg-selected)",
              border: "1px solid var(--border-purple)",
              boxShadow: "0 0 12px rgba(139,92,246,0.2)",
            }
          : {
              fontSize: "13px",
              background: "transparent",
              border: "1px solid transparent",
            }
      }
    >
      {/* Icon */}
      <span
        className="flex items-center justify-center flex-shrink-0"
        style={{ width: "18px", textAlign: "center", lineHeight: 1 }}
      >
        <Icon size={15} />
      </span>

      {/* Label — hidden when collapsed */}
      {!collapsed && (
        <span className="flex-1 truncate sidebar-label">{item.label}</span>
      )}

      {/* Optional badge count */}
      {!collapsed && item.badge !== undefined && item.badge > 0 && (
        <span className="badge badge-pending ml-auto">{item.badge}</span>
      )}
    </NavLink>
  );
}

// ---------------------------------------------------------------------------
// Section label
// ---------------------------------------------------------------------------

interface SectionLabelProps {
  label: string;
  collapsed: boolean;
}

function SectionLabel({ label, collapsed }: SectionLabelProps) {
  if (collapsed) return null;

  return (
    <div
      className="sidebar-label"
      style={{
        fontSize: "10px",
        fontWeight: 700,
        textTransform: "uppercase",
        letterSpacing: "0.12em",
        color: "var(--text-subtle)",
        padding: "18px 18px 6px",
        whiteSpace: "nowrap",
        overflow: "hidden",
      }}
    >
      {label}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sidebar
// ---------------------------------------------------------------------------

export function Sidebar({ collapsed, professional, className }: SidebarProps) {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const initials = professional ? getInitials(professional.full_name) : "?";

  async function handleLogout() {
    await logout();
    navigate("/login");
  }

  return (
    <aside
      className={cn("flex flex-col overflow-hidden flex-shrink-0", className)}
      style={{
        width: collapsed ? "var(--sidebar-collapsed)" : "var(--sidebar-width)",
        minWidth: collapsed
          ? "var(--sidebar-collapsed)"
          : "var(--sidebar-width)",
        background: "rgba(15, 15, 25, 0.80)",
        backdropFilter: "blur(20px)",
        WebkitBackdropFilter: "blur(20px)",
        borderRight: "1px solid var(--border-default)",
        transition: "width 0.25s ease, min-width 0.25s ease",
        zIndex: 40,
      }}
    >
      {/* ── Logo ── */}
      <div
        className={cn(
          "flex items-center flex-shrink-0 overflow-hidden",
          collapsed ? "justify-center px-0" : "gap-[10px] px-[18px]",
        )}
        style={{
          height: "var(--topbar-height)",
          borderBottom: "1px solid var(--border-default)",
        }}
      >
        {/* Purple stethoscope icon box */}
        <div
          className="flex items-center justify-center flex-shrink-0 rounded-[8px]"
          style={{
            width: 30,
            height: 30,
            background: "rgba(139, 92, 246, 0.20)",
            border: "1px solid rgba(139, 92, 246, 0.45)",
          }}
        >
          <Stethoscope size={15} style={{ color: "hsl(260,95%,75%)" }} />
        </div>

        {/* Brand name — hidden when collapsed */}
        {!collapsed && (
          <span
            className="sidebar-label"
            style={{
              fontFamily: "var(--font-heading)",
              fontSize: "15px",
              fontWeight: 800,
              color: "var(--text-primary)",
              whiteSpace: "nowrap",
            }}
          >
            Corelix
          </span>
        )}
      </div>

      {/* ── Navigation ── */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden py-[8px]">
        <SectionLabel label="Menu" collapsed={collapsed} />
        <nav aria-label="Navegação principal">
          {NAV_ITEMS.map((item) => (
            <NavLinkItem key={item.path} item={item} collapsed={collapsed} />
          ))}
        </nav>

        <SectionLabel label="Conta" collapsed={collapsed} />
        <nav aria-label="Conta">
          {ACCOUNT_ITEMS.map((item) => (
            <NavLinkItem key={item.path} item={item} collapsed={collapsed} />
          ))}
        </nav>
      </div>

      {/* ── Footer — user card + logout ── */}
      <div
        className="flex-shrink-0 p-[12px]"
        style={{ borderTop: "1px solid var(--border-default)" }}
      >
        <div
          className={cn(
            "flex items-center rounded-[var(--radius-md)]",
            collapsed
              ? "justify-center p-[9px]"
              : "gap-[10px] px-[10px] py-[9px]",
          )}
        >
          {/* Purple-tinted avatar */}
          <Avatar initials={initials} size="md" />

          {/* Name + specialty + logout — hidden when collapsed */}
          {!collapsed && professional && (
            <>
              <div className="flex flex-col overflow-hidden min-w-0 flex-1">
                <span
                  className="truncate"
                  style={{
                    fontSize: "13px",
                    fontWeight: 600,
                    color: "var(--text-primary)",
                  }}
                >
                  {professional.full_name}
                </span>
                {professional.specialty && (
                  <span
                    className="truncate"
                    style={{ fontSize: "11px", color: "var(--text-muted)" }}
                  >
                    {professional.specialty}
                  </span>
                )}
              </div>

              {/* Logout icon button */}
              <button
                type="button"
                onClick={() => {
                  void handleLogout();
                }}
                aria-label="Sair"
                className="icon-btn flex-shrink-0"
                title="Sair"
              >
                <LogOut size={14} />
              </button>
            </>
          )}
        </div>
      </div>
    </aside>
  );
}
