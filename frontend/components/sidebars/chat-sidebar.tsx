"use client"

import {
  SecondarySidebar,
  SecondarySidebarSection,
  SecondarySidebarPromo,
} from "@/components/secondary-sidebar"
import { Button } from "@/components/ui/button"
import { Plus, MessageSquare, Clock, Sparkles } from "lucide-react"

interface ChatSidebarProps {
  onNewChat?: () => void
}

export function ChatSidebar({ onNewChat }: ChatSidebarProps) {
  return (
    <SecondarySidebar
      title="Conversations"
      action={
        <Button
          size="sm"
          className="rounded-full bg-[#171717] hover:bg-[#4338CA] h-8 w-8 p-0"
          onClick={onNewChat}
        >
          <Plus className="h-4 w-4" />
        </Button>
      }
      showSearch
      searchPlaceholder="Search conversations..."
      footer={
        <SecondarySidebarPromo
          title="AI with Ethics"
          description="Every response is filtered through our Ethical Safeguard Layer."
        />
      }
    >
      <SecondarySidebarSection title="Recent">
        <div className="space-y-1">
          {/* Example recent chats - in real implementation, this would be dynamic */}
          <button className="w-full flex items-start gap-3 p-3 rounded-lg hover:bg-[#F5F5F5] transition-colors text-left">
            <div className="w-8 h-8 rounded-lg bg-[#171717]/10 flex items-center justify-center shrink-0">
              <MessageSquare className="h-4 w-4 text-[#171717]" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-[#171717] truncate">Current Session</p>
              <p className="text-xs text-[#171717] truncate">Active conversation</p>
            </div>
          </button>
        </div>
      </SecondarySidebarSection>

      <SecondarySidebarSection title="Suggestions">
        <div className="space-y-2">
          <div className="p-3 rounded-lg bg-[#FAFAFA] border border-[#E5E5E5]">
            <div className="flex items-center gap-2 mb-2">
              <Sparkles className="h-4 w-4 text-[#171717]" />
              <span className="text-xs font-medium text-[#171717]">Try asking</span>
            </div>
            <p className="text-sm text-[#525252]">"Help me prioritize my goals for this week"</p>
          </div>
          <div className="p-3 rounded-lg bg-[#FAFAFA] border border-[#E5E5E5]">
            <div className="flex items-center gap-2 mb-2">
              <Clock className="h-4 w-4 text-[#171717]" />
              <span className="text-xs font-medium text-[#171717]">Quick prompt</span>
            </div>
            <p className="text-sm text-[#525252]">"What should I focus on today?"</p>
          </div>
        </div>
      </SecondarySidebarSection>
    </SecondarySidebar>
  )
}
