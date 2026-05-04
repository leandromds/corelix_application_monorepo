import { z } from "zod";

export const sessionSchema = z.object({
  client_id: z.string().min(1, "Selecione um cliente"),
  scheduled_at: z.string().min(1, "Data e hora são obrigatórios"),
  duration_minutes: z.coerce
    .number()
    .int()
    .min(15, "Mínimo 15 minutos")
    .max(480, "Máximo 8 horas"),
  price: z.string().regex(/^\d+([.,]\d{1,2})?$/, "Valor inválido"),
  status: z.enum(["scheduled", "completed", "cancelled", "no_show"]),
  notes: z.string().optional(),
});

export type SessionFormValues = z.infer<typeof sessionSchema>;
