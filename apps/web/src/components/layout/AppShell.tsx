/**
 * AppShell — root layout wrapper for authenticated routes.
 *
 * Composes:
 *  - bg-blobs: fixed decorative blobs behind everything (z-index 0)
 *  - <Sidebar>: collapsible navigation, hidden on mobile (< 768px)
 *  - <Topbar>:  sticky header with actions
 *  - <main>:    scrollable content area (.screen-area), renders via <Outlet>
 *
 * Layout classes come from index.css:
 *  .app-shell → flex, 100vh, overflow hidden
 *  .main-content → flex-col, flex-1, overflow hidden
 *  .screen-area → flex-1, overflow-y-auto, padding 24px (16px mobile)
 *
 * State:
 *  - `collapsed` — controls sidebar width; toggled by Topbar hamburger
 */

import { useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

// ---------------------------------------------------------------------------
// Route → page title map
// ---------------------------------------------------------------------------

const ROUTE_TITLES: Record<string, string> = {
  "/dashboard": "Início",
  "/clients": "Clientes",
  "/agenda": "Agenda",
  "/whatsapp": "WhatsApp",
  "/reports": "Relatórios",
  "/settings": "Configurações",
};

// ---------------------------------------------------------------------------
// AppShell
// ---------------------------------------------------------------------------

export function AppShell() {
  const [collapsed, setCollapsed] = useState(false);
  const { professional } = useAuth();
  const location = useLocation();

  const currentTitle = ROUTE_TITLES[location.pathname] ?? "Corelix";

  function toggleCollapsed() {
    setCollapsed((prev) => !prev);
  }

  return (
    <>
      {/* ── Decorative background blobs (fixed, behind everything) ── */}
      <div className="bg-blobs">
        <div className="blob blob-1" />
        <div className="blob blob-2" />
      </div>

      {/* ── App shell (sits above blobs) ── */}
      <div className="app-shell">
        {/* Sidebar — hidden on mobile via .sidebar-desktop class */}
        <Sidebar
          collapsed={collapsed}
          professional={professional}
          className="sidebar-desktop"
        />

        {/* Main column: topbar + scrollable content */}
        <div className="main-content">
          <Topbar
            onToggleSidebar={toggleCollapsed}
            title={currentTitle}
            professional={professional}
          />

          <main className="screen-area">
            <Outlet />
          </main>
        </div>
      </div>
    </>
  );
}
