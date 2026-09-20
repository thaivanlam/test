import { z } from "zod";

// Mirrors the API's limits (name 1-50 after trimming, color up to 20) so the
// user sees the problem before submitting. The API stays the authority:
// uniqueness, for one, is only known there and comes back as a 409.
export const tagSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, "Name is required")
    .max(50, "Name must be at most 50 characters"),
  color: z
    .string()
    .trim()
    .max(20, "Color must be at most 20 characters")
    .nullable()
    .optional(),
});

export type TagFormData = z.infer<typeof tagSchema>;

/** Form values to request body: an empty color means no color. */
export function toTagPayload(data: TagFormData): {
  name: string;
  color: string | null;
} {
  return { name: data.name, color: data.color ? data.color : null };
}
