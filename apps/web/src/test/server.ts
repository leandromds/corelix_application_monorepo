/**
 * MSW Node server — imported as a Vitest setupFile so the server
 * lifecycle (listen / resetHandlers / close) runs automatically for
 * every test file without any manual wiring.
 *
 * Individual tests add per-test handlers via:
 *   import { server } from '@/test/server'
 *   server.use(http.get(BASE_URL + '/clients', () => ...))
 */

import { setupServer } from 'msw/node'

export const server = setupServer()

// ---------------------------------------------------------------------------
// Base URL helper — matches the axios instance baseURL in src/services/api.ts
// (baseURL: import.meta.env.VITE_API_URL ?? '/api/v1')
// In jsdom (url: 'http://localhost'), axios resolves '/api/v1' to:
//   http://localhost/api/v1
// ---------------------------------------------------------------------------

export const BASE_URL = 'http://localhost/api/v1'

// ---------------------------------------------------------------------------
// Lifecycle — using Vitest globals (globals: true in vite.config.ts)
// ---------------------------------------------------------------------------

// 'warn' instead of 'error': during retroactive coverage there may be
// requests not yet mocked (e.g. /auth/refresh from the response interceptor).
beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
