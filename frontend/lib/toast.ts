import { toast as sonnerToast } from "sonner"

/** Thin wrapper so the rest of the app stays decoupled from sonner. */
export const toast = {
  success: (message: string, description?: string) =>
    sonnerToast.success(message, description ? { description } : undefined),
  error: (message: string, description?: string) =>
    sonnerToast.error(message, description ? { description } : undefined),
  info: (message: string, description?: string) =>
    sonnerToast(message, description ? { description } : undefined),
}
