import { X } from "lucide-react";
import type { TagSummary } from "../api/tags";
import { safeCssColor } from "../utils/color";

interface TagBadgeProps {
  tag: TagSummary;
  /** When given, the badge has a remove button with this accessible name. */
  removeLabel?: string;
  onRemove?: () => void;
  disabled?: boolean;
}

export function TagBadge({ tag, removeLabel, onRemove, disabled }: TagBadgeProps) {
  // The color is only a swatch; the name keeps the default text color, so it
  // stays readable whatever color the tag has.
  const color = safeCssColor(tag.color);

  return (
    <span className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs">
      <span
        aria-hidden="true"
        className="size-2 rounded-full bg-muted-foreground/40"
        style={color ? { backgroundColor: color } : undefined}
      />
      {tag.name}
      {onRemove && (
        <button
          type="button"
          aria-label={removeLabel}
          className="ml-0.5 rounded-full text-muted-foreground hover:text-foreground disabled:opacity-50"
          onClick={onRemove}
          disabled={disabled}
        >
          <X className="size-3" />
        </button>
      )}
    </span>
  );
}
