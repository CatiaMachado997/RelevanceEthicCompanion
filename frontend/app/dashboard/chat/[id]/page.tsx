'use client'

import { use } from 'react'
import ChatPage from '../page'

export default function ConversationPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  return <ChatPage conversationId={id} />
}
