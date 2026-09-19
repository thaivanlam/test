import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { MAX_PAGE_SIZE } from "../api/queryKeys";

const PAGE_SIZE_OPTIONS = [10, 20, 50, MAX_PAGE_SIZE];

interface TodoPaginationProps {
  page: number;
  pages: number;
  pageSize: number;
  disabled: boolean;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
}

export function TodoPagination({
  page,
  pages,
  pageSize,
  disabled,
  onPageChange,
  onPageSizeChange,
}: TodoPaginationProps) {
  return (
    <nav
      aria-label="Pagination"
      className="flex flex-wrap items-center justify-between gap-2"
    >
      <div className="flex items-center gap-2">
        <Label htmlFor="page-size">Per page</Label>
        <select
          id="page-size"
          className="h-8 rounded-md border border-input bg-transparent px-2 text-sm"
          value={pageSize}
          disabled={disabled}
          onChange={(event) => onPageSizeChange(Number(event.target.value))}
        >
          {PAGE_SIZE_OPTIONS.map((size) => (
            <option key={size} value={size}>
              {size}
            </option>
          ))}
        </select>
      </div>
      <div className="flex items-center gap-2">
        <Button
          size="sm"
          variant="outline"
          disabled={disabled || page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          Previous
        </Button>
        <span className="text-sm text-muted-foreground">
          Page {pages === 0 ? 0 : page} of {pages}
        </span>
        <Button
          size="sm"
          variant="outline"
          disabled={disabled || page >= pages}
          onClick={() => onPageChange(page + 1)}
        >
          Next
        </Button>
      </div>
    </nav>
  );
}
