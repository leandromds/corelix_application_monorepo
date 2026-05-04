import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'

import { clientSchema, type ClientFormValues } from '../schemas/clientSchema'
import { useCreateClient } from '../hooks/useCreateClient'
import { useUpdateClient } from '../hooks/useUpdateClient'
import type { Client, UpdateClientPayload } from '../types'

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { Textarea } from '@/components/ui/textarea'

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ClientFormProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** When provided the form operates in edit mode. */
  client?: Client | null
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function buildDefaultValues(client: Client | null | undefined): ClientFormValues {
  if (!client) {
    return {
      full_name: '',
      phone: '',
      email: '',
      notes: '',
      whatsapp_opt_in: false,
      email_opt_in: false,
    }
  }
  return {
    full_name: client.full_name,
    phone: client.phone,
    // null → empty string so the controlled input stays consistent
    email: client.email ?? '',
    notes: client.notes ?? '',
    whatsapp_opt_in: client.whatsapp_opt_in,
    email_opt_in: client.email_opt_in,
  }
}

/**
 * PATCH semântico (ADR-024): builds only the fields that actually changed
 * compared to the server-side values.
 */
function computeDiff(original: Client, values: ClientFormValues): UpdateClientPayload {
  const diff: UpdateClientPayload = {}

  if (values.full_name !== original.full_name) {
    diff.full_name = values.full_name
  }
  if (values.phone !== original.phone) {
    diff.phone = values.phone
  }

  // Treat empty string as "no value" to match the server representation (null)
  const formEmail = values.email !== '' ? values.email : undefined
  const origEmail = original.email ?? undefined
  if (formEmail !== origEmail) {
    diff.email = formEmail
  }

  const formNotes = values.notes !== '' ? values.notes : undefined
  const origNotes = original.notes ?? undefined
  if (formNotes !== origNotes) {
    diff.notes = formNotes
  }

  if (values.whatsapp_opt_in !== original.whatsapp_opt_in) {
    diff.whatsapp_opt_in = values.whatsapp_opt_in
  }
  if (values.email_opt_in !== original.email_opt_in) {
    diff.email_opt_in = values.email_opt_in
  }

  return diff
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ClientForm({ open, onOpenChange, client }: ClientFormProps) {
  const isEditing = client != null

  const form = useForm<ClientFormValues>({
    resolver: zodResolver(clientSchema),
    defaultValues: buildDefaultValues(client),
  })

  // Re-populate whenever the target client changes (opening a different record)
  useEffect(() => {
    form.reset(buildDefaultValues(client))
  }, [client, form])

  const createMutation = useCreateClient()
  const updateMutation = useUpdateClient()
  const isPending = createMutation.isPending || updateMutation.isPending

  function handleSubmit(values: ClientFormValues): void {
    if (isEditing) {
      const diff = computeDiff(client, values)

      // Nothing changed — just close
      if (Object.keys(diff).length === 0) {
        onOpenChange(false)
        return
      }

      updateMutation.mutate(
        { id: client.id, payload: diff },
        { onSuccess: () => onOpenChange(false) },
      )
    } else {
      createMutation.mutate(
        {
          full_name: values.full_name,
          phone: values.phone,
          // Only include optional fields when they carry actual content
          ...(values.email !== '' && values.email != null && { email: values.email }),
          ...(values.notes !== '' && values.notes != null && { notes: values.notes }),
          whatsapp_opt_in: values.whatsapp_opt_in,
          email_opt_in: values.email_opt_in,
        },
        { onSuccess: () => onOpenChange(false) },
      )
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent style={{ maxWidth: 520 }}>
        <DialogHeader>
          <DialogTitle>{isEditing ? 'Editar Cliente' : 'Novo Cliente'}</DialogTitle>
          <DialogDescription>
            {isEditing
              ? 'Atualize os dados do cliente.'
              : 'Preencha os dados do novo cliente.'}
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(handleSubmit)}
            className="space-y-4"
          >
            {/* Nome completo */}
            <FormField
              control={form.control}
              name="full_name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Nome completo</FormLabel>
                  <FormControl>
                    <Input placeholder="Nome do cliente" {...field} />
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
                  <FormLabel>Telefone</FormLabel>
                  <FormControl>
                    <Input placeholder="+5511999999999" {...field} />
                  </FormControl>
                  <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                    Ex: +5511999999999
                  </p>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* E-mail */}
            <FormField
              control={form.control}
              name="email"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    E-mail{' '}
                    <span style={{ color: 'var(--text-muted)', fontWeight: 400, fontSize: 13 }}>
                      (opcional)
                    </span>
                  </FormLabel>
                  <FormControl>
                    <Input type="email" placeholder="email@exemplo.com" {...field} />
                  </FormControl>
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
                  <FormLabel>
                    Notas{' '}
                    <span style={{ color: 'var(--text-muted)', fontWeight: 400, fontSize: 13 }}>
                      (opcional)
                    </span>
                  </FormLabel>
                  <FormControl>
                    <Textarea
                      placeholder="Observações administrativas (não clínicas)"
                      rows={3}
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* WhatsApp opt-in */}
            <FormField
              control={form.control}
              name="whatsapp_opt_in"
              render={({ field }) => (
                <FormItem className="flex items-center gap-2 space-y-0">
                  <FormControl>
                    <Checkbox
                      checked={field.value}
                      onCheckedChange={(checked) => {
                        field.onChange(checked === true)
                      }}
                    />
                  </FormControl>
                  <Label style={{ fontWeight: 400, cursor: 'pointer' }}>
                    Autorizo comunicações via WhatsApp (LGPD)
                  </Label>
                </FormItem>
              )}
            />

            {/* E-mail opt-in */}
            <FormField
              control={form.control}
              name="email_opt_in"
              render={({ field }) => (
                <FormItem className="flex items-center gap-2 space-y-0">
                  <FormControl>
                    <Checkbox
                      checked={field.value}
                      onCheckedChange={(checked) => {
                        field.onChange(checked === true)
                      }}
                    />
                  </FormControl>
                  <Label style={{ fontWeight: 400, cursor: 'pointer' }}>
                    Autorizo comunicações por e-mail (LGPD)
                  </Label>
                </FormItem>
              )}
            />

            <DialogFooter>
              <Button
                type="button"
                variant="secondary"
                onClick={() => onOpenChange(false)}
                disabled={isPending}
              >
                Cancelar
              </Button>
              <Button type="submit" disabled={isPending}>
                {isPending ? 'Salvando...' : 'Salvar'}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
