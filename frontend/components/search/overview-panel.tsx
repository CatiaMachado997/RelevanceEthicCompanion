"use client"

import * as React from "react"
import { Play, Image as ImageIcon, Plane, GraduationCap, Plus, Info } from "lucide-react"
import { cn } from "@/lib/utils"

interface ActionItem {
  id: string
  icon: React.ElementType
  label: string
}

const defaultActions: ActionItem[] = [
  { id: "videos", icon: Play, label: "Search Videos" },
  { id: "image", icon: ImageIcon, label: "Generate Image" },
  { id: "travel", icon: Plane, label: "Book Tickets" },
  { id: "learn", icon: GraduationCap, label: "Learn & Educate" },
]

interface OverviewImage {
  id: string
  src: string
  alt: string
}

interface OverviewPanelProps {
  images?: OverviewImage[]
  actions?: ActionItem[]
  onClose?: () => void
  className?: string
}

export function OverviewPanel({
  images = [],
  actions = defaultActions,
  onClose,
  className,
}: OverviewPanelProps) {
  return (
    <div className={cn("flex h-full w-[286px] flex-col border-r border-[#E5E5E5] bg-white", className)}>
      {/* Images Section */}
      <div className="border-b border-[#E5E5E5]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-3">
          <div className="flex items-center gap-2">
            <Info className="h-6 w-6 text-[#525252]" />
            <span className="text-base font-semibold text-[#404040]">Overview</span>
          </div>
          <button className="text-sm font-bold text-[#171717] hover:text-[#4338CA]">
            See all
          </button>
        </div>

        {/* Image Grid */}
        <div className="flex flex-col gap-2 px-6 pb-4">
          {/* Large Image */}
          <div className="h-60 w-full overflow-hidden rounded-lg border border-[#E5E5E5] bg-[#F5F5F5]">
            {images[0] ? (
              <img
                src={images[0].src}
                alt={images[0].alt}
                className="h-full w-full object-cover"
              />
            ) : (
              <div className="flex h-full items-center justify-center">
                <ImageIcon className="h-12 w-12 text-[#A3A3A3]" />
              </div>
            )}
          </div>

          {/* Small Images Row */}
          <div className="flex gap-2">
            {[1, 2].map((i) => (
              <div
                key={i}
                className="h-24 flex-1 overflow-hidden rounded-lg border border-[#E5E5E5] bg-[#F5F5F5]"
              >
                {images[i] ? (
                  <img
                    src={images[i].src}
                    alt={images[i].alt}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <div className="flex h-full items-center justify-center">
                    <ImageIcon className="h-6 w-6 text-[#A3A3A3]" />
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Another Small Images Row */}
          <div className="flex gap-2">
            {[3, 4].map((i) => (
              <div
                key={i}
                className="h-24 flex-1 overflow-hidden rounded-lg border border-[#E5E5E5] bg-[#F5F5F5]"
              >
                {images[i] ? (
                  <img
                    src={images[i].src}
                    alt={images[i].alt}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <div className="flex h-full items-center justify-center">
                    <ImageIcon className="h-6 w-6 text-[#A3A3A3]" />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Action Items */}
      <div className="flex-1">
        {actions.map((action) => (
          <button
            key={action.id}
            onClick={() => console.log(`Action: ${action.label}`)}
            className="flex w-full items-center gap-4 border-b border-[#E5E5E5] px-6 py-3 transition-colors hover:bg-[#FAFAFA]"
          >
            <action.icon className="h-6 w-6 text-[#525252]" />
            <span className="flex-1 text-left text-base font-semibold text-[#404040]">
              {action.label}
            </span>
            <Plus className="h-5 w-5 text-[#A3A3A3]" />
          </button>
        ))}
      </div>
    </div>
  )
}
