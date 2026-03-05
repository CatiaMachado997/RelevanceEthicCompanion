"use client"

import * as React from "react"
import { Globe } from "lucide-react"
import { cn } from "@/lib/utils"

export interface Source {
  id: string
  title: string
  url: string
  domain: string
  favicon?: string
}

interface SourceCardProps {
  source: Source
  className?: string
}

export function SourceCard({ source, className }: SourceCardProps) {
  return (
    <button
      onClick={() => window.open(source.url, "_blank")}
      className={cn(
        "flex flex-col gap-4 rounded-lg border border-[#E5E5E5] bg-[#FAFAFA] p-3 text-left transition-all hover:border-[#171717]/50 hover:shadow-md",
        className
      )}
    >
      <p className="line-clamp-2 text-xs font-medium leading-4 text-[#404040]">
        {source.title}
      </p>
      <div className="flex items-center gap-1">
        <Globe className="h-4 w-4 text-[#A3A3A3]" />
        <span className="truncate text-[10px] font-medium text-[#525252]">
          {source.domain}
        </span>
      </div>
    </button>
  )
}

interface SourcesGridProps {
  sources: Source[]
  className?: string
}

export function SourcesGrid({ sources, className }: SourcesGridProps) {
  const displayedSources = sources.slice(0, 2)
  const remainingCount = sources.length - 2

  return (
    <div className={cn("flex items-center gap-2", className)}>
      {displayedSources.map((source) => (
        <SourceCard key={source.id} source={source} className="w-[157px] h-[88px]" />
      ))}
      {remainingCount > 0 && (
        <button
          onClick={() => console.log("Show all sources")}
          className="flex h-[88px] w-[170px] flex-col gap-4 rounded-lg border border-[#E5E5E5] bg-[#FAFAFA] p-3 text-left transition-all hover:border-[#171717]/50 hover:shadow-md"
        >
          <p className="line-clamp-2 text-xs font-medium leading-4 text-[#404040]">
            View {remainingCount}+ more external sources
          </p>
          <div className="flex items-center gap-1">
            <Globe className="h-4 w-4 text-[#A3A3A3]" />
            <span className="truncate text-[10px] font-medium text-[#525252]">
              various sources
            </span>
          </div>
        </button>
      )}
    </div>
  )
}
