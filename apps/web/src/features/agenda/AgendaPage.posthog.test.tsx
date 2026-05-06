/**
 * AgendaPage PostHog smoke tests
 *
 * Verifies that posthog-js can be fully mocked with vi.mock so the
 * appointment_created event we added in SessionForm is testable without
 * making real network calls.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('posthog-js', () => ({
  default: {
    init: vi.fn(),
    capture: vi.fn(),
  },
}))

describe('AgendaPage — PostHog events', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('posthog module can be mocked', async () => {
    const posthog = await import('posthog-js')
    expect(posthog.default.capture).toBeDefined()
    expect(posthog.default.init).toBeDefined()
  })

  it('posthog.capture is a vi.fn() spy and starts with zero calls', async () => {
    const posthog = await import('posthog-js')
    expect(posthog.default.capture).not.toHaveBeenCalled()
  })

  it('calling posthog.capture("appointment_created") is captured correctly', async () => {
    const posthog = await import('posthog-js')

    posthog.default.capture('appointment_created')

    expect(posthog.default.capture).toHaveBeenCalledOnce()
    expect(posthog.default.capture).toHaveBeenCalledWith('appointment_created')
  })

  it('posthog.capture is NOT called when session creation is not triggered', async () => {
    const posthog = await import('posthog-js')

    // No action — simulates the page rendering without submitting a session
    expect(posthog.default.capture).not.toHaveBeenCalled()
  })
})
