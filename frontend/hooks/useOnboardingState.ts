'use client'

import { useQuery } from '@tanstack/react-query'
import api, { type OnboardingState } from '@/lib/api'

/**
 * Read live onboarding state for the current user.
 *
 * Returned shape mirrors the backend `/api/onboarding/state` response —
 * `onboarded_at` is the source of truth for whether the user has completed
 * (or explicitly skipped) the wizard, and the three has_* flags drive the
 * sidebar nudge ("2 of 3 done").
 *
 * The wizard's redirect-guard reads this; the sidebar's "finish setup" tile
 * also reads this. Sharing one query key (`onboarding-state`) lets us
 * invalidate from a single place when the wizard saves a step.
 */
export function useOnboardingState() {
  return useQuery<OnboardingState>({
    queryKey: ['onboarding-state'],
    queryFn: () => api.onboarding.state(),
    // Refetch on window focus so a user who completed step 1 in another tab
    // sees the nudge update without a hard reload.
    staleTime: 30_000,
  })
}
