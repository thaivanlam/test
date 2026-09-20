import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { Tag } from "@/features/tags/api/tags";
import {
  hasActiveFilters,
  type TodoFilters,
  type TodoStatusFilter,
} from "../api/queryKeys";

const KEYWORD_DEBOUNCE_MS = 300;

// Same look as the Input component, for the native <select>s.
const selectClassName =
  "h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 dark:bg-input/30";

interface TodoFilterBarProps {
  filters: TodoFilters;
  tags: Tag[];
  dateRangeInvalid: boolean;
  onChange: (changes: Partial<TodoFilters>) => void;
  onClear: () => void;
}

/**
 * Remount it (change its key) to reset the keyword box: the box keeps its own
 * text so that typing is not held up by the debounce.
 */
export function TodoFilterBar({
  filters,
  tags,
  dateRangeInvalid,
  onChange,
  onClear,
}: TodoFilterBarProps) {
  const [keyword, setKeyword] = useState(filters.keyword);

  // Only the settled text becomes a filter, so typing a word is one request
  // rather than one per keystroke.
  useEffect(() => {
    if (keyword === filters.keyword) return;
    const timer = setTimeout(
      () => onChange({ keyword }),
      KEYWORD_DEBOUNCE_MS
    );
    return () => clearTimeout(timer);
  }, [keyword, filters.keyword, onChange]);

  return (
    <div className="space-y-3" role="search" aria-label="Filter todos">
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1 sm:col-span-2">
          <Label htmlFor="filter-keyword">Search</Label>
          <Input
            id="filter-keyword"
            type="search"
            placeholder="Title or description"
            maxLength={200}
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="filter-status">Status</Label>
          <select
            id="filter-status"
            className={selectClassName}
            value={filters.status}
            onChange={(event) =>
              onChange({ status: event.target.value as TodoStatusFilter })
            }
          >
            <option value="all">All</option>
            <option value="active">Active</option>
            <option value="completed">Completed</option>
          </select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="filter-tag">Tag</Label>
          <select
            id="filter-tag"
            className={selectClassName}
            value={filters.tagId ?? ""}
            onChange={(event) => onChange({ tagId: event.target.value || null })}
          >
            <option value="">All tags</option>
            {tags.map((tag) => (
              <option key={tag.id} value={tag.id}>
                {tag.name}
              </option>
            ))}
          </select>
        </div>
        {/* type="date" yields YYYY-MM-DD as the user picked it; it is sent
            as is, never through a Date, so no time zone can shift the day. */}
        <div className="space-y-1">
          <Label htmlFor="filter-date-from">From</Label>
          <Input
            id="filter-date-from"
            type="date"
            value={filters.dateFrom ?? ""}
            max={filters.dateTo ?? undefined}
            aria-invalid={dateRangeInvalid}
            onChange={(event) =>
              onChange({ dateFrom: event.target.value || null })
            }
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="filter-date-to">To</Label>
          <Input
            id="filter-date-to"
            type="date"
            value={filters.dateTo ?? ""}
            min={filters.dateFrom ?? undefined}
            aria-invalid={dateRangeInvalid}
            onChange={(event) => onChange({ dateTo: event.target.value || null })}
          />
        </div>
      </div>
      <div className="flex items-center justify-between gap-2">
        {dateRangeInvalid ? (
          <p role="alert" className="text-sm text-destructive">
            "From" must be on or before "To".
          </p>
        ) : (
          <span />
        )}
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={onClear}
          disabled={!hasActiveFilters(filters) && keyword === ""}
        >
          Clear filters
        </Button>
      </div>
    </div>
  );
}
