/**
 * Accessibility tests for WhatsAppPage.
 *
 * MSW intercepts GET /whatsapp/conversations to return an empty array so
 * the page renders its idle (no-conversations) state.
 *
 * Rules disabled:
 *   - color-contrast: CSS custom properties aren't computed in jsdom
 *   - region: components rendered in isolation have no landmark wrapper
 */

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

import { axe } from 'jest-axe'
import { http, HttpResponse } from 'msw'
import { screen } from '@testing-library/react'
import { server, BASE_URL } from '@/test/server'
import { renderWithProviders } from '@/test/utils'
import { WhatsAppPage } from './WhatsAppPage'

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
    http.get(BASE_URL + '/whatsapp/conversations', () => HttpResponse.json([])),
  )
})

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('WhatsAppPage a11y', () => {
  it('não tem violações axe críticas ou sérias', async () => {
    const { container } = renderWithProviders(<WhatsAppPage />)

    // Wait for the conversations query to settle (empty state renders)
    await screen.findByText(/nenhuma conversa/i)

    const results = await axe(container, AXE_CONFIG)
    expect(results).toHaveNoViolations()
  })
})
