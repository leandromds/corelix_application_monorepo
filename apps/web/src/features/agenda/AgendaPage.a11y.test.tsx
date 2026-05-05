/**
 * Accessibility tests for AgendaPage.
 *
 * MSW intercepts:
 *   - GET /agenda/sessions  → empty array (no sessions to render)
 *   - GET /clients          → empty array (SessionForm preloads clients list)
 *
 * Rules disabled:
 *   - color-contrast: CSS custom properties aren't computed in jsdom
 *   - region: components rendered in isolation have no landmark wrapper
 */

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

import { axe } from 'jest-axe'
import { http, HttpResponse } from 'msw'
import { waitFor } from '@testing-library/react'
import { server, BASE_URL } from '@/test/server'
import { renderWithProviders } from '@/test/utils'
import { AgendaPage } from './AgendaPage'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const AXE_CONFIG = {
  rules: {
    'color-contrast': { enabled: false },
    region: { enabled: false },
  },
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  server.use(
    http.get(BASE_URL + '/agenda/sessions', () => HttpResponse.json([])),
    http.get(BASE_URL + '/clients', () => HttpResponse.json([])),
  )
})

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('AgendaPage a11y', () => {
  it('não tem violações axe críticas ou sérias', async () => {
    const { container } = renderWithProviders(<AgendaPage />)

    // Wait for the sessions query to resolve
    await waitFor(() => {
      expect(container.querySelector('.animate-pulse')).toBeNull()
    })

    const results = await axe(container, AXE_CONFIG)
    expect(results).toHaveNoViolations()
  })
})
