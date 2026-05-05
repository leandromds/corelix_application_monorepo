/**
 * KpiCard — a single KPI metric tile.
 *
 * Shows a large icon, a muted label, and a prominent value.
 * Renders a pulsing skeleton while data is loading.
 */

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------

function KpiCardSkeleton() {
  return (
    <div
      className="animate-pulse"
      style={{
        background:    'var(--bg-surface-card)',
        borderRadius:  'var(--radius-lg)',
        border:        '1px solid var(--border-default)',
        boxShadow:     'var(--shadow-card)',
        padding:       '20px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        {/* Icon placeholder */}
        <div
          style={{
            width: 40, height: 40, flexShrink: 0,
            background:   'var(--bg-surface)',
            borderRadius: 10,
          }}
        />
        {/* Text placeholders */}
        <div style={{ flex: 1 }}>
          <div style={{ width: '55%', height: 10, background: 'var(--bg-surface)', borderRadius: 6, marginBottom: 10 }} />
          <div style={{ width: '75%', height: 20, background: 'var(--bg-surface)', borderRadius: 6 }} />
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// KpiCard
// ---------------------------------------------------------------------------

interface KpiCardProps {
  /** Short uppercase label shown above the value */
  label: string
  /** Formatted value string (e.g. "12" or "R$ 1.800,00") */
  value: string
  /** Emoji icon displayed to the left */
  icon: string
  /** Show skeleton instead of content */
  isLoading?: boolean
  /** Optional CSS color for the value (defaults to --text-primary) */
  valueColor?: string
}

export function KpiCard({ label, value, icon, isLoading, valueColor }: KpiCardProps) {
  if (isLoading) return <KpiCardSkeleton />

  return (
    <div
      style={{
        background:   'var(--bg-surface-card)',
        borderRadius: 'var(--radius-lg)',
        border:       '1px solid var(--border-default)',
        boxShadow:    'var(--shadow-card)',
        padding:      '20px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        {/* Icon */}
        <div
          aria-hidden="true"
          style={{
            width:           40,
            height:          40,
            display:         'flex',
            alignItems:      'center',
            justifyContent:  'center',
            background:      'rgba(0,0,0,0.05)',
            borderRadius:    10,
            fontSize:        20,
            flexShrink:      0,
          }}
        >
          {icon}
        </div>

        {/* Label + value */}
        <div>
          <p
            style={{
              fontSize:       11,
              fontWeight:     700,
              textTransform:  'uppercase',
              letterSpacing:  '0.06em',
              color:          'var(--text-muted)',
              margin:         '0 0 4px',
            }}
          >
            {label}
          </p>
          <p
            style={{
              fontSize:    22,
              fontWeight:  700,
              color:       valueColor ?? 'var(--text-primary)',
              margin:      0,
              fontFamily:  'var(--font-heading)',
              lineHeight:  1.2,
            }}
          >
            {value}
          </p>
        </div>
      </div>
    </div>
  )
}
