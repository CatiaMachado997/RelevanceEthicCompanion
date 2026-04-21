/**
 * Tiny natural-language date parser.
 *
 * Extracts a best-effort due-date from free text and returns:
 *   - `iso`:   ISO8601 date if one was found, else null
 *   - `title`: the input with the parsed date span removed
 *
 * Handles: "today", "tonight", "tomorrow", "next week", "this weekend",
 * weekday names ("monday", "next friday"), "in 3 days", "in 2 weeks",
 * and "by 2026-05-10" / "on may 10" / "may 10".
 *
 * Kept deliberately small — no external deps. Good enough for slash
 * creation commands; misses are fine (user can edit on the details page).
 */

const WEEKDAYS = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]
const MONTHS = [
  "january", "february", "march", "april", "may", "june",
  "july", "august", "september", "october", "november", "december",
]


function startOfDay(d: Date): Date {
  const c = new Date(d); c.setHours(0, 0, 0, 0); return c
}


function nextWeekday(from: Date, targetDow: number): Date {
  const d = startOfDay(from)
  const cur = d.getDay()
  const diff = ((targetDow - cur) + 7) % 7 || 7  // always future (at least +1 day)
  d.setDate(d.getDate() + diff)
  return d
}


export interface ParsedDate {
  iso: string | null
  title: string
}


export function parseNaturalDate(raw: string, now: Date = new Date()): ParsedDate {
  const text = raw.trim()
  if (!text) return { iso: null, title: text }

  // Helpers
  const today = startOfDay(now)
  const tomorrow = new Date(today); tomorrow.setDate(today.getDate() + 1)

  // Try each pattern in order; first match wins. Each returns a [regex, factory].
  const patterns: Array<[RegExp, (m: RegExpMatchArray) => Date | null]> = [
    // "today" / "tonight"
    [/\b(today|tonight)\b/i, () => today],
    // "tomorrow"
    [/\btomorrow\b/i, () => tomorrow],
    // "this weekend" — Saturday of the current or upcoming week
    [/\bthis weekend\b/i, () => nextWeekday(now, 6)],
    // "next week" — upcoming Monday
    [/\bnext week\b/i, () => nextWeekday(now, 1)],
    // "next <weekday>" or "<weekday>"
    [/\b(next\s+)?(sunday|monday|tuesday|wednesday|thursday|friday|saturday)\b/i, (m) => {
      const dow = WEEKDAYS.indexOf(m[2].toLowerCase())
      return nextWeekday(now, dow)
    }],
    // "in N days" / "in N weeks"
    [/\bin\s+(\d+)\s+(day|days|week|weeks)\b/i, (m) => {
      const n = parseInt(m[1], 10)
      const d = new Date(today)
      d.setDate(today.getDate() + (m[2].startsWith('week') ? n * 7 : n))
      return d
    }],
    // ISO "2026-05-10" (optionally prefixed with "by" / "on")
    [/\b(?:by|on)?\s*(\d{4}-\d{2}-\d{2})\b/i, (m) => {
      const d = new Date(m[1] + "T00:00:00")
      return isNaN(d.getTime()) ? null : d
    }],
    // "may 10", "by may 10", "on may 10"
    [/\b(?:by|on)?\s*(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})\b/i, (m) => {
      const month = MONTHS.indexOf(m[1].toLowerCase())
      const day = parseInt(m[2], 10)
      if (month < 0 || day < 1 || day > 31) return null
      const year = now.getFullYear()
      let d = new Date(year, month, day)
      if (d < today) d = new Date(year + 1, month, day)  // roll forward if past
      return d
    }],
  ]

  for (const [re, factory] of patterns) {
    const match = text.match(re)
    if (!match) continue
    const d = factory(match)
    if (!d || isNaN(d.getTime())) continue
    // Remove the matched span from the title, tidy whitespace.
    const title = (text.slice(0, match.index!) + text.slice(match.index! + match[0].length))
      .replace(/\s+/g, " ")
      .trim()
    return { iso: d.toISOString().slice(0, 10), title }  // YYYY-MM-DD
  }

  return { iso: null, title: text }
}
