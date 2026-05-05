/**
 * WhatsApp feature types — mirrors backend schemas.py
 *
 * ConversationResponse → Conversation
 * MessageResponse      → Message
 * ConversationWithMessagesResponse → ConversationWithMessages
 * HandoffResponse      → HandoffResult
 */

export type ConversationStatus = 'active' | 'resolved' | 'waiting_professional'
export type ConversationMode = 'ai' | 'handoff'
export type MessageDirection = 'inbound' | 'outbound'
export type SenderType = 'client' | 'ai' | 'professional'

export interface Conversation {
  id: string              // UUID
  client_phone: string
  client_id: string | null
  status: ConversationStatus
  mode: ConversationMode
  started_at: string      // ISO 8601
  last_message_at: string // ISO 8601
  ended_at: string | null
}

export interface Message {
  id: string              // UUID
  direction: MessageDirection
  sender_type: SenderType
  content: string
  sent_at: string         // ISO 8601
}

export interface ConversationWithMessages {
  conversation: Conversation
  messages: Message[]
}

export interface HandoffResult {
  id: string
  mode: string
  status: string
}
