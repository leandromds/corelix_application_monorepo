/**
 * Accessibility tests for ClientsPage.
 *
 * MSW intercepts GET /clients to return an empty array so the page
 * renders its idle (non-loading) state.
 *
 * Rules disabled:
 *   - color-contrast: CSS custom properties aren't computed in jsdom
 *   - region: components rendered in isolation have no landmark wrapper
 */

import { axe } from 'jest-axe'
import { http, HttpResponse } from 'msw'
import { waitFor } from '@testing-library/react'
import { server, BASE_URL } from '@/test/server'
import { renderWithProviders } from '@/test/utils'
import { ClientsPage } from './ClientsPage'

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
    http.get(BASE_URL + '/clients', () => HttpResponse.json([])),
  )
})

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ClientsPage a11y', () => {
  it('não tem violações axe críticas ou sérias', async () => {
    const { container } = renderWithProviders(<ClientsPage />)

    // Wait for the query to settle (skeleton → idle empty state)
    await waitFor(() => {
      expect(container.querySelector('.animate-pulse')).toBeNull()
    })

    const results = await axe(container, AXE_CONFIG)
    expect(results).toHaveNoViolations()
  })
})
