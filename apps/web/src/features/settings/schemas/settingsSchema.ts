import { z } from 'zod'

/**
 * Zod schema for the Settings / profile form.
 *
 * Backend constraints (UpdateProfileRequest):
 *   full_name:        min 2, max 200
 *   specialty:        nullable, min 2, max 100
 *   bio:              nullable, no length constraint
 *   phone:            nullable, min 10, max 20
 *   session_duration: int, 15 ≤ x ≤ 480
 *   session_price:    Decimal, ≥ 0
 *
 * Optional text fields use z.union([z.literal(''), z.string().min(2)]) so
 * that an empty string (= user left the field blank = keep unchanged) is
 * valid, but a non-empty string that is too short still surfaces an error.
 *
 * Gotcha: z.coerce.number() makes the field type `unknown` in the inferred
 * TFieldValues, which breaks useForm<TFieldValues>.  Fix in the component:
 *   zodResolver(settingsSchema) as Resolver<SettingsFormValues>
 */

export const settingsSchema = z.object({
  full_name: z
    .string()
    .min(2, 'Nome deve ter pelo menos 2 caracteres')
    .max(200, 'Nome muito longo'),

  specialty: z.union([
    z.literal(''),
    z.string().min(2, 'Especialidade deve ter pelo menos 2 caracteres').max(100),
  ]),

  bio: z.string().max(500, 'Bio muito longa'),

  phone: z.union([
    z.literal(''),
    z
      .string()
      .min(10, 'Telefone deve ter pelo menos 10 caracteres')
      .max(20, 'Telefone muito longo'),
  ]),

  session_duration: z.coerce
    .number({ invalid_type_error: 'Informe a duração em minutos' })
    .int('Deve ser um número inteiro')
    .min(15, 'Duração mínima: 15 minutos')
    .max(480, 'Duração máxima: 480 minutos'),

  session_price: z.coerce
    .number({ invalid_type_error: 'Informe o preço' })
    .min(0, 'Preço não pode ser negativo'),
})

export type SettingsFormValues = z.infer<typeof settingsSchema>
