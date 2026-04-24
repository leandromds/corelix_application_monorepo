import axios, {
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from 'axios'
import type { AccessTokenResponse } from '@/types/auth'

// ---------------------------------------------------------------------------
// Token storage -- module variable (never localStorage)
// ---------------------------------------------------------------------------

let _accessToken: string | null = null

export function setAccessToken(token: string | null): void {
  _accessToken = token
}

export function getAccessToken(): string | null {
  return _accessToken
}

// ---------------------------------------------------------------------------
// Axios instance
// ---------------------------------------------------------------------------

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? '/api/v1',
  withCredentials: true, // Required for HttpOnly refresh_token cookie
  headers: { 'Content-Type': 'application/json' },
})

// ---------------------------------------------------------------------------
// Request interceptor -- inject Bearer token
// ---------------------------------------------------------------------------

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (_accessToken) {
    config.headers.set('Authorization', `Bearer ${_accessToken}`)
  }
  return config
})

// ---------------------------------------------------------------------------
// Response interceptor -- handle 401 -> refresh -> retry
// ---------------------------------------------------------------------------

interface QueueItem {
  resolve: (token: string) => void
  reject: (error: unknown) => void
}

let _isRefreshing = false
let _refreshQueue: QueueItem[] = []

function flushQueue(error: unknown, token: string | null): void {
  _refreshQueue.forEach(({ resolve, reject }) => {
    if (error !== null || token === null) {
      reject(error)
    } else {
      resolve(token)
    }
  })
  _refreshQueue = []
}

// Endpoints where a 401 should NOT trigger a refresh attempt.
// These are authentication endpoints -- a 401 from them means
// wrong credentials or an invalid token, not an expired session.
const SKIP_REFRESH_PATHS = ['/auth/refresh', '/auth/login', '/auth/register']

type RetryConfig = InternalAxiosRequestConfig & { _retry?: boolean }

api.interceptors.response.use(
  (response: AxiosResponse) => response,
  async (error: unknown) => {
    if (!axios.isAxiosError(error)) {
      return Promise.reject(error)
    }

    const config = error.config as RetryConfig | undefined

    const shouldSkip =
      error.response?.status !== 401 ||
      config === undefined ||
      config._retry === true ||
      SKIP_REFRESH_PATHS.some((path) => config.url?.includes(path))

    if (shouldSkip) {
      return Promise.reject(error)
    }

    // Mark so that if the retry itself gets a 401 we don't loop
    config._retry = true

    if (_isRefreshing) {
      // Another refresh is already in flight -- queue this request.
      // It will be retried automatically once the token arrives.
      return new Promise<string>((resolve, reject) => {
        _refreshQueue.push({ resolve, reject })
      }).then((token) => {
        config.headers.set('Authorization', `Bearer ${token}`)
        return api(config)
      })
    }

    _isRefreshing = true

    try {
      const { data } = await api.post<AccessTokenResponse>('/auth/refresh')
      setAccessToken(data.access_token)
      flushQueue(null, data.access_token)
      // Retry the original request -- request interceptor will attach new token
      return api(config)
    } catch (refreshError) {
      setAccessToken(null)
      flushQueue(refreshError, null)
      return Promise.reject(refreshError)
    } finally {
      _isRefreshing = false
    }
  },
)

export default api
