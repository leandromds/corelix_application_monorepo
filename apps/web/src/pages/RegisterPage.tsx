import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Stethoscope } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import type { RegisterRequest } from "@/types/auth";

export function RegisterPage() {
  const { register } = useAuth();

  const [formData, setFormData] = useState<RegisterRequest>({
    email: "",
    password: "",
    full_name: "",
    specialty: "",
    bio: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function handleChange(
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
  ): void {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>): Promise<void> {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    // Strip empty optional fields before sending
    const payload: RegisterRequest = {
      email: formData.email,
      password: formData.password,
      full_name: formData.full_name,
      ...(formData.specialty?.trim() && {
        specialty: formData.specialty.trim(),
      }),
      ...(formData.bio?.trim() && { bio: formData.bio.trim() }),
    };

    try {
      await register(payload);
      // On success: register() calls login() internally → professional is set
      // → PublicRoute redirects to /dashboard automatically.
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao criar conta");
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
          maxWidth: "420px",
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
              Criar conta
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
          <div style={{ marginBottom: "14px" }}>
            <label htmlFor="email" className="form-label">
              E-mail <span style={{ color: "var(--danger)" }}>*</span>
            </label>
            <input
              id="email"
              name="email"
              type="email"
              value={formData.email}
              onChange={handleChange}
              required
              autoComplete="email"
              className="form-input"
              placeholder="seu@email.com"
            />
          </div>

          {/* Senha */}
          <div style={{ marginBottom: "14px" }}>
            <label htmlFor="password" className="form-label">
              Senha <span style={{ color: "var(--danger)" }}>*</span>
            </label>
            <input
              id="password"
              name="password"
              type="password"
              value={formData.password}
              onChange={handleChange}
              required
              minLength={8}
              autoComplete="new-password"
              className="form-input"
              placeholder="Mínimo 8 caracteres"
            />
          </div>

          {/* Nome completo */}
          <div style={{ marginBottom: "14px" }}>
            <label htmlFor="full_name" className="form-label">
              Nome completo <span style={{ color: "var(--danger)" }}>*</span>
            </label>
            <input
              id="full_name"
              name="full_name"
              type="text"
              value={formData.full_name}
              onChange={handleChange}
              required
              autoComplete="name"
              className="form-input"
              placeholder="Seu nome completo"
            />
          </div>

          {/* Especialidade */}
          <div style={{ marginBottom: "14px" }}>
            <label htmlFor="specialty" className="form-label">
              Especialidade{" "}
              <span style={{ color: "var(--text-subtle)", fontWeight: 400 }}>
                (opcional)
              </span>
            </label>
            <input
              id="specialty"
              name="specialty"
              type="text"
              value={formData.specialty ?? ""}
              onChange={handleChange}
              className="form-input"
              placeholder="Ex: Fisioterapia, Psicologia..."
            />
          </div>

          {/* Bio */}
          <div style={{ marginBottom: "20px" }}>
            <label htmlFor="bio" className="form-label">
              Bio{" "}
              <span style={{ color: "var(--text-subtle)", fontWeight: 400 }}>
                (opcional)
              </span>
            </label>
            <textarea
              id="bio"
              name="bio"
              value={formData.bio ?? ""}
              onChange={handleChange}
              rows={3}
              className="form-input"
              placeholder="Uma breve descrição sobre você..."
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
            {isSubmitting ? "Criando conta..." : "Criar conta"}
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
          Já tem conta?{" "}
          <Link
            to="/login"
            style={{
              color: "hsl(260,95%,75%)",
              textDecoration: "none",
              fontWeight: 600,
            }}
          >
            Entrar
          </Link>
        </p>
      </div>
    </div>
  );
}
