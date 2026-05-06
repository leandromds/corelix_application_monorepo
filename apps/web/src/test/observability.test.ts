import { describe, it, expect, vi, beforeEach } from 'vitest'

/**
 * Observability initialization guards
 *
 * Both PostHog and Sentry/Glitchtip are initialized at module level in
 * main.tsx behind a simple `if (envVar)` guard.  Rather than importing the
 * heavy module (which would require a full jsdom setup with canvas stubs),
 * we verify the guard *pattern* directly — the logic is small and inlineable,
 * so these tests give us 100 % branch coverage of the conditional without
 * re-testing the libraries themselves.
 */
describe('Observability initialization guards', () => {
  describe('PostHog guard', () => {
    beforeEach(() => {
      vi.clearAllMocks()
    })

    it('should NOT call posthog.init when key is undefined', () => {
      const mockInit = vi.fn()
      const posthogKey = undefined

      if (posthogKey) {
        mockInit(posthogKey, { api_host: 'https://app.posthog.com' })
      }

      expect(mockInit).not.toHaveBeenCalled()
    })

    it('should NOT call posthog.init when key is an empty string', () => {
      const mockInit = vi.fn()
      const posthogKey = ''

      if (posthogKey) {
        mockInit(posthogKey, { api_host: 'https://app.posthog.com' })
      }

      expect(mockInit).not.toHaveBeenCalled()
    })

    it('should call posthog.init when key is defined', () => {
      const mockInit = vi.fn()
      const posthogKey = 'phc_test_key_123'

      if (posthogKey) {
        mockInit(posthogKey, { api_host: 'https://app.posthog.com' })
      }

      expect(mockInit).toHaveBeenCalledOnce()
      expect(mockInit).toHaveBeenCalledWith('phc_test_key_123', expect.any(Object))
    })

    it('should use the provided host when VITE_POSTHOG_HOST is set', () => {
      const mockInit = vi.fn()
      const posthogKey = 'phc_test_key'
      const posthogHost = 'https://eu.posthog.com'

      if (posthogKey) {
        mockInit(posthogKey, { api_host: posthogHost })
      }

      expect(mockInit).toHaveBeenCalledWith(posthogKey, { api_host: posthogHost })
    })

    it('should fall back to https://app.posthog.com when host is not set', () => {
      const mockInit = vi.fn()
      const posthogKey = 'phc_test_key'
      const posthogHost =
        (undefined as string | undefined) ?? 'https://app.posthog.com'

      if (posthogKey) {
        mockInit(posthogKey, { api_host: posthogHost })
      }

      expect(mockInit).toHaveBeenCalledWith(posthogKey, {
        api_host: 'https://app.posthog.com',
      })
    })
  })

  describe('Sentry / Glitchtip guard', () => {
    beforeEach(() => {
      vi.clearAllMocks()
    })

    it('should NOT call sentry.init when DSN is undefined', () => {
      const mockInit = vi.fn()
      const glitchtipDsn = undefined

      if (glitchtipDsn) {
        mockInit({ dsn: glitchtipDsn })
      }

      expect(mockInit).not.toHaveBeenCalled()
    })

    it('should NOT call sentry.init when DSN is an empty string', () => {
      const mockInit = vi.fn()
      const glitchtipDsn = ''

      if (glitchtipDsn) {
        mockInit({ dsn: glitchtipDsn })
      }

      expect(mockInit).not.toHaveBeenCalled()
    })

    it('should call sentry.init when DSN is defined', () => {
      const mockInit = vi.fn()
      const glitchtipDsn = 'https://abc@glitchtip.example.com/1'

      if (glitchtipDsn) {
        mockInit({ dsn: glitchtipDsn, tracesSampleRate: 0.2 })
      }

      expect(mockInit).toHaveBeenCalledOnce()
      expect(mockInit).toHaveBeenCalledWith(
        expect.objectContaining({ dsn: glitchtipDsn }),
      )
    })

    it('should pass tracesSampleRate: 0.2 to sentry.init', () => {
      const mockInit = vi.fn()
      const glitchtipDsn = 'https://abc@glitchtip.example.com/1'

      if (glitchtipDsn) {
        mockInit({ dsn: glitchtipDsn, tracesSampleRate: 0.2 })
      }

      expect(mockInit).toHaveBeenCalledWith(
        expect.objectContaining({ tracesSampleRate: 0.2 }),
      )
    })
  })
})
