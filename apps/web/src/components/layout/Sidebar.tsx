/**
 * Sidebar — collapsible navigation sidebar.
 *
 * Design (dark glass morphism):
 *  - .sidebar class handles background, width, border, transition
 *  - .sidebar.collapsed → narrowed to icon-only mode (64px)
 *  - Active NavLink: .nav-item.active (bg-selected + border-purple + glow)
 *  - Inactive NavLink: .nav-item (text-muted, hover → bg-elevated)
 *  - Section labels: .sidebar-section-label (10px uppercase, text-subtle)
 *  - Footer: .sidebar-footer > .sidebar-user > .avatar.avatar-md
 *  - Icons: Font Awesome 6 via <i className="nav-icon fas fa-...">
 */

import { NavLink, useNavigate } from "react-router-dom";
import { cn } from "@/lib/utils";
import { getInitials } from "@/components/shared/Avatar";
import { useAuth } from "@/hooks/useAuth";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface NavItem {
  path: string;
  icon: string; // Font Awesome class string, e.g. "fas fa-home"
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
  { path: "/dashboard", icon: "fas fa-home", label: "Início" },
  { path: "/agenda", icon: "fas fa-calendar-alt", label: "Agenda" },
  { path: "/clients", icon: "fas fa-users", label: "Clientes" },
  { path: "/whatsapp", icon: "fab fa-whatsapp", label: "WhatsApp" },
  { path: "/reports", icon: "fas fa-chart-line", label: "Relatórios" },
];

const ACCOUNT_ITEMS: NavItem[] = [
  { path: "/settings", icon: "fas fa-cog", label: "Configurações" },
];

// ---------------------------------------------------------------------------
// NavLinkItem
// ---------------------------------------------------------------------------

interface NavLinkItemProps {
  item: NavItem;
  collapsed: boolean;
}

function NavLinkItem({ item, collapsed }: NavLinkItemProps) {
  return (
    <NavLink
      to={item.path}
      title={collapsed ? item.label : undefined}
      className={({ isActive }) => cn("nav-item", isActive && "active")}
      style={
        collapsed ? { justifyContent: "center", padding: "9px 0" } : undefined
      }
    >
      <i className={cn("nav-icon", item.icon)} />

      {!collapsed && <span className="nav-item-label">{item.label}</span>}

      {!collapsed && item.badge !== undefined && item.badge > 0 && (
        <span className="sidebar-badge">{item.badge}</span>
      )}
    </NavLink>
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
    <aside className={cn("sidebar", collapsed && "collapsed", className)}>
      {/* ── Logo ── */}
      <div className="sidebar-logo">
        <div className="logo-icon">
          <i
            className="fas fa-stethoscope"
            style={{ fontSize: 13, color: "hsl(270,95%,75%)" }}
          />
        </div>
        {!collapsed && <span className="logo-text">Corelix</span>}
      </div>

      {/* ── Navigation ── */}
      <div style={{ flex: 1, overflowY: "auto", overflowX: "hidden" }}>
        {!collapsed && <div className="sidebar-section-label">Menu</div>}
        <nav aria-label="Navegação principal">
          {NAV_ITEMS.map((item) => (
            <NavLinkItem key={item.path} item={item} collapsed={collapsed} />
          ))}
        </nav>

        {!collapsed && <div className="sidebar-section-label">Conta</div>}
        <nav aria-label="Conta">
          {ACCOUNT_ITEMS.map((item) => (
            <NavLinkItem key={item.path} item={item} collapsed={collapsed} />
          ))}
        </nav>
      </div>

      {/* ── Footer — user card + logout ── */}
      <div className="sidebar-footer">
        <div className="sidebar-user">
          <div className="avatar avatar-md">{initials}</div>

          {!collapsed && professional && (
            <>
              <div className="sidebar-user-info" style={{ overflow: "hidden" }}>
                <div
                  style={{
                    fontSize: 12,
                    fontWeight: 700,
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                >
                  {professional.full_name}
                </div>
                {professional.specialty && (
                  <div style={{ fontSize: 10, color: "var(--text-muted)" }}>
                    {professional.specialty}
                  </div>
                )}
              </div>

              <button
                type="button"
                onClick={() => {
                  void handleLogout();
                }}
                aria-label="Sair"
                className="icon-btn"
                title="Sair"
                style={{ marginLeft: "auto" }}
              >
                <i
                  className="fas fa-arrow-right-from-bracket"
                  style={{ fontSize: 11 }}
                />
              </button>
            </>
          )}
        </div>
      </div>
    </aside>
  );
}
