import { isAxiosError } from "axios";

/** The API's own message where it has one (409 duplicate, 404), else fallback. */
export function apiErrorMessage(error: unknown, fallback: string): string {
  if (isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
  }
  return fallback;
}
