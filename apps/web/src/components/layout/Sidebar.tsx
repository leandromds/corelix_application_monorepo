/**
 * Sidebar — collapsible navigation sidebar.
 *
 * Receives `collapsed` state from AppShell so the parent
 * fully controls the expand/collapse lifecycle.
 *
 * Design rules:
 *  - Width transitions from var(--sidebar-width) ↔ var(--sidebar-collapsed)
 *  - When collapsed: only icons visible, all text labels hidden
 *  - Active NavLink: left accent border + subtle bg tint
 *  - Hover: slightly lighter bg + primary text
 */

import { NavLink } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { Avatar, getInitials } from '@/components/shared/Avatar'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface NavItem {
  path: string
  /** Emoji icon — no external dependency needed */
  icon: string
  label: string
  badge?: number
}

export interface SidebarProps {
  collapsed: boolean
  professional: { full_name: string; specialty: string | null } | null
  /** Optional extra class — used by AppShell for responsive hiding */
  className?: string
}

// ---------------------------------------------------------------------------
// Navigation items
// ---------------------------------------------------------------------------

const NAV_ITEMS: NavItem[] = [
  { path: '/dashboard', icon: '🏠', label: 'Início'       },
  { path: '/agenda',    icon: '📅', label: 'Agenda'       },
  { path: '/clients',   icon: '👥', label: 'Clientes'     },
  { path: '/whatsapp',  icon: '💬', label: 'WhatsApp'     },
  { path: '/reports',   icon: '📊', label: 'Relatórios'   },
]

const ACCOUNT_ITEMS: NavItem[] = [
  { path: '/settings',  icon: '⚙️',  label: 'Configurações' },
]

// ---------------------------------------------------------------------------
// NavLinkItem — individual nav entry
// ---------------------------------------------------------------------------

interface NavLinkItemProps {
  item: NavItem
  collapsed: boolean
}

function NavLinkItem({ item, collapsed }: NavLinkItemProps) {
  return (
    <NavLink
      to={item.path}
      title={collapsed ? item.label : undefined}
      className={({ isActive }) =>
        cn(
          // Base layout
          'flex items-center no-underline mx-[8px]',
          'rounded-[var(--radius-md)] whitespace-nowrap',
          'transition-all duration-200',
          'py-[9px]',
          // Horizontal padding & icon alignment
          collapsed ? 'justify-center' : 'gap-[10px]',
          // Active / inactive states
          isActive
            ? 'font-bold text-[var(--text-primary)] bg-[rgba(0,0,0,0.06)]'
            : cn(
                'font-medium text-[var(--text-muted)]',
                'hover:text-[var(--text-primary)] hover:bg-[rgba(0,0,0,0.04)]',
              ),
        )
      }
      style={({ isActive }) => ({
        fontSize:        '13px',
        // Left accent border — always present to avoid layout shift
        borderLeft:      `3px solid ${isActive ? 'var(--color-primary)' : 'transparent'}`,
        paddingLeft:     collapsed ? '0px' : '11px',   // 14px − 3px border
        paddingRight:    collapsed ? '0px' : '14px',
      })}
    >
      {/* Icon */}
      <span
        className="flex items-center justify-center flex-shrink-0"
        style={{ fontSize: '14px', width: '18px', textAlign: 'center', lineHeight: 1 }}
      >
        {item.icon}
      </span>

      {/* Label — hidden when collapsed */}
      {!collapsed && <span className="flex-1 truncate">{item.label}</span>}

      {/* Optional badge count */}
      {!collapsed && item.badge !== undefined && item.badge > 0 && (
        <span
          className="ml-auto text-[10px] font-bold px-[7px] py-[1px] rounded-full"
          style={{
            background:  'var(--warning-bg,  rgba(251,191,36,0.15))',
            color:       'var(--warning,     #fbbf24)',
            border:      '1px solid var(--warning-border, rgba(251,191,36,0.30))',
          }}
        >
          {item.badge}
        </span>
      )}
    </NavLink>
  )
}

// ---------------------------------------------------------------------------
// Section label — hidden when sidebar is collapsed
// ---------------------------------------------------------------------------

interface SectionLabelProps {
  label: string
  collapsed: boolean
}

function SectionLabel({ label, collapsed }: SectionLabelProps) {
  if (collapsed) return null

  return (
    <div
      style={{
        fontSize:      '10px',
        fontWeight:    700,
        textTransform: 'uppercase',
        letterSpacing: '0.12em',
        color:         'var(--text-muted)',
        padding:       '18px 18px 6px',
        whiteSpace:    'nowrap',
        overflow:      'hidden',
      }}
    >
      {label}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Sidebar
// ---------------------------------------------------------------------------

export function Sidebar({ collapsed, professional, className }: SidebarProps) {
  const initials = professional ? getInitials(professional.full_name) : '?'

  return (
    <aside
      className={cn('flex flex-col overflow-hidden flex-shrink-0', className)}
      style={{
        width:             collapsed ? 'var(--sidebar-collapsed)' : 'var(--sidebar-width)',
        minWidth:          collapsed ? 'var(--sidebar-collapsed)' : 'var(--sidebar-width)',
        background:        'var(--bg-surface)',
        backdropFilter:    'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
        borderRight:       '1px solid rgba(255,255,255,0.3)',
        boxShadow:         'var(--shadow-glass)',
        transition:        'width 0.25s ease, min-width 0.25s ease',
        zIndex:            40,
      }}
    >
      {/* ── Logo ── */}
      <div
        className={cn(
          'flex items-center flex-shrink-0 overflow-hidden',
          collapsed ? 'justify-center px-0' : 'gap-[10px] px-[18px]',
        )}
        style={{
          height:       'var(--topbar-height)',
          borderBottom: '1px solid var(--border-default)',
        }}
      >
        {/* Logo icon */}
        <div
          className="flex items-center justify-center flex-shrink-0 rounded-[8px]"
          style={{
            width:      30,
            height:     30,
            background: 'rgba(0,0,0,0.12)',
            border:     '1px solid var(--color-primary)',
          }}
        >
          <span
            style={{
              fontSize:   '13px',
              fontWeight: 800,
              color:      'var(--color-primary)',
              fontFamily: 'var(--font-heading)',
            }}
          >
            C
          </span>
        </div>

        {/* Brand name — hidden when collapsed */}
        {!collapsed && (
          <span
            style={{
              fontFamily:  'var(--font-heading)',
              fontSize:    '15px',
              fontWeight:  800,
              color:       'var(--text-primary)',
              whiteSpace:  'nowrap',
            }}
          >
            Corelix
          </span>
        )}
      </div>

      {/* ── Navigation ── */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden py-[8px]">
        {/* Main menu section */}
        <SectionLabel label="Menu" collapsed={collapsed} />
        <nav aria-label="Navegação principal">
          {NAV_ITEMS.map((item) => (
            <NavLinkItem key={item.path} item={item} collapsed={collapsed} />
          ))}
        </nav>

        {/* Account section */}
        <SectionLabel label="Conta" collapsed={collapsed} />
        <nav aria-label="Conta">
          {ACCOUNT_ITEMS.map((item) => (
            <NavLinkItem key={item.path} item={item} collapsed={collapsed} />
          ))}
        </nav>
      </div>

      {/* ── Footer — user card ── */}
      <div
        className="flex-shrink-0 p-[12px]"
        style={{ borderTop: '1px solid var(--border-default)' }}
      >
        <div
          className={cn(
            'flex items-center rounded-[var(--radius-md)] cursor-pointer',
            'transition-colors duration-200',
            'hover:bg-[rgba(0,0,0,0.04)]',
            collapsed ? 'justify-center p-[9px]' : 'gap-[10px] px-[10px] py-[9px]',
          )}
        >
          <Avatar initials={initials} size="md" />

          {/* Name + specialty — hidden when collapsed */}
          {!collapsed && professional && (
            <div className="flex flex-col overflow-hidden min-w-0">
              <span
                className="truncate"
                style={{
                  fontSize:   '13px',
                  fontWeight: 600,
                  color:      'var(--text-primary)',
                }}
              >
                {professional.full_name}
              </span>
              {professional.specialty && (
                <span
                  className="truncate"
                  style={{ fontSize: '11px', color: 'var(--text-muted)' }}
                >
                  {professional.specialty}
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    </aside>
  )
}
