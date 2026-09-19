export const DEFAULT_PAGE_SIZE = 20;
// The API rejects page_size above 100 with a 422.
export const MAX_PAGE_SIZE = 100;

export type TodoStatusFilter = "all" | "active" | "completed";

/** Filter state as the filter bar holds it. */
export interface TodoFilters {
  status: TodoStatusFilter;
  tagId: string | null;
  keyword: string;
  /** YYYY-MM-DD, exactly as picked; never converted through a Date. */
  dateFrom: string | null;
  dateTo: string | null;
}

export const DEFAULT_TODO_FILTERS: TodoFilters = {
  status: "all",
  tagId: null,
  keyword: "",
  dateFrom: null,
  dateTo: null,
};

/**
 * One todo list request in canonical form, named as the API names its query
 * parameters. It is both the variable part of the query key and the source of
 * the request's params, so a cached entry can only ever hold the answer to
 * the request its key describes.
 */
export interface TodoListQuery {
  page: number;
  page_size: number;
  status: "active" | "completed" | null;
  tag_id: string | null;
  keyword: string | null;
  date_from: string | null;
  date_to: string | null;
}

export interface TodoListInput {
  page?: number;
  pageSize?: number;
  filters?: Partial<TodoFilters>;
}

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

function normalizeDate(value: string | null | undefined): string | null {
  return value && ISO_DATE.test(value) ? value : null;
}

/**
 * Everything that means the same request comes out identical: blank values
 * become null, the keyword is trimmed and lowercased (the API matches it
 * case-insensitively and normalizes it the same way), and page and page size
 * fall back to their defaults or are clamped to what the API accepts.
 */
export function normalizeTodoListQuery({
  page,
  pageSize,
  filters = {},
}: TodoListInput): TodoListQuery {
  const keyword = (filters.keyword ?? "").trim().toLowerCase();
  const status = filters.status ?? "all";
  const size =
    pageSize !== undefined && Number.isInteger(pageSize) && pageSize >= 1
      ? Math.min(pageSize, MAX_PAGE_SIZE)
      : DEFAULT_PAGE_SIZE;

  // Built in one fixed property order. TanStack Query hashes keys with object
  // properties sorted anyway, so order could not produce two keys; this just
  // keeps the object readable in devtools.
  return {
    page: page !== undefined && Number.isInteger(page) && page >= 1 ? page : 1,
    page_size: size,
    status: status === "all" ? null : status,
    tag_id: filters.tagId || null,
    keyword: keyword || null,
    date_from: normalizeDate(filters.dateFrom),
    date_to: normalizeDate(filters.dateTo),
  };
}

/** Query params for axios: unset filters are left out of the URL. */
export function toTodoListParams(
  query: TodoListQuery
): Record<string, string | number> {
  const params: Record<string, string | number> = {};
  for (const [name, value] of Object.entries(query)) {
    if (value !== null) params[name] = value;
  }
  return params;
}

export function hasActiveFilters(filters: TodoFilters): boolean {
  const query = normalizeTodoListQuery({ filters });
  return [
    query.status,
    query.tag_id,
    query.keyword,
    query.date_from,
    query.date_to,
  ].some((value) => value !== null);
}

export const todoKeys = {
  /** Prefix of every todo query: invalidating it refreshes every list variant. */
  all: ["todos"] as const,
  lists: () => [...todoKeys.all, "list"] as const,
  list: (query: TodoListQuery) => [...todoKeys.lists(), query] as const,
};

export function todoListQueryKey(input: TodoListInput) {
  return todoKeys.list(normalizeTodoListQuery(input));
}
