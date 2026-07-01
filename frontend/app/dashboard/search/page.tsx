"use client"

import { useState, useEffect } from "react"
import { Search, X, MessageSquare, Clock, Zap, Calendar, FileText } from "lucide-react"
import { searchApi, SearchResult } from "@/lib/api"
import { PageHeader } from "@/components/ui/page-header"
import { FilterChips } from "@/components/ui/filter-chips"

type FilterType = "all" | "memory" | "event" | "document"

export default function SearchPage() {
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<SearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const [recentSearches, setRecentSearches] = useState<string[]>([])
  const [filterType, setFilterType] = useState<FilterType>("all")
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const saved = localStorage.getItem("recentSearches")
    if (saved) {
      try {
        setRecentSearches(JSON.parse(saved))
      } catch {}
    }
  }, [])

  const saveRecentSearch = (searchQuery: string) => {
    if (!searchQuery.trim()) return
    const updated = [
      searchQuery,
      ...recentSearches.filter((s) => s !== searchQuery),
    ].slice(0, 5)
    setRecentSearches(updated)
    localStorage.setItem("recentSearches", JSON.stringify(updated))
  }

  const performSearch = async (searchQuery: string) => {
    if (!searchQuery.trim()) {
      setResults([])
      return
    }
    setLoading(true)
    setError(null)
    try {
      const raw = await searchApi.query(searchQuery, 20)
      const filtered =
        filterType === "all" ? raw : raw.filter((r) => r.type === filterType)
      setResults(filtered)
    } catch (err) {
      console.error("Search error:", err)
      setError("Search unavailable — Weaviate may not be running locally.")
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = async (searchQuery: string) => {
    setQuery(searchQuery)
    saveRecentSearch(searchQuery)
    await performSearch(searchQuery)
  }

  const handleClear = () => {
    setQuery("")
    setResults([])
    setError(null)
  }

  const handleRecentClick = (search: string) => {
    setQuery(search)
    performSearch(search)
  }

  const getIcon = (type: string) => {
    switch (type) {
      case "memory":
        return <MessageSquare className="h-4 w-4" />
      case "event":
        return <Calendar className="h-4 w-4" />
      case "document":
        return <FileText className="h-4 w-4" />
      default:
        return <Zap className="h-4 w-4" />
    }
  }

  const getTypeLabel = (type: string) => {
    switch (type) {
      case "memory": return "Memory"
      case "event": return "Event"
      case "document": return "Document"
      default: return type
    }
  }

  const filteredResults =
    filterType === "all" ? results : results.filter((r) => r.type === filterType)

  return (
    <div className="space-y-4 md:space-y-6">
      <PageHeader title="Search" subtitle="Semantic search across your conversation memories" />

        {/* Search Input */}
        <div className="relative">
          <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--ec-text-subtle)]" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleSearch(query)
            }}
            placeholder="Search your memories..."
            className="h-11 w-full rounded-xl border border-[var(--ec-card-border)] bg-[var(--ec-card-bg)] pl-10 pr-10 text-sm text-[var(--ec-text)] placeholder:text-[var(--ec-text-subtle)] focus:border-[var(--ec-text)] focus:outline-none focus:ring-1 focus:ring-[var(--ec-text)]"
          />
          {query && (
            <button
              onClick={handleClear}
              aria-label="Clear search"
              className="absolute right-3 top-1/2 -translate-y-1/2 rounded-full p-0.5 hover:bg-[var(--ec-page-bg)]"
            >
              <X className="h-4 w-4 text-[var(--ec-text-subtle)]" />
            </button>
          )}
        </div>

        {/* Filter Chips */}
        <FilterChips<FilterType>
          chips={[
            { value: null, label: 'All' },
            { value: 'memory', label: 'Memory' },
            { value: 'event', label: 'Event' },
            { value: 'document', label: 'Document' },
          ]}
          selected={filterType === 'all' ? null : filterType}
          onChange={(f) => {
            const v = (f ?? 'all') as FilterType
            setFilterType(v)
            if (query) performSearch(query)
          }}
        />

        {/* Error state */}
        {error && (
          <div className="rounded-xl border border-[rgba(239,68,68,0.2)] bg-[rgba(239,68,68,0.05)] px-4 py-3 text-sm text-red-600">
            {error}
          </div>
        )}

        {/* Results */}
        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-20 animate-pulse rounded-2xl border border-[var(--ec-card-border)] bg-[var(--ec-page-bg)]"
              />
            ))}
          </div>
        ) : filteredResults.length > 0 ? (
          <div className="space-y-3">
            <p className="text-xs font-medium uppercase tracking-wide text-[var(--ec-text-subtle)]">
              {filteredResults.length} result{filteredResults.length !== 1 ? "s" : ""}
            </p>
            <div className="space-y-2">
              {filteredResults.map((result) => (
                <div
                  key={result.id}
                  className="rounded-2xl border border-[var(--ec-card-border)] bg-[var(--ec-card-bg)] p-4 shadow-[var(--ec-card-shadow)] transition-shadow hover:shadow-[0_4px_12px_rgba(0,0,0,0.10)]"
                >
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5 text-[var(--ec-text-muted)]">
                      {getIcon(result.type)}
                    </div>
                    <div className="flex-1 space-y-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="inline-flex items-center rounded-full bg-[var(--ec-page-bg)] px-2.5 py-0.5 text-xs font-medium text-[var(--ec-text)]">
                          {getTypeLabel(result.type)}
                        </span>
                        <span className="text-xs text-[var(--ec-text-subtle)]">
                          {Math.round(result.score * 100)}% match
                        </span>
                      </div>
                      <p className="text-sm text-[var(--ec-text)] line-clamp-3">
                        {result.content}
                      </p>
                      {typeof result.metadata?.timestamp === 'string' && (
                        <div className="flex items-center gap-1 text-xs text-[var(--ec-text-subtle)]">
                          <Clock className="h-3 w-3" />
                          {new Date(result.metadata.timestamp).toLocaleDateString()}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : query && !loading ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <Search className="mb-3 h-8 w-8 text-[var(--ec-text-subtle)]" />
            <p className="text-sm font-medium text-[var(--ec-text)]">No results found</p>
            <p className="text-xs text-[var(--ec-text-subtle)]">
              Try a different query — memories are stored after chat conversations
            </p>
          </div>
        ) : null}

        {/* Recent Searches */}
        {!query && recentSearches.length > 0 && (
          <div className="space-y-3">
            <p className="text-xs font-medium uppercase tracking-wide text-[var(--ec-text-subtle)]">
              Recent Searches
            </p>
            <div className="space-y-2">
              {recentSearches.map((search, index) => (
                <button
                  key={index}
                  onClick={() => handleRecentClick(search)}
                  className="flex w-full items-center gap-3 rounded-2xl border border-[var(--ec-card-border)] bg-[var(--ec-card-bg)] p-3 text-left shadow-[var(--ec-card-shadow)] transition-shadow hover:shadow-[0_4px_12px_rgba(0,0,0,0.10)]"
                >
                  <Clock className="h-4 w-4 text-[var(--ec-text-subtle)]" />
                  <span className="text-sm text-[var(--ec-text)]">{search}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Empty State */}
        {!query && recentSearches.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="mb-4 rounded-full bg-[var(--ec-page-bg)] p-4">
              <Search className="h-8 w-8 text-[var(--ec-text-subtle)]" />
            </div>
            <h3 className="mb-1 text-sm font-medium text-[var(--ec-text)]">
              Semantic search
            </h3>
            <p className="text-xs text-[var(--ec-text-muted)]">
              Search your AI conversation memories by meaning, not just keywords
            </p>
          </div>
        )}
    </div>
  )
}
