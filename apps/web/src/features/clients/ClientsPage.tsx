import { useState, useEffect } from 'react'
import { UserPlus } from 'lucide-react'

import { useClients } from './hooks/useClients'
import { ClientList } from './components/ClientList'
import { ClientForm } from './components/ClientForm'
import type { Client } from './types'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'

export function ClientsPage() {
  // -------------------------------------------------------------------------
  // Local state
  // -------------------------------------------------------------------------

  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [showInactive, setShowInactive] = useState(false)
  const [formOpen, setFormOpen] = useState(false)
  const [editingClient, setEditingClient] = useState<Client | null>(null)

  // Mount animation: fade-in + slide-up
  const [mounted, setMounted] = useState(false)
  useEffect(() => {
    setMounted(true)
  }, [])

  // Debounce search input (300 ms)
  useEffect(() => {
    const id = setTimeout(() => setDebouncedSearch(search), 300)
    return () => clearTimeout(id)
  }, [search])

  // -------------------------------------------------------------------------
  // Data
  // -------------------------------------------------------------------------

  const { data: clients, isLoading } = useClients({
    search: debouncedSearch !== '' ? debouncedSearch : undefined,
    is_active: showInactive ? undefined : true,
  })

  const clientCount = clients?.length ?? 0

  // -------------------------------------------------------------------------
  // Handlers
  // -------------------------------------------------------------------------

  function handleEdit(client: Client): void {
    setEditingClient(client)
    setFormOpen(true)
  }

  function handleFormOpenChange(open: boolean): void {
    setFormOpen(open)
    if (!open) {
      // Reset after the dialog close animation completes
      setTimeout(() => {
        setEditingClient(null)
      }, 200)
    }
  }

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <div
      style={{
        padding: '24px',
        maxWidth: 1200,
        margin: '0 auto',
        opacity: mounted ? 1 : 0,
        transform: mounted ? 'translateY(0)' : 'translateY(10px)',
        transition: 'opacity 0.25s ease, transform 0.25s ease',
      }}
    >
      {/* ------------------------------------------------------------------ */}
      {/* Header row                                                           */}
      {/* ------------------------------------------------------------------ */}
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: 16,
          marginBottom: 16,
          flexWrap: 'wrap',
        }}
      >
        {/* Title + count */}
        <div style={{ flex: 1, minWidth: 200 }}>
          <h2
            style={{
              fontFamily: 'var(--font-heading)',
              fontWeight: 700,
              fontSize: 24,
              color: 'var(--text-primary)',
              margin: 0,
            }}
          >
            Clientes
          </h2>
          <p style={{ fontSize: 14, color: 'var(--text-muted)', margin: '4px 0 0' }}>
            {clientCount} {clientCount === 1 ? 'cliente cadastrado' : 'clientes cadastrados'}
          </p>
        </div>

        {/* Search + CTA */}
        <div
          style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}
        >
          <Input
            type="search"
            placeholder="🔍 Buscar cliente..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ width: 240 }}
            aria-label="Buscar cliente"
          />
          <Button
            onClick={() => {
              setEditingClient(null)
              setFormOpen(true)
            }}
          >
            <UserPlus
              aria-hidden="true"
              style={{ width: 16, height: 16, marginRight: 8 }}
            />
            Novo Cliente
          </Button>
        </div>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Filter bar                                                           */}
      {/* ------------------------------------------------------------------ */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          marginBottom: 16,
        }}
      >
        <Checkbox
          id="show-inactive"
          checked={showInactive}
          onCheckedChange={(checked) => {
            setShowInactive(checked === true)
          }}
        />
        <Label
          htmlFor="show-inactive"
          style={{ cursor: 'pointer', fontSize: 14, color: 'var(--text-primary)' }}
        >
          Mostrar inativos
        </Label>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Content card                                                         */}
      {/* ------------------------------------------------------------------ */}
      <div
        style={{
          backgroundColor: 'var(--bg-surface-card)',
          borderRadius: 'var(--radius-lg)',
          border: '1px solid var(--border-default)',
          boxShadow: 'var(--shadow-card)',
          overflow: 'hidden',
        }}
      >
        <ClientList
          clients={clients ?? []}
          isLoading={isLoading}
          onEdit={handleEdit}
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
  )
}
