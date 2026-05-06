/**
 * SettingsPage — professional profile configuration.
 *
 * Data flow:
 *   READ  → professional from AuthContext (already in memory, no extra request)
 *   WRITE → PATCH /professionals/me via useUpdateProfile()
 *   SYNC  → refreshProfile() is called on success to keep the context current
 *
 * Fields:
 *   Perfil tab:    full_name, specialty (opt), bio (opt), phone (opt), email (ro)
 *   Valores tab:   session_duration (min), session_price (BRL)
 *   Other tabs:    placeholder UI (feature-complete backend not yet wired)
 *
 * PATCH semantics with backend exclude_none:
 *   Sending null for an optional field does NOT clear it — the backend skips
 *   null values. Empty string → converted to null before sending → field stays
 *   unchanged. This is a known limitation of the current backend schema.
 *
 * Form state across tabs:
 *   react-hook-form v7 defaults shouldUnregister:false, so values are preserved
 *   in the form object even when tab panels unmount. Both Perfil and Valores
 *   submit buttons call the same handleSubmit → same full PATCH payload.
 */

import { useState, useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import type { Resolver } from "react-hook-form";
import { format, parseISO } from "date-fns";
import { ptBR } from "date-fns/locale";
import {
  UserCircle,
  Clock,
  DollarSign,
  MessageCircle,
  Bell,
  Key,
  Save,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { useAuth } from "@/hooks/useAuth";
import { useUpdateProfile } from "./hooks/useUpdateProfile";
import { settingsSchema } from "./schemas/settingsSchema";
import type { SettingsFormValues } from "./schemas/settingsSchema";
import type { UpdateProfilePayload } from "./hooks/useUpdateProfile";

import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { getInitials } from "@/components/shared/Avatar";

// ---------------------------------------------------------------------------
// Tab config
// ---------------------------------------------------------------------------

type TabId =
  | "perfil"
  | "disponibilidade"
  | "valores"
  | "whatsapp"
  | "notificacoes"
  | "seguranca";

const TABS: Array<{ id: TabId; label: string; Icon: LucideIcon }> = [
  { id: "perfil", label: "Perfil", Icon: UserCircle },
  { id: "disponibilidade", label: "Disponibilidade", Icon: Clock },
  { id: "valores", label: "Valores", Icon: DollarSign },
  { id: "whatsapp", label: "WhatsApp", Icon: MessageCircle },
  { id: "notificacoes", label: "Notificações", Icon: Bell },
  { id: "seguranca", label: "Segurança", Icon: Key },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function buildDefaultValues(
  professional: ReturnType<typeof useAuth>["professional"],
): SettingsFormValues {
  return {
    full_name: professional?.full_name ?? "",
    specialty: professional?.specialty ?? "",
    bio: professional?.bio ?? "",
    phone: professional?.phone ?? "",
    session_duration: professional?.session_duration ?? 50,
    session_price:
      professional?.session_price != null
        ? Number(professional.session_price)
        : 0,
  };
}

/**
 * Converts form values to the PATCH payload.
 * Empty-string optional fields become null (backend excludes them → no-op).
 */
function buildPayload(values: SettingsFormValues): UpdateProfilePayload {
  return {
    full_name: values.full_name,
    specialty: values.specialty.trim() || null,
    bio: values.bio.trim() || null,
    phone: values.phone.trim() || null,
    session_duration: values.session_duration,
    session_price: values.session_price,
  };
}

// ---------------------------------------------------------------------------
// SettingsPage
// ---------------------------------------------------------------------------

export function SettingsPage() {
  const { professional } = useAuth();
  const { mutate, isPending } = useUpdateProfile();
  const [activeTab, setActiveTab] = useState<TabId>("perfil");

  const form = useForm<SettingsFormValues>({
    // z.coerce.number() makes input type `unknown` in TFieldValues — explicit
    // cast required (see gotchas_resolved in STATE.json)
    resolver: zodResolver(settingsSchema) as Resolver<SettingsFormValues>,
    defaultValues: buildDefaultValues(professional),
  });

  // Sync form when the AuthContext updates (e.g. after refreshProfile())
  useEffect(() => {
    form.reset(buildDefaultValues(professional));
  }, [professional, form]);

  function handleSubmit(values: SettingsFormValues): void {
    mutate(buildPayload(values));
  }

  const memberSince = professional?.created_at
    ? format(parseISO(professional.created_at), "MMMM 'de' yyyy", {
        locale: ptBR,
      })
    : "";

  const initials = getInitials(professional?.full_name ?? "?");

  return (
    <div style={{ padding: "24px", maxWidth: 1100, margin: "0 auto" }}>
      {/* ── Header ── */}
      <div style={{ marginBottom: 24 }}>
        <h2
          style={{
            fontFamily: "var(--font-heading)",
            fontWeight: 700,
            fontSize: 24,
            color: "var(--text-primary)",
            margin: 0,
          }}
        >
          Configurações
        </h2>
        <p
          style={{
            fontSize: 14,
            color: "var(--text-muted)",
            margin: "4px 0 0",
          }}
        >
          Gerencie perfil e preferências
        </p>
      </div>

      {/* ── Two-column layout ── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "196px 1fr",
          gap: 16,
          alignItems: "start",
        }}
      >
        {/* ── Left: nav tabs ── */}
        <div className="glass-card" style={{ padding: 8, alignSelf: "start" }}>
          {TABS.map(({ id, label, Icon }) => (
            <button
              key={id}
              type="button"
              className={`config-tab${activeTab === id ? " active" : ""}`}
              onClick={() => setActiveTab(id)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                width: "100%",
                textAlign: "left",
                background: "none",
                border: "none",
                cursor: "pointer",
                marginBottom: 2,
              }}
            >
              <Icon size={14} style={{ flexShrink: 0 }} />
              {label}
            </button>
          ))}
        </div>

        {/* ── Right: content ── */}
        <div className="glass-card bordered" style={{ minHeight: 400 }}>
          {/* Form-related tabs (Perfil + Valores share the same RHF form) */}
          {(activeTab === "perfil" || activeTab === "valores") && (
            <Form {...form}>
              <form onSubmit={form.handleSubmit(handleSubmit)}>
                {/* ── Perfil ── */}
                {activeTab === "perfil" && (
                  <div>
                    {/* Avatar + identity row */}
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 14,
                        marginBottom: 20,
                      }}
                    >
                      <div
                        style={{
                          width: 56,
                          height: 56,
                          borderRadius: "50%",
                          background: "rgba(139,92,246,0.20)",
                          border: "1px solid rgba(139,92,246,0.45)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          color: "#c4b5fd",
                          fontSize: 18,
                          fontWeight: 700,
                          flexShrink: 0,
                          letterSpacing: "0.03em",
                        }}
                        aria-label={professional?.full_name ?? "Avatar"}
                      >
                        {initials}
                      </div>
                      <div>
                        <p
                          style={{
                            fontFamily: "var(--font-heading)",
                            fontWeight: 700,
                            fontSize: 15,
                            color: "var(--text-primary)",
                            margin: 0,
                          }}
                        >
                          {professional?.full_name ?? "—"}
                        </p>
                        <p
                          style={{
                            fontSize: 13,
                            color: "var(--text-muted)",
                            margin: "2px 0 0",
                          }}
                        >
                          {professional?.specialty ?? "Profissional de saúde"}
                        </p>
                        {memberSince && (
                          <p
                            style={{
                              fontSize: 11,
                              color: "var(--text-subtle, var(--text-muted))",
                              margin: "2px 0 0",
                            }}
                          >
                            Membro desde {memberSince}
                          </p>
                        )}
                      </div>
                    </div>

                    <div
                      className="card-divider"
                      style={{ marginBottom: 20 }}
                    />

                    {/* Form grid */}
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns:
                          "repeat(auto-fill, minmax(220px, 1fr))",
                        gap: 16,
                        marginBottom: 16,
                      }}
                    >
                      {/* Nome completo */}
                      <FormField
                        control={form.control}
                        name="full_name"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel className="form-label">
                              Nome completo
                            </FormLabel>
                            <FormControl>
                              <Input
                                className="form-input"
                                placeholder="Seu nome profissional"
                                {...field}
                              />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />

                      {/* Especialidade */}
                      <FormField
                        control={form.control}
                        name="specialty"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel className="form-label">
                              Especialidade{" "}
                              <span
                                style={{
                                  color: "var(--text-muted)",
                                  fontWeight: 400,
                                  fontSize: 11,
                                }}
                              >
                                (opcional)
                              </span>
                            </FormLabel>
                            <FormControl>
                              <Input
                                className="form-input"
                                placeholder="Ex: Psicologia, Personal Trainer…"
                                {...field}
                              />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />

                      {/* Telefone */}
                      <FormField
                        control={form.control}
                        name="phone"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel className="form-label">
                              Telefone{" "}
                              <span
                                style={{
                                  color: "var(--text-muted)",
                                  fontWeight: 400,
                                  fontSize: 11,
                                }}
                              >
                                (opcional)
                              </span>
                            </FormLabel>
                            <FormControl>
                              <Input
                                className="form-input"
                                placeholder="+5511999999999"
                                {...field}
                              />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />

                      {/* E-mail (read-only — not in PATCH endpoint) */}
                      <div>
                        <label
                          className="form-label"
                          style={{ display: "block", marginBottom: 6 }}
                        >
                          E-mail
                        </label>
                        <input
                          className="form-input"
                          type="email"
                          value={professional?.email ?? ""}
                          readOnly
                          style={{
                            width: "100%",
                            opacity: 0.55,
                            cursor: "not-allowed",
                          }}
                        />
                      </div>
                    </div>

                    {/* Bio (full width) */}
                    <div style={{ marginBottom: 24 }}>
                      <FormField
                        control={form.control}
                        name="bio"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel className="form-label">
                              Bio{" "}
                              <span
                                style={{
                                  color: "var(--text-muted)",
                                  fontWeight: 400,
                                  fontSize: 11,
                                }}
                              >
                                (opcional)
                              </span>
                            </FormLabel>
                            <FormControl>
                              <Textarea
                                className="form-input"
                                placeholder="Conte um pouco sobre você e sua abordagem…"
                                rows={3}
                                {...field}
                              />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    </div>

                    {/* Submit */}
                    <div
                      style={{ display: "flex", justifyContent: "flex-end" }}
                    >
                      <button
                        type="submit"
                        className="btn-primary"
                        disabled={isPending}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 6,
                        }}
                      >
                        <Save
                          aria-hidden="true"
                          style={{ width: 14, height: 14 }}
                        />
                        {isPending ? "Salvando…" : "Salvar alterações"}
                      </button>
                    </div>
                  </div>
                )}

                {/* ── Valores ── */}
                {activeTab === "valores" && (
                  <div>
                    <p className="card-title" style={{ marginBottom: 6 }}>
                      Configurações de sessão
                    </p>
                    <p
                      style={{
                        fontSize: 12,
                        color: "var(--text-muted)",
                        marginBottom: 24,
                      }}
                    >
                      Padrão aplicado quando você cria novos agendamentos.
                    </p>

                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns:
                          "repeat(auto-fill, minmax(200px, 1fr))",
                        gap: 16,
                        marginBottom: 24,
                      }}
                    >
                      {/* Duração */}
                      <FormField
                        control={form.control}
                        name="session_duration"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel className="form-label">
                              Duração da sessão (min)
                            </FormLabel>
                            <FormControl>
                              <Input
                                className="form-input"
                                type="number"
                                min={15}
                                max={480}
                                placeholder="50"
                                {...field}
                              />
                            </FormControl>
                            <p
                              style={{
                                fontSize: 11,
                                color: "var(--text-muted)",
                                marginTop: 4,
                              }}
                            >
                              Entre 15 e 480 minutos
                            </p>
                            <FormMessage />
                          </FormItem>
                        )}
                      />

                      {/* Preço */}
                      <FormField
                        control={form.control}
                        name="session_price"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel className="form-label">
                              Preço da sessão (R$)
                            </FormLabel>
                            <FormControl>
                              <Input
                                className="form-input"
                                type="number"
                                min={0}
                                step={0.01}
                                placeholder="0.00"
                                {...field}
                              />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    </div>

                    {/* Submit */}
                    <div
                      style={{ display: "flex", justifyContent: "flex-end" }}
                    >
                      <button
                        type="submit"
                        className="btn-primary"
                        disabled={isPending}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 6,
                        }}
                      >
                        <Save
                          aria-hidden="true"
                          style={{ width: 14, height: 14 }}
                        />
                        {isPending ? "Salvando…" : "Salvar alterações"}
                      </button>
                    </div>
                  </div>
                )}
              </form>
            </Form>
          )}

          {/* ── Disponibilidade ── */}
          {activeTab === "disponibilidade" && (
            <div>
              <p className="card-title" style={{ marginBottom: 16 }}>
                Disponibilidade
              </p>
              <div className="alert alert-info">
                Configure seus horários de atendimento diretamente na{" "}
                <strong>Agenda</strong>, nos slots de disponibilidade.
              </div>
            </div>
          )}

          {/* ── WhatsApp ── */}
          {activeTab === "whatsapp" && (
            <div>
              <p className="card-title" style={{ marginBottom: 16 }}>
                WhatsApp
              </p>
              <div className="alert alert-purple">
                A configuração do WhatsApp estará disponível em breve. Você
                poderá conectar seu número via Embedded Signup.
              </div>
            </div>
          )}

          {/* ── Notificações ── */}
          {activeTab === "notificacoes" && (
            <div>
              <p className="card-title" style={{ marginBottom: 16 }}>
                Notificações
              </p>
              <div className="alert alert-info">
                As preferências de notificação estarão disponíveis em breve.
              </div>
            </div>
          )}

          {/* ── Segurança ── */}
          {activeTab === "seguranca" && (
            <div>
              <p className="card-title" style={{ marginBottom: 20 }}>
                Alterar senha
              </p>

              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 14,
                  maxWidth: 340,
                }}
              >
                {/* Senha atual */}
                <div>
                  <label
                    className="form-label"
                    style={{ display: "block", marginBottom: 6 }}
                  >
                    Senha atual
                  </label>
                  <input
                    className="form-input"
                    type="password"
                    placeholder="••••••••"
                    autoComplete="current-password"
                    style={{ width: "100%" }}
                  />
                </div>

                {/* Nova senha */}
                <div>
                  <label
                    className="form-label"
                    style={{ display: "block", marginBottom: 6 }}
                  >
                    Nova senha
                  </label>
                  <input
                    className="form-input"
                    type="password"
                    placeholder="••••••••"
                    autoComplete="new-password"
                    style={{ width: "100%" }}
                  />
                </div>

                {/* Confirmar nova senha */}
                <div>
                  <label
                    className="form-label"
                    style={{ display: "block", marginBottom: 6 }}
                  >
                    Confirmar nova senha
                  </label>
                  <input
                    className="form-input"
                    type="password"
                    placeholder="••••••••"
                    autoComplete="new-password"
                    style={{ width: "100%" }}
                  />
                </div>

                <div
                  style={{
                    display: "flex",
                    justifyContent: "flex-end",
                    marginTop: 4,
                  }}
                >
                  <button
                    type="button"
                    className="btn-primary"
                    disabled
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 6,
                      opacity: 0.55,
                      cursor: "not-allowed",
                    }}
                  >
                    <Save
                      aria-hidden="true"
                      style={{ width: 14, height: 14 }}
                    />
                    Alterar senha
                  </button>
                </div>

                <p style={{ fontSize: 11, color: "var(--text-muted)" }}>
                  Funcionalidade de alteração de senha em breve.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
