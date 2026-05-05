/**
 * App — root component.
 *
 * Route structure:
 * - Public routes (/login, /register) — redirect to /dashboard if authenticated
 * - Protected routes — wrapped in AppShell (sidebar + topbar + Outlet)
 *   - /dashboard  → DashboardPage
 *   - /clients    → ClientsPage
 *   - /agenda     → AgendaPage
 */

import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "@/contexts/AuthContext";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { PublicRoute } from "@/components/PublicRoute";
import { AppShell } from "@/components/layout/AppShell";
import { LoginPage } from "@/pages/LoginPage";
import { RegisterPage } from "@/pages/RegisterPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { ClientsPage } from "@/features/clients/ClientsPage";
import { AgendaPage } from "@/features/agenda/AgendaPage";
import { ReportsPage } from "@/features/reports/ReportsPage";
import { SettingsPage } from "@/features/settings/SettingsPage";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* ─── Public routes ─────────────────────────────────────────── */}
          <Route
            path="/login"
            element={
              <PublicRoute>
                <LoginPage />
              </PublicRoute>
            }
          />
          <Route
            path="/register"
            element={
              <PublicRoute>
                <RegisterPage />
              </PublicRoute>
            }
          />

          {/* ─── Protected routes — AppShell layout ────────────────────── */}
          {/*
            AppShell renders Sidebar + Topbar + <Outlet />.
            Each child route renders into that Outlet.
          */}
          <Route
            element={
              <ProtectedRoute>
                <AppShell />
              </ProtectedRoute>
            }
          >
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/clients" element={<ClientsPage />} />
            <Route path="/agenda" element={<AgendaPage />} />
            <Route path="/reports" element={<ReportsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            {/* TODO: /whatsapp */}
          </Route>

          {/* ─── Default + 404 ─────────────────────────────────────────── */}
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
