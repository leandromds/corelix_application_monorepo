import { useState, useEffect } from "react";
import { Plus, Search } from "lucide-react";

import { useClients } from "./hooks/useClients";
import { ClientList } from "./components/ClientList";
import { ClientForm } from "./components/ClientForm";
import type { Client } from "./types";

import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";

export function ClientsPage() {
  // -------------------------------------------------------------------------
  // Local state
  // -------------------------------------------------------------------------

  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [showInactive, setShowInactive] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [editingClient, setEditingClient] = useState<Client | null>(null);

  // Mount animation
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);

  // Debounce search input (300 ms)
  useEffect(() => {
    const id = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(id);
  }, [search]);

  // -------------------------------------------------------------------------
  // Data
  // -------------------------------------------------------------------------

  const { data: clients, isLoading } = useClients({
    search: debouncedSearch !== "" ? debouncedSearch : undefined,
    is_active: showInactive ? undefined : true,
  });

  const clientCount = clients?.length ?? 0;

  // -------------------------------------------------------------------------
  // Handlers
  // -------------------------------------------------------------------------

  function handleEdit(client: Client): void {
    setEditingClient(client);
    setFormOpen(true);
  }

  function handleFormOpenChange(open: boolean): void {
    setFormOpen(open);
    if (!open) {
      // Reset after the dialog close animation completes
      setTimeout(() => {
        setEditingClient(null);
      }, 200);
    }
  }

  function handleNewClient(): void {
    setEditingClient(null);
    setFormOpen(true);
  }

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <div
      className={mounted ? "animate-slide-up" : ""}
      style={{ padding: "24px", maxWidth: 1200, margin: "0 auto" }}
    >
      {/* ------------------------------------------------------------------ */}
      {/* Header row                                                           */}
      {/* ------------------------------------------------------------------ */}
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          gap: 16,
          marginBottom: 20,
          flexWrap: "wrap",
        }}
      >
        {/* Title + count */}
        <div style={{ flex: 1, minWidth: 200 }}>
          <h2
            style={{
              fontFamily: "var(--font-heading)",
              fontWeight: 700,
              fontSize: 24,
              color: "var(--text-primary)",
              margin: 0,
            }}
          >
            Clientes
          </h2>
          <p
            style={{
              fontSize: 14,
              color: "var(--text-muted)",
              margin: "4px 0 0",
            }}
          >
            {clientCount}{" "}
            {clientCount === 1 ? "cliente cadastrado" : "clientes cadastrados"}
          </p>
        </div>

        {/* Search + CTA */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            flexWrap: "wrap",
          }}
        >
          <div style={{ position: "relative" }}>
            <Search
              aria-hidden="true"
              style={{
                position: "absolute",
                left: 10,
                top: "50%",
                transform: "translateY(-50%)",
                width: 14,
                height: 14,
                color: "var(--text-muted)",
                pointerEvents: "none",
              }}
            />
            <input
              type="search"
              className="form-input"
              placeholder="Buscar cliente..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Buscar cliente"
              style={{ width: 200, paddingLeft: 32 }}
            />
          </div>

          <button
            type="button"
            className="btn-primary"
            onClick={handleNewClient}
            style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
          >
            <Plus aria-hidden="true" style={{ width: 14, height: 14 }} />
            Novo cliente
          </button>
        </div>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Filter bar                                                           */}
      {/* ------------------------------------------------------------------ */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginBottom: 16,
        }}
      >
        <Checkbox
          id="show-inactive"
          checked={showInactive}
          onCheckedChange={(checked) => {
            setShowInactive(checked === true);
          }}
        />
        <Label
          htmlFor="show-inactive"
          style={{
            cursor: "pointer",
            fontSize: 13,
            color: "var(--text-muted)",
          }}
        >
          Mostrar inativos
        </Label>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Content card                                                         */}
      {/* ------------------------------------------------------------------ */}
      <div
        className="glass-card bordered"
        style={{ padding: 0, overflow: "hidden" }}
      >
        <ClientList
          clients={clients ?? []}
          isLoading={isLoading}
          onEdit={handleEdit}
          onNewClient={handleNewClient}
        />
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Form modal (create + edit)                                           */}
      {/* ------------------------------------------------------------------ */}
      <ClientForm
        open={formOpen}
        onOpenChange={handleFormOpenChange}
        client={editingClient}
      />
    </div>
  );
}
