import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";

interface BulkActionsBarProps {
  selectedCount: number;
  pageCount: number;
  pending: boolean;
  error: string | null;
  onSelectAll: (selected: boolean) => void;
  onClear: () => void;
  onApply: (completed: boolean) => void;
}

export function BulkActionsBar({
  selectedCount,
  pageCount,
  pending,
  error,
  onSelectAll,
  onClear,
  onApply,
}: BulkActionsBarProps) {
  const allSelected = pageCount > 0 && selectedCount === pageCount;
  const noneSelected = selectedCount === 0;

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2 rounded-lg border bg-muted/40 p-2">
        <Checkbox
          aria-label="Select all todos on this page"
          checked={allSelected ? true : noneSelected ? false : "indeterminate"}
          disabled={pageCount === 0 || pending}
          onCheckedChange={(checked) => onSelectAll(checked === true)}
        />
        <span className="text-sm text-muted-foreground" aria-live="polite">
          {selectedCount} selected
        </span>
        <div className="ml-auto flex flex-wrap gap-2">
          <Button
            size="sm"
            variant="outline"
            disabled={noneSelected || pending}
            onClick={() => onApply(true)}
          >
            Mark completed
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={noneSelected || pending}
            onClick={() => onApply(false)}
          >
            Mark active
          </Button>
          <Button
            size="sm"
            variant="ghost"
            disabled={noneSelected || pending}
            onClick={onClear}
          >
            Clear selection
          </Button>
        </div>
      </div>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
