import { parseNaturalDate } from '@/components/chat/parse-natural-date'

// Fixed reference date: Wednesday, 2026-04-22
// DOW: 0=Sun 1=Mon 2=Tue 3=Wed 4=Thu 5=Fri 6=Sat
// Wed = 3, so:
//   nextWeekday(ref, 1 Mon) = +5 days -> 2026-04-27
//   nextWeekday(ref, 6 Sat) = +3 days -> 2026-04-25
//   nextWeekday(ref, 3 Wed) = +7 days -> 2026-04-29  (same weekday: always future)
//   nextWeekday(ref, 5 Fri) = +2 days -> 2026-04-24
const REF = new Date('2026-04-22T10:00:00')

describe('parseNaturalDate', () => {
  // ── edge cases ────────────────────────────────────────────────────────────

  it('returns null iso and empty title for empty string', () => {
    expect(parseNaturalDate('', REF)).toEqual({ iso: null, title: '' })
  })

  it('returns null iso and trimmed title for whitespace-only input', () => {
    expect(parseNaturalDate('   ', REF)).toEqual({ iso: null, title: '' })
  })

  it('returns null iso when no date pattern is found', () => {
    const result = parseNaturalDate('finish the report', REF)
    expect(result.iso).toBeNull()
    expect(result.title).toBe('finish the report')
  })

  // ── today / tonight ───────────────────────────────────────────────────────

  it('parses "today" → today\'s date', () => {
    expect(parseNaturalDate('today', REF).iso).toBe('2026-04-22')
  })

  it('parses "tonight" → today\'s date', () => {
    expect(parseNaturalDate('tonight', REF).iso).toBe('2026-04-22')
  })

  // ── tomorrow ─────────────────────────────────────────────────────────────

  it('parses "tomorrow" → next day', () => {
    expect(parseNaturalDate('tomorrow', REF).iso).toBe('2026-04-23')
  })

  // ── this weekend / next week ──────────────────────────────────────────────

  it('parses "this weekend" → upcoming Saturday', () => {
    // From Wed 2026-04-22, next Saturday is 2026-04-25
    expect(parseNaturalDate('this weekend', REF).iso).toBe('2026-04-25')
  })

  it('parses "next week" → upcoming Monday', () => {
    // From Wed 2026-04-22, next Monday is 2026-04-27
    expect(parseNaturalDate('next week', REF).iso).toBe('2026-04-27')
  })

  // ── weekday names ─────────────────────────────────────────────────────────

  it('parses a bare weekday name → always at least 1 day in future', () => {
    // "wednesday" on a Wednesday → jumps +7 days, not today
    expect(parseNaturalDate('wednesday', REF).iso).toBe('2026-04-29')
  })

  it('parses "friday" → next Friday', () => {
    // From Wed 2026-04-22, next Friday is 2026-04-24
    expect(parseNaturalDate('friday', REF).iso).toBe('2026-04-24')
  })

  it('parses "next friday" → next Friday', () => {
    expect(parseNaturalDate('next friday', REF).iso).toBe('2026-04-24')
  })

  // ── relative durations ────────────────────────────────────────────────────

  it('parses "in 3 days"', () => {
    expect(parseNaturalDate('in 3 days', REF).iso).toBe('2026-04-25')
  })

  it('parses "in 2 weeks"', () => {
    expect(parseNaturalDate('in 2 weeks', REF).iso).toBe('2026-05-06')
  })

  // ── ISO date ──────────────────────────────────────────────────────────────

  it('parses bare ISO date "2026-05-10"', () => {
    expect(parseNaturalDate('2026-05-10', REF).iso).toBe('2026-05-10')
  })

  it('parses "by 2026-05-10"', () => {
    expect(parseNaturalDate('by 2026-05-10', REF).iso).toBe('2026-05-10')
  })

  // ── month + day ───────────────────────────────────────────────────────────

  it('parses "may 10" (future month) → current year', () => {
    expect(parseNaturalDate('may 10', REF).iso).toBe('2026-05-10')
  })

  it('parses "on may 10"', () => {
    expect(parseNaturalDate('on may 10', REF).iso).toBe('2026-05-10')
  })

  it('parses "january 5" in April → rolls to next year', () => {
    // Jan 5 has already passed in 2026, so should roll to 2027
    expect(parseNaturalDate('january 5', REF).iso).toBe('2027-01-05')
  })

  // ── title stripping ───────────────────────────────────────────────────────

  it('strips the date token from the title', () => {
    const result = parseNaturalDate('submit report by 2026-05-10', REF)
    expect(result.iso).toBe('2026-05-10')
    expect(result.title).toBe('submit report')
  })

  it('strips "tomorrow" from the middle of text', () => {
    const result = parseNaturalDate('call dentist tomorrow morning', REF)
    expect(result.iso).toBe('2026-04-23')
    expect(result.title).toBe('call dentist morning')
  })

  it('strips "in N days" and collapses extra whitespace', () => {
    const result = parseNaturalDate('review PR in 3 days', REF)
    expect(result.iso).toBe('2026-04-25')
    expect(result.title).toBe('review PR')
  })
})
