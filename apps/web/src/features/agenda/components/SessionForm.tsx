import { useEffect } from "react";
import { useForm, type Resolver } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { format } from "date-fns";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
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
      createSession.mutate(payload, { onSuccess: () => onOpenChange(false) });
    }
  }

  const isPending = createSession.isPending || updateSession.isPending;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle
            style={{
              fontFamily: "var(--font-heading)",
              color: "var(--text-primary)",
            }}
          >
            {isEdit ? "Editar Sessão" : "Nova Sessão"}
          </DialogTitle>
          <DialogDescription style={{ color: "var(--text-muted)" }}>
            {isEdit
              ? "Edite os dados da sessão agendada."
              : "Preencha os dados para agendar uma nova sessão."}
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(onSubmit)}
            className="space-y-4 pt-2"
          >
            {/* Cliente */}
            <FormField
              control={form.control}
              name="client_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Cliente</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Selecione um cliente" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {clients.map((client) => (
                        <SelectItem key={client.id} value={client.id}>
                          {client.full_name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Data e hora */}
            <FormField
              control={form.control}
              name="scheduled_at"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Data e hora</FormLabel>
                  <FormControl>
                    <Input type="datetime-local" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Duração e Valor — side by side */}
            <div className="grid grid-cols-2 gap-4">
              <FormField
                control={form.control}
                name="duration_minutes"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Duração (min)</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        min={15}
                        max={480}
                        step={5}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="price"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Valor (R$)</FormLabel>
                    <FormControl>
                      <Input placeholder="150.00" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            {/* Status */}
            <FormField
              control={form.control}
              name="status"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Status</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {(
                        Object.keys(STATUS_LABELS) as Array<
                          keyof typeof STATUS_LABELS
                        >
                      ).map((value) => (
                        <SelectItem key={value} value={value}>
                          {STATUS_LABELS[value]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Notas */}
            <FormField
              control={form.control}
              name="notes"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Notas</FormLabel>
                  <FormControl>
                    <Textarea
                      placeholder="Observações sobre a sessão..."
                      rows={3}
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <DialogFooter className="pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
              >
                Cancelar
              </Button>
              <Button
                type="submit"
                disabled={isPending}
                style={{
                  background: "var(--color-primary)",
                  color: "var(--color-primary-fg)",
                }}
              >
                {isPending ? "Salvando..." : isEdit ? "Salvar" : "Agendar"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
