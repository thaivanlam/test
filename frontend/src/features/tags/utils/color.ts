/**
 * The tag's color if the browser recognises it as a CSS color, else undefined.
 *
 * Color is free text on the API. React sets it as a single style property, so
 * it cannot inject other CSS, but an unrecognised value would silently render
 * nothing; checking first lets the caller fall back to a neutral swatch.
 */
export function safeCssColor(color: string | null): string | undefined {
  if (!color) return undefined;
  if (typeof CSS === "undefined" || !CSS.supports("color", color)) {
    return undefined;
  }
  return color;
}
