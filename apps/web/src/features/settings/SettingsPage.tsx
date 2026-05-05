/**
 * SettingsPage — professional profile configuration.
 *
 * Data flow:
 *   READ  → professional from AuthContext (already in memory, no extra request)
 *   WRITE → PATCH /professionals/me via useUpdateProfile()
 *   SYNC  → refreshProfile() is called on success to keep the context current
 *
 * Fields:
 *   Personal:  full_name, specialty (opt), bio (opt), phone (opt)
 *   Session:   session_duration (min), session_price (BRL)
 *   Read-only: email (not updatable via this endpoint by design)
 *
 * PATCH semantics with backend exclude_none:
 *   Sending null for an optional field does NOT clear it — the backend skips
 *   null values. Empty string → converted to null before sending → field stays
 *   unchanged. This is a known limitation of the current backend schema.
 */

import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import type { Resolver } from "react-hook-form";
import { format, parseISO } from "date-fns";
import { ptBR } from "date-fns/locale";

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
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Avatar, getInitials } from "@/components/shared/Avatar";

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
// Section wrapper
// ---------------------------------------------------------------------------

function Section({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <div
      style={{
        paddingBottom: 28,
        borderBottom: "1px solid var(--border-default)",
        marginBottom: 28,
      }}
    >
      <div style={{ marginBottom: 16 }}>
        <p
          style={{
            fontSize: 14,
            fontWeight: 600,
            color: "var(--text-primary)",
            margin: 0,
          }}
        >
          {title}
        </p>
        {description && (
          <p
            style={{
              fontSize: 12,
              color: "var(--text-muted)",
              margin: "2px 0 0",
            }}
          >
            {description}
          </p>
        )}
      </div>
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// SettingsPage
// ---------------------------------------------------------------------------

export function SettingsPage() {
  const { professional } = useAuth();
  const { mutate, isPending } = useUpdateProfile();

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

  return (
    <div
      style={{
        padding: "24px",
        maxWidth: 740,
        margin: "0 auto",
      }}
    >
      {/* ── Header ── */}
      <div style={{ marginBottom: 28 }}>
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
          Gerencie seu perfil e preferências de atendimento
        </p>
      </div>

      {/* ── Main card ── */}
      <div
        style={{
          background: "var(--bg-surface-card)",
          borderRadius: "var(--radius-lg)",
          border: "1px solid var(--border-default)",
          boxShadow: "var(--shadow-card)",
          padding: "32px",
        }}
      >
        {/* ── Account info (read-only) ── */}
        <Section
          title="Conta"
          description="Informações de acesso (não editáveis)"
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 16,
              padding: "14px 16px",
              background: "var(--bg-surface)",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border-default)",
            }}
          >
            <Avatar
              initials={getInitials(professional?.full_name ?? "?")}
              size="lg"
            />
            <div>
              <p
                style={{
                  fontSize: 14,
                  fontWeight: 600,
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
                {professional?.email}
              </p>
              {memberSince && (
                <p
                  style={{
                    fontSize: 11,
                    color: "var(--text-muted)",
                    margin: "2px 0 0",
                  }}
                >
                  Membro desde {memberSince}
                </p>
              )}
            </div>
          </div>
        </Section>

        {/* ── Editable form ── */}
        <Form {...form}>
          <form onSubmit={form.handleSubmit(handleSubmit)}>
            {/* ── Informações pessoais ── */}
            <Section
              title="Informações pessoais"
              description="Dados exibidos para seus clientes"
            >
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
                  gap: 16,
                }}
              >
                {/* Nome completo */}
                <FormField
                  control={form.control}
                  name="full_name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Nome completo</FormLabel>
                      <FormControl>
                        <Input placeholder="Seu nome profissional" {...field} />
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
                      <FormLabel>
                        Especialidade{" "}
                        <span
                          style={{
                            color: "var(--text-muted)",
                            fontWeight: 400,
                            fontSize: 12,
                          }}
                        >
                          (opcional)
                        </span>
                      </FormLabel>
                      <FormControl>
                        <Input
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
                      <FormLabel>
                        Telefone{" "}
                        <span
                          style={{
                            color: "var(--text-muted)",
                            fontWeight: 400,
                            fontSize: 12,
                          }}
                        >
                          (opcional)
                        </span>
                      </FormLabel>
                      <FormControl>
                        <Input placeholder="+5511999999999" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              {/* Bio */}
              <div style={{ marginTop: 16 }}>
                <FormField
                  control={form.control}
                  name="bio"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>
                        Bio{" "}
                        <span
                          style={{
                            color: "var(--text-muted)",
                            fontWeight: 400,
                            fontSize: 12,
                          }}
                        >
                          (opcional)
                        </span>
                      </FormLabel>
                      <FormControl>
                        <Textarea
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
            </Section>

            {/* ── Configurações de sessão ── */}
            <Section
              title="Configurações de sessão"
              description="Padrão aplicado quando você cria novos agendamentos"
            >
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
                  gap: 16,
                }}
              >
                {/* Duração da sessão */}
                <FormField
                  control={form.control}
                  name="session_duration"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Duração da sessão (min)</FormLabel>
                      <FormControl>
                        <Input
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
                          marginTop: 2,
                        }}
                      >
                        Entre 15 e 480 minutos
                      </p>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                {/* Preço da sessão */}
                <FormField
                  control={form.control}
                  name="session_price"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Preço da sessão (R$)</FormLabel>
                      <FormControl>
                        <Input
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
            </Section>

            {/* ── Submit ── */}
            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <Button type="submit" disabled={isPending}>
                {isPending ? "Salvando…" : "Salvar alterações"}
              </Button>
            </div>
          </form>
        </Form>
      </div>
    </div>
  );
}
