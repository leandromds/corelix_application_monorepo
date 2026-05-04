import { z } from "zod";

export const clientSchema = z.object({
  full_name: z.string().min(2, "Nome deve ter pelo menos 2 caracteres"),
  phone: z.string().regex(/^\+55\d{10,11}$/, "Formato: +5511999999999"),
  email: z.string().email("E-mail inválido").optional().or(z.literal("")),
  notes: z.string().optional(),
  whatsapp_opt_in: z.boolean(),
  email_opt_in: z.boolean(),
});

export type ClientFormValues = z.infer<typeof clientSchema>;
