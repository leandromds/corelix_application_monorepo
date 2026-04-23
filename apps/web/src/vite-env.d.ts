/// <reference types="vite/client" />

// Type definitions for environment variables
// Add VITE_ prefixed variables here for type safety
interface ImportMetaEnv {
  readonly VITE_API_URL: string
  readonly VITE_APP_TITLE: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
