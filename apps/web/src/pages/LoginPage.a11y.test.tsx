/**
 * Accessibility tests for LoginPage and RegisterPage.
 *
 * Uses jest-axe to run an automated a11y audit on each page.
 * Rules disabled:
 *   - color-contrast: CSS custom properties aren't computed in jsdom
 *   - region: components rendered in isolation have no landmark wrapper
 */

vi.mock('@/hooks/useAuth')

import { axe } from 'jest-axe'
import { useAuth } from '@/hooks/useAuth'
import { renderWithProviders } from '@/test/utils'
import { LoginPage } from './LoginPage'
import { RegisterPage } from './RegisterPage'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const AXE_CONFIG = {
  rules: {
    'color-contrast': { enabled: false },
    region: { enabled: false },
  },
}

const MOCK_AUTH = {
  professional: null,
  isLoading: false,
  isAuthenticated: false,
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
  refreshProfile: vi.fn(),
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.mocked(useAuth).mockReturnValue(MOCK_AUTH)
})

afterEach(() => {
  vi.clearAllMocks()
})

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('LoginPage a11y', () => {
  it('não tem violações axe críticas ou sérias', async () => {
    const { container } = renderWithProviders(<LoginPage />)
    const results = await axe(container, AXE_CONFIG)
    expect(results).toHaveNoViolations()
  })
})

describe('RegisterPage a11y', () => {
  it('não tem violações axe críticas ou sérias', async () => {
    const { container } = renderWithProviders(<RegisterPage />)
    const results = await axe(container, AXE_CONFIG)
    expect(results).toHaveNoViolations()
  })
})
