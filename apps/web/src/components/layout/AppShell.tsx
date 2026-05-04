/**
 * AppShell — root layout wrapper for authenticated routes.
 *
 * Composes:
 *  - <Sidebar>  — collapsible navigation (hidden on mobile)
 *  - <Topbar>   — sticky header with actions
 *  - <main>     — scrollable content area, renders nested routes via <Outlet>
 *
 * State:
 *  - `collapsed` — controls sidebar width; toggled by Topbar hamburger button
 *
 * Route → title mapping lives here so Topbar stays purely presentational.
 */

import { useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'

// ---------------------------------------------------------------------------
// Route → page title map
// ---------------------------------------------------------------------------

const ROUTE_TITLES: Record<string, string> = {
  '/dashboard': 'Início',
  '/clients':   'Clientes',
  '/agenda':    'Agenda',
  '/whatsapp':  'WhatsApp',
  '/reports':   'Relatórios',
  '/settings':  'Configurações',
}

// ---------------------------------------------------------------------------
// AppShell
// ---------------------------------------------------------------------------

export function AppShell() {
  const [collapsed, setCollapsed] = useState(false)
  const { professional } = useAuth()
  const location         = useLocation()

  const currentTitle = ROUTE_TITLES[location.pathname] ?? 'Corelix'

  function toggleCollapsed() {
    setCollapsed((prev) => !prev)
  }

  return (
    <div
      className="flex overflow-hidden h-screen"
      style={{ background: 'var(--bg-page)' }}
    >
      {/* ── Sidebar — hidden on mobile (< md), visible + collapsible on desktop ── */}
      <Sidebar
        collapsed={collapsed}
        professional={professional}
        className="hidden md:flex"
      />

      {/* ── Main column ── */}
      <div className="flex flex-col flex-1 overflow-hidden min-w-0">

        {/* Sticky topbar */}
        <Topbar
          onToggleSidebar={toggleCollapsed}
          title={currentTitle}
          professional={professional}
        />

        {/* Scrollable page content */}
        <main
          className="flex-1 overflow-y-auto p-[24px]"
          // scrollbar-thin via Tailwind utility (requires tailwind-scrollbar or
          // the native CSS property — index.css can set the scrollbar styles globally)
        >
          <Outlet />
        </main>
      </div>
    </div>
  )
}
