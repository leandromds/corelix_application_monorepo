/**
 * PeriodFilter — date range selector with preset shortcuts and status
 * checkboxes.
 *
 * Fully controlled: all state lives in the parent (ReportsPage).
 * Intentionally avoids React Hook Form — these are filter controls for a
 * GET request, not a mutation form. Simple onChange props are cleaner here.
 */

import { Button }   from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Label }    from '@/components/ui/label'

import { STATUS_OPTIONS } from '../types'
import type { SessionStatus } from '../types'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface PeriodFilterProps {
  startDate: string
  endDate: string
  statusFilter: string[]
  onStartDateChange: (date: string) => void
  onEndDateChange: (date: string) => void
  onStatusFilterChange: (statuses: string[]) => void
  /** days=7|30|90 → called when user clicks a preset shortcut */
  onPreset: (days: number) => void
  onGenerateReport: () => void
  isGenerating?: boolean
}

// ---------------------------------------------------------------------------
// PeriodFilter
// ---------------------------------------------------------------------------

export function PeriodFilter({
  startDate,
  endDate,
  statusFilter,
  onStartDateChange,
  onEndDateChange,
  onStatusFilterChange,
  onPreset,
  onGenerateReport,
  isGenerating,
}: PeriodFilterProps) {

  function toggleStatus(value: SessionStatus): void {
    if (statusFilter.includes(value)) {
      onStatusFilterChange(statusFilter.filter((s) => s !== value))
    } else {
      onStatusFilterChange([...statusFilter, value])
    }
  }

  return (
    <div
      style={{
        background:    'var(--bg-surface-card)',
        borderRadius:  'var(--radius-lg)',
        border:        '1px solid var(--border-default)',
        boxShadow:     'var(--shadow-card)',
        padding:       '20px',
        marginBottom:  24,
      }}
    >
      {/* ── Preset shortcuts ── */}
      <div
        style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}
      >
        <span
          style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-muted)' }}
        >
          Atalhos:
        </span>
        {[
          { label: 'Últimos 7 dias',  days: 7  },
          { label: 'Últimos 30 dias', days: 30 },
          { label: 'Últimos 90 dias', days: 90 },
        ].map(({ label, days }) => (
          <Button
            key={days}
            variant="outline"
            size="sm"
            type="button"
            onClick={() => onPreset(days)}
          >
            {label}
          </Button>
        ))}
      </div>

      {/* ── Date range inputs + generate CTA ── */}
      <div
        style={{
          display:     'flex',
          gap:         16,
          marginBottom: 16,
          flexWrap:    'wrap',
          alignItems:  'flex-end',
        }}
      >
        {/* Start date */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <Label
            htmlFor="start-date"
            style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)' }}
          >
            Data de início
          </Label>
          <input
            id="start-date"
            type="date"
            value={startDate}
            onChange={(e) => onStartDateChange(e.target.value)}
            max={endDate}
            aria-label="Data de início"
            style={{
              padding:      '8px 12px',
              borderRadius: 'var(--radius-md)',
              border:       '1px solid var(--border-default)',
              background:   'var(--bg-surface)',
              color:        'var(--text-primary)',
              fontSize:     14,
              cursor:       'pointer',
            }}
          />
        </div>

        {/* End date */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <Label
            htmlFor="end-date"
            style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)' }}
          >
            Data de fim
          </Label>
          <input
            id="end-date"
            type="date"
            value={endDate}
            onChange={(e) => onEndDateChange(e.target.value)}
            min={startDate}
            aria-label="Data de fim"
            style={{
              padding:      '8px 12px',
              borderRadius: 'var(--radius-md)',
              border:       '1px solid var(--border-default)',
              background:   'var(--bg-surface)',
              color:        'var(--text-primary)',
              fontSize:     14,
              cursor:       'pointer',
            }}
          />
        </div>

        {/* Generate button */}
        <Button
          type="button"
          onClick={onGenerateReport}
          disabled={isGenerating}
          style={{ alignSelf: 'flex-end' }}
        >
          {isGenerating ? 'Gerando…' : 'Gerar Relatório'}
        </Button>
      </div>

      {/* ── Status checkboxes ── */}
      <div
        style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'center' }}
      >
        <span
          style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-muted)' }}
        >
          Status:
        </span>
        {STATUS_OPTIONS.map(({ value, label }) => (
          <div key={value} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Checkbox
              id={`status-${value}`}
              checked={statusFilter.includes(value)}
              onCheckedChange={() => toggleStatus(value)}
              aria-label={label}
            />
            <Label
              htmlFor={`status-${value}`}
              style={{ cursor: 'pointer', fontSize: 13, color: 'var(--text-primary)' }}
            >
              {label}
            </Label>
          </div>
        ))}
      </div>
    </div>
  )
}
