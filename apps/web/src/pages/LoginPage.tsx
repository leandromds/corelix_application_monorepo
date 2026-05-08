import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Stethoscope } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";

export function LoginPage() {
  const { login } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent<HTMLFormElement>): Promise<void> {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await login(email, password);
      // On success: AuthContext sets `professional`, isAuthenticated becomes true,
      // and PublicRoute redirects to /dashboard automatically.
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao fazer login");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        height: "100%",
        overflowY: "auto",
        background: "var(--bg-page)",
        padding: "20px",
        position: "relative",
      }}
    >
      {/* Background blobs */}
      <div className="blob blob-1" />
      <div className="blob blob-2" />

      {/* Glass card */}
      <div
        className="glass-card bordered glow animate-slide-up"
        style={{
          width: "100%",
          maxWidth: "400px",
          zIndex: 1,
          padding: "32px",
        }}
      >
        {/* Logo + title */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            marginBottom: "28px",
            gap: "12px",
          }}
        >
          <div
            style={{
              width: "48px",
              height: "48px",
              borderRadius: "var(--radius-lg)",
              background: "rgba(139, 92, 246, 0.20)",
              border: "1px solid rgba(139, 92, 246, 0.45)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Stethoscope size={22} style={{ color: "hsl(260,95%,75%)" }} />
          </div>

          <div style={{ textAlign: "center" }}>
            <h1
              style={{
                fontFamily: "var(--font-heading)",
                fontSize: "20px",
                fontWeight: 800,
                color: "var(--text-primary)",
                margin: 0,
              }}
            >
              Corelix
            </h1>
            <p
              style={{
                fontSize: "12px",
                color: "var(--text-muted)",
                margin: "4px 0 0",
              }}
            >
              Secretária Digital
            </p>
          </div>
        </div>

        <form
          onSubmit={(e) => {
            void handleSubmit(e);
          }}
          noValidate
        >
          {/* E-mail */}
          <div style={{ marginBottom: "16px" }}>
            <label htmlFor="email" className="form-label">
              E-mail
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              className="form-input"
              placeholder="seu@email.com"
            />
          </div>

          {/* Senha */}
          <div style={{ marginBottom: "20px" }}>
            <label htmlFor="password" className="form-label">
              Senha
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              className="form-input"
              placeholder="Sua senha"
            />
          </div>

          {/* Error */}
          {error !== null && (
            <div
              role="alert"
              className="alert alert-danger"
              style={{ marginBottom: "16px" }}
            >
              {error}
            </div>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={isSubmitting}
            className="btn-primary"
            style={{
              width: "100%",
              justifyContent: "center",
              padding: "10px 18px",
              fontSize: "13px",
            }}
          >
            {isSubmitting ? "Entrando..." : "Entrar"}
          </button>
        </form>

        {/* Footer link */}
        <p
          style={{
            textAlign: "center",
            fontSize: "12px",
            color: "var(--text-muted)",
            marginTop: "20px",
            marginBottom: 0,
          }}
        >
          Ainda não tem conta?{" "}
          <Link
            to="/register"
            style={{
              color: "hsl(260,95%,75%)",
              textDecoration: "none",
              fontWeight: 600,
            }}
          >
            Criar conta
          </Link>
        </p>
      </div>
    </div>
  );
}
