import { useCallback, useState } from "react";
import { isAxiosError } from "axios";
import { Plus, LogOut, Tags } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { apiErrorMessage } from "@/lib/apiError";
import { useTags } from "@/features/tags/api/tags";
import { TagManager } from "@/features/tags/components/TagManager";
import { useBulkUpdateStatus, useTodos, type Todo } from "../api/todos";
import {
  DEFAULT_PAGE_SIZE,
  DEFAULT_TODO_FILTERS,
  hasActiveFilters,
  normalizeTodoListQuery,
  type TodoFilters,
} from "../api/queryKeys";
import { TodoList } from "./TodoList";
import { TodoForm } from "./TodoForm";
import { TodoFilterBar } from "./TodoFilterBar";
import { TodoPagination } from "./TodoPagination";
import { BulkActionsBar } from "./BulkActionsBar";
import { useAuth } from "@/features/auth/hooks/useAuth";

export function TodoPage() {
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [showTagManager, setShowTagManager] = useState(false);
  const [filters, setFilters] = useState<TodoFilters>(DEFAULT_TODO_FILTERS);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [selectedIds, setSelectedIds] = useState<ReadonlySet<string>>(new Set());
  const [bulkError, setBulkError] = useState<string | null>(null);
  // Changing it remounts the filter bar, which resets its keyword box.
  const [filterBarKey, setFilterBarKey] = useState(0);
  const { user, logout } = useAuth();

  const dateRangeInvalid =
    !!filters.dateFrom && !!filters.dateTo && filters.dateFrom > filters.dateTo;
  const query = normalizeTodoListQuery({ page, pageSize, filters });
  // A reversed range is a 422 from the API; say so here instead of asking.
  const { data, isLoading, error, isPlaceholderData } = useTodos(query, {
    enabled: !dateRangeInvalid,
  });
  const { data: tags = [] } = useTags();
  const bulkUpdate = useBulkUpdateStatus();

  // A selection only makes sense for the rows it was made on.
  const resetSelection = () => {
    setSelectedIds(new Set());
    setBulkError(null);
  };

  // Any filter change starts again from page 1: the old page number may not
  // exist under the new filters, and would mean something else if it did.
  const handleFilterChange = useCallback((changes: Partial<TodoFilters>) => {
    setFilters((current) => ({ ...current, ...changes }));
    setPage(1);
    setSelectedIds(new Set());
    setBulkError(null);
  }, []);

  const handleClearFilters = () => {
    setFilters(DEFAULT_TODO_FILTERS);
    setPage(1);
    setFilterBarKey((key) => key + 1);
    resetSelection();
  };

  const handlePageChange = (next: number) => {
    setPage(next);
    resetSelection();
  };

  const handlePageSizeChange = (next: number) => {
    setPageSize(next);
    setPage(1);
    resetSelection();
  };

  // After a delete or a bulk change the current page can fall off the end
  // (e.g. the last todo of the last page is gone). Move to the last page that
  // exists rather than showing an empty one. Set during render, not in an
  // effect, so the stale page is never painted.
  if (data && !isPlaceholderData && page > Math.max(data.pages, 1)) {
    setPage(Math.max(data.pages, 1));
  }

  const items = data?.items ?? [];
  // Derived from the rows on screen, so the request can only name todos the
  // user can see selected; a Set means no id is sent twice.
  const selectedOnPage = items
    .filter((todo) => selectedIds.has(todo.id))
    .map((todo) => todo.id);

  const handleSelectChange = (todo: Todo, selected: boolean) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (selected) next.add(todo.id);
      else next.delete(todo.id);
      return next;
    });
    setBulkError(null);
  };

  const handleSelectAll = (selected: boolean) => {
    setSelectedIds(selected ? new Set(items.map((todo) => todo.id)) : new Set());
    setBulkError(null);
  };

  const handleBulkApply = (completed: boolean) => {
    if (selectedOnPage.length === 0) return;
    setBulkError(null);
    bulkUpdate.mutate(
      { todo_ids: selectedOnPage, completed },
      {
        onSuccess: () => setSelectedIds(new Set()),
        // The selection is kept, so the user can retry or adjust it.
        onError: (bulkErrorCause) => {
          setBulkError(
            isAxiosError(bulkErrorCause) &&
              bulkErrorCause.response?.status === 404
              ? "Some selected todos no longer exist. Nothing was changed; refresh and try again."
              : apiErrorMessage(bulkErrorCause, "Failed to update the selected todos.")
          );
        },
      }
    );
  };

  const handleDeleted = (id: string) => {
    setSelectedIds((current) => {
      if (!current.has(id)) return current;
      const next = new Set(current);
      next.delete(id);
      return next;
    });
  };

  const handleTagDeleted = (tagId: string) => {
    // The filter would otherwise point at a tag that no longer exists (404).
    if (filters.tagId === tagId) handleFilterChange({ tagId: null });
  };

  return (
    <div className="min-h-screen bg-muted/40">
      {/* Header */}
      <header className="bg-card border-b">
        <div className="max-w-3xl mx-auto px-4 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold">Todo App</h1>
            {user && (
              <p className="text-sm text-muted-foreground">{user.email}</p>
            )}
          </div>
          <Button variant="ghost" size="sm" onClick={logout}>
            <LogOut className="h-4 w-4 mr-2" />
            Logout
          </Button>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-3xl mx-auto px-4 py-8">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-lg">My Todos</CardTitle>
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => setShowTagManager(true)}
              >
                <Tags className="h-4 w-4 mr-1" />
                Manage Tags
              </Button>
              <Button size="sm" onClick={() => setShowCreateForm(true)}>
                <Plus className="h-4 w-4 mr-1" />
                Add Todo
              </Button>
            </div>
          </CardHeader>
          <Separator />
          <CardContent className="pt-4 space-y-4">
            <TodoFilterBar
              key={filterBarKey}
              filters={filters}
              tags={tags}
              dateRangeInvalid={dateRangeInvalid}
              onChange={handleFilterChange}
              onClear={handleClearFilters}
            />

            <BulkActionsBar
              selectedCount={selectedOnPage.length}
              pageCount={items.length}
              pending={bulkUpdate.isPending}
              error={bulkError}
              onSelectAll={handleSelectAll}
              onClear={resetSelection}
              onApply={handleBulkApply}
            />

            {isLoading && (
              <div className="text-center py-12 text-muted-foreground">
                Loading todos...
              </div>
            )}

            {error && (
              <div className="text-center py-12 text-destructive">
                Failed to load todos. Please try again.
              </div>
            )}

            {data && !error && (
              <TodoList
                todos={items}
                tags={tags}
                filtered={hasActiveFilters(filters)}
                selectedIds={selectedIds}
                onSelectChange={handleSelectChange}
                onDeleted={handleDeleted}
              />
            )}

            {data && !error && data.total > 0 && (
              <>
                <div className="text-center text-sm text-muted-foreground">
                  Showing {data.items.length} of {data.total} todos
                </div>
                <TodoPagination
                  page={page}
                  pages={data.pages}
                  pageSize={query.page_size}
                  disabled={isPlaceholderData}
                  onPageChange={handlePageChange}
                  onPageSizeChange={handlePageSizeChange}
                />
              </>
            )}
          </CardContent>
        </Card>
      </main>

      {/* Create Todo Dialog */}
      <TodoForm
        mode="create"
        open={showCreateForm}
        onClose={() => setShowCreateForm(false)}
      />

      <TagManager
        open={showTagManager}
        onClose={() => setShowTagManager(false)}
        onTagDeleted={handleTagDeleted}
      />
    </div>
  );
}
