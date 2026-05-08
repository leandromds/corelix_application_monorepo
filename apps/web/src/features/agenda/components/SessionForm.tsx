import { useEffect } from "react";
import posthog from "posthog-js";
import { useForm, type Resolver } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { format } from "date-fns";

import { useClients } from "@/features/clients/hooks/useClients";

import {
  sessionSchema,
  type SessionFormValues,
} from "../schemas/sessionSchema";
import { useCreateSession } from "../hooks/useCreateSession";
import { useUpdateSession } from "../hooks/useUpdateSession";
import type {
  Session,
  CreateSessionPayload,
  UpdateSessionPayload,
} from "../types";
import { STATUS_LABELS } from "../types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Convert a datetime-local string ("2025-07-20T14:00") to ISO with local TZ offset. */
function toISOWithOffset(localDatetime: string): string {
  const date = new Date(localDatetime);
  const offset = -date.getTimezoneOffset();
  const sign = offset >= 0 ? "+" : "-";
  const pad = (n: number) => String(Math.abs(n)).padStart(2, "0");
  const hours = pad(Math.floor(Math.abs(offset) / 60));
  const minutes = pad(Math.abs(offset) % 60);
  return `${date.toISOString().slice(0, 19)}${sign}${hours}:${minutes}`;
}

/** Convert an ISO date string to the "YYYY-MM-DDTHH:mm" format for datetime-local inputs. */
function isoToDatetimeLocal(iso: string): string {
  return new Date(iso).toISOString().slice(0, 16);
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface SessionFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** When provided, the form operates in edit mode. */
  session?: Session | null;
  /** Pre-fill scheduled_at when the user clicked on a calendar slot. */
  defaultDate?: Date;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SessionForm({
  open,
  onOpenChange,
  session,
  defaultDate,
}: SessionFormProps) {
  const { data: clients = [] } = useClients({ is_active: true });
  const createSession = useCreateSession();
  const updateSession = useUpdateSession();

  const isEdit = session !== null && session !== undefined;

  const form = useForm<SessionFormValues>({
    // z.coerce.number() has input type `unknown`, causing a static type
    // incompatibility with useForm's Resolver generic. The cast is safe:
    // at runtime zodResolver correctly validates and returns SessionFormValues.
    resolver: zodResolver(sessionSchema) as Resolver<SessionFormValues>,
    defaultValues: {
      client_id: "",
      scheduled_at: "",
      duration_minutes: 50,
      price: "0.00",
      status: "scheduled",
      notes: "",
    },
  });

  // Close on Escape key.
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onOpenChange(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onOpenChange]);

  // Reset the form whenever the dialog opens or the target session changes.
  useEffect(() => {
    if (!open) return;
    form.reset({
      client_id: session?.client_id ?? "",
      scheduled_at: session
        ? isoToDatetimeLocal(session.scheduled_at)
        : defaultDate
          ? format(defaultDate, "yyyy-MM-dd'T'HH:mm")
          : "",
      duration_minutes: session?.duration_minutes ?? 50,
      price: session?.price ?? "0.00",
      status: session?.status ?? "scheduled",
      notes: session?.notes ?? "",
    });
  }, [open, session, defaultDate, form]);

  function onSubmit(values: SessionFormValues): void {
    const scheduledAt = toISOWithOffset(values.scheduled_at);

    if (isEdit && session) {
      // PATCH semântico: only send fields that actually changed.
      const { dirtyFields } = form.formState;
      const changed: UpdateSessionPayload = {};
      if (dirtyFields.client_id) changed.client_id = values.client_id;
      if (dirtyFields.scheduled_at) changed.scheduled_at = scheduledAt;
      if (dirtyFields.duration_minutes)
        changed.duration_minutes = values.duration_minutes;
      if (dirtyFields.price) changed.price = values.price;
      if (dirtyFields.status) changed.status = values.status;
      if (dirtyFields.notes !== undefined) changed.notes = values.notes;

      updateSession.mutate(
        { id: session.id, payload: changed },
        { onSuccess: () => onOpenChange(false) },
      );
    } else {
      const payload: CreateSessionPayload = {
        client_id: values.client_id,
        scheduled_at: scheduledAt,
        duration_minutes: values.duration_minutes,
        price: values.price,
        status: values.status,
        notes: values.notes || undefined,
      };
      createSession.mutate(payload, {
        onSuccess: () => {
          posthog.capture("appointment_created");
          onOpenChange(false);
        },
      });
    }
  }

  const isPending = createSession.isPending || updateSession.isPending;

  if (!open) return null;

  return (
    <div className="modal-overlay animate-fade-in" onClick={() => onOpenChange(false)}>
      <div
        className="modal animate-slide-up"
        role="dialog"
        aria-modal="true"
        aria-labelledby="sf-title"
        aria-describedby="sf-desc"
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: 520, width: "100%" }}
      >
        <div className="modal-header">
          <h2
            className="modal-title"
            id="sf-title"
            style={{ fontFamily: "var(--font-heading)" }}
          >
            {isEdit ? "Editar Sessão" : "Nova Sessão"}
          </h2>
          <button
            className="modal-close"
            type="button"
            onClick={() => onOpenChange(false)}
            aria-label="Fechar"
          >
            <i className="fas fa-xmark" />
          </button>
        </div>

        <p
          id="sf-desc"
          style={{ fontSize: 12, color: "var(--text-muted)", margin: "0 0 16px" }}
        >
          {isEdit
            ? "Edite os dados da sessão agendada."
            : "Preencha os dados para agendar uma nova sessão."}
        </p>

        <form onSubmit={form.handleSubmit(onSubmit)}>
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {/* Cliente */}
            <div>
              <label className="label" htmlFor="sf-client_id">
                Cliente
              </label>
              <select
                id="sf-client_id"
                className="input"
                style={{
                  background: "var(--bg-surface)",
                  color: "var(--text-primary)",
                }}
                autoFocus
                {...form.register("client_id")}
              >
                <option value="">Selecione um cliente</option>
                {clients.map((client) => (
                  <option key={client.id} value={client.id}>
                    {client.full_name}
                  </option>
                ))}
              </select>
              {form.formState.errors.client_id && (
                <p style={{ fontSize: 11, color: "var(--danger)", margin: "4px 0 0" }}>
                  {form.formState.errors.client_id.message}
                </p>
              )}
            </div>

            {/* Data e hora */}
            <div>
              <label className="label" htmlFor="sf-scheduled_at">
                Data e hora
              </label>
              <input
                id="sf-scheduled_at"
                className="input"
                type="datetime-local"
                {...form.register("scheduled_at")}
              />
              {form.formState.errors.scheduled_at && (
                <p style={{ fontSize: 11, color: "var(--danger)", margin: "4px 0 0" }}>
                  {form.formState.errors.scheduled_at.message}
                </p>
              )}
            </div>

            {/* Duração e Valor — side by side */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label" htmlFor="sf-duration">
                  Duração (min)
                </label>
                <input
                  id="sf-duration"
                  className="input"
                  type="number"
                  min={15}
                  max={480}
                  step={5}
                  {...form.register("duration_minutes")}
                />
                {form.formState.errors.duration_minutes && (
                  <p style={{ fontSize: 11, color: "var(--danger)", margin: "4px 0 0" }}>
                    {form.formState.errors.duration_minutes.message}
                  </p>
                )}
              </div>

              <div>
                <label className="label" htmlFor="sf-price">
                  Valor (R$)
                </label>
                <input
                  id="sf-price"
                  className="input"
                  type="text"
                  placeholder="150.00"
                  {...form.register("price")}
                />
                {form.formState.errors.price && (
                  <p style={{ fontSize: 11, color: "var(--danger)", margin: "4px 0 0" }}>
                    {form.formState.errors.price.message}
                  </p>
                )}
              </div>
            </div>

            {/* Status */}
            <div>
              <label className="label" htmlFor="sf-status">
                Status
              </label>
              <select
                id="sf-status"
                className="input"
                style={{
                  background: "var(--bg-surface)",
                  color: "var(--text-primary)",
                }}
                {...form.register("status")}
              >
                {(
                  Object.keys(STATUS_LABELS) as Array<
                    keyof typeof STATUS_LABELS
                  >
                ).map((value) => (
                  <option key={value} value={value}>
                    {STATUS_LABELS[value]}
                  </option>
                ))}
              </select>
              {form.formState.errors.status && (
                <p style={{ fontSize: 11, color: "var(--danger)", margin: "4px 0 0" }}>
                  {form.formState.errors.status.message}
                </p>
              )}
            </div>

            {/* Notas */}
            <div>
              <label className="label" htmlFor="sf-notes">
                Notas
              </label>
              <textarea
                id="sf-notes"
                className="input"
                placeholder="Observações sobre a sessão..."
                rows={3}
                style={{ resize: "vertical" }}
                {...form.register("notes")}
              />
              {form.formState.errors.notes && (
                <p style={{ fontSize: 11, color: "var(--danger)", margin: "4px 0 0" }}>
                  {form.formState.errors.notes.message}
                </p>
              )}
            </div>
          </div>

          <div className="modal-footer">
            <button
              type="button"
              className="btn-secondary"
              onClick={() => onOpenChange(false)}
            >
              Cancelar
            </button>
            <button type="submit" className="btn-primary" disabled={isPending}>
              <i className={isPending ? "fas fa-spinner fa-spin" : "fas fa-floppy-disk"} />{" "}
              {isPending ? "Salvando..." : isEdit ? "Salvar" : "Agendar"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
