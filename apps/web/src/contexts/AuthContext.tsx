import {
  createContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import axios from "axios";
import api, { setAccessToken } from "@/services/api";
import type {
  AccessTokenResponse,
  LoginRequest,
  ProfessionalResponse,
  RegisterRequest,
} from "@/types/auth";

// ---------------------------------------------------------------------------
// Context shape
// ---------------------------------------------------------------------------

interface AuthContextValue {
  professional: ProfessionalResponse | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  logout: () => Promise<void>;
  /** Re-fetches /professionals/me and updates the in-memory professional state.
   *  Call after a successful PATCH /professionals/me to keep the context in sync. */
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function extractErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    // Backend format: { error: { message: string } }
    const msg: unknown = error.response?.data?.error?.message;
    if (typeof msg === "string" && msg.length > 0) return msg;
  }
  return fallback;
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [professional, setProfessional] = useState<ProfessionalResponse | null>(
    null,
  );
  const [isLoading, setIsLoading] = useState(true);

  // ---------------------------------------------------------------------------
  // Session restore on mount
  // Tries to exchange the HttpOnly refresh_token cookie for a new access_token.
  // If the cookie is missing or expired, the user is simply not authenticated.
  // ---------------------------------------------------------------------------

  const didAttemptRestore = useRef(false);

  useEffect(() => {
    // Guard against React StrictMode double-invocation
    if (didAttemptRestore.current) return;
    didAttemptRestore.current = true;

    let mounted = true;

    async function restoreSession(): Promise<void> {
      try {
        const { data: tokenData } =
          await api.post<AccessTokenResponse>("/auth/refresh");

        if (!mounted) return;
        setAccessToken(tokenData.access_token);

        const { data: profData } =
          await api.get<ProfessionalResponse>("/professionals/me");

        if (!mounted) return;
        setProfessional(profData);
      } catch {
        // Cookie missing, expired, or network error -- treat as unauthenticated.
        // Do NOT redirect here; the route guards handle redirection.
        // Note: no `if (mounted)` guard here — clearing a stale token is always safe.
        setAccessToken(null);
      } finally {
        // Always clear loading, regardless of mounted state.
        //
        // Why: in dev, React 18 StrictMode runs cleanup (mounted=false) BEFORE the
        // async POST /auth/refresh completes. The useRef guard correctly prevents a
        // second restoreSession call, but the first one finishes after mounted=false.
        // Without this unconditional call, isLoading stays true forever → blank page.
        // In React 18, calling a state setter after unmount is a safe no-op.
        setIsLoading(false);
      }
    }

    void restoreSession();

    return () => {
      mounted = false;
    };
  }, []);

  // ---------------------------------------------------------------------------
  // login
  // ---------------------------------------------------------------------------

  async function login(email: string, password: string): Promise<void> {
    try {
      const { data: tokenData } = await api.post<AccessTokenResponse>(
        "/auth/login",
        { email, password } satisfies LoginRequest,
      );
      setAccessToken(tokenData.access_token);

      const { data: profData } =
        await api.get<ProfessionalResponse>("/professionals/me");
      setProfessional(profData);
    } catch (error) {
      // Clear any stale state before re-throwing
      setAccessToken(null);
      throw new Error(extractErrorMessage(error, "Credenciais inválidas"));
    }
  }

  // ---------------------------------------------------------------------------
  // register
  // ---------------------------------------------------------------------------

  async function register(data: RegisterRequest): Promise<void> {
    try {
      await api.post("/auth/register", data);
      // Immediately authenticate after successful registration
      await login(data.email, data.password);
    } catch (error) {
      // Re-throw with a message the form can display.
      // login() already sets a good message for auth failures;
      // here we handle registration-specific errors (e.g. duplicate email).
      if (error instanceof Error) throw error;
      throw new Error(extractErrorMessage(error, "Erro ao criar conta"));
    }
  }

  // ---------------------------------------------------------------------------
  // refreshProfile
  // ---------------------------------------------------------------------------

  async function refreshProfile(): Promise<void> {
    const { data } = await api.get<ProfessionalResponse>("/professionals/me");
    setProfessional(data);
  }

  // ---------------------------------------------------------------------------
  // logout
  // ---------------------------------------------------------------------------

  async function logout(): Promise<void> {
    try {
      await api.post("/auth/logout");
    } catch {
      // Even if the server call fails (e.g. network error), clear local state.
      // The server will eventually expire the token.
    } finally {
      setAccessToken(null);
      setProfessional(null);
    }
  }

  // ---------------------------------------------------------------------------
  // Context value
  // ---------------------------------------------------------------------------

  const value: AuthContextValue = {
    professional,
    isLoading,
    isAuthenticated: professional !== null,
    login,
    register,
    logout,
    refreshProfile,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ---------------------------------------------------------------------------
// Raw context export (for useAuth hook)
// ---------------------------------------------------------------------------

export { AuthContext };
