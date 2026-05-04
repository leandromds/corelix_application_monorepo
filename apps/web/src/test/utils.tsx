/**
 * Shared test utilities for Vitest + @testing-library/react.
 *
 * Provides:
 * - createTestQueryClient()  — a QueryClient with retries disabled (no flaky waits)
 * - renderWithProviders()    — renders inside QueryClientProvider + MemoryRouter
 * - makeWrapper()            — hook-only wrapper factory (for renderHook)
 */

import type { ReactNode } from 'react'
import { render, type RenderOptions } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'

// ---------------------------------------------------------------------------
// QueryClient factory
// ---------------------------------------------------------------------------

export function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // Disable retries so failed requests surface immediately as errors
        retry: false,
        // Disable garbage collection delay — keeps results in cache during tests
        gcTime: Infinity,
        staleTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  })
}

// ---------------------------------------------------------------------------
// Render with all providers
// ---------------------------------------------------------------------------

interface RenderWithProvidersOptions extends Omit<RenderOptions, 'wrapper'> {
  /** Provide a pre-configured QueryClient (useful for pre-loading cache). */
  queryClient?: QueryClient
  /** Initial router entry (default: '/'). */
  initialEntries?: string[]
}

export function renderWithProviders(
  ui: React.ReactElement,
  options: RenderWithProvidersOptions = {},
) {
  const {
    queryClient = createTestQueryClient(),
    initialEntries = ['/'],
    ...renderOptions
  } = options

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={initialEntries}>{children}</MemoryRouter>
      </QueryClientProvider>
    )
  }

  return { ...render(ui, { wrapper: Wrapper, ...renderOptions }), queryClient }
}

// ---------------------------------------------------------------------------
// Hook wrapper factory (for use with renderHook)
// ---------------------------------------------------------------------------

export function makeWrapper(queryClient?: QueryClient) {
  const client = queryClient ?? createTestQueryClient()
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>
  }
}

// ---------------------------------------------------------------------------
// Re-export everything from RTL for convenience
// ---------------------------------------------------------------------------

export * from '@testing-library/react'
