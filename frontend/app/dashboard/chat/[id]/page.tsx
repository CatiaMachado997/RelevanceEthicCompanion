'use client'

import { use } from 'react'
import ChatPageContent from '../ChatPageContent'

export default function ConversationPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  return <ChatPageContent conversationId={id} />
}
