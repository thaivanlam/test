import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { queryClient } from "@/lib/queryClient";
import { apiErrorMessage } from "@/lib/apiError";
import type { TagSummary } from "@/features/tags/api/tags";
import { todoKeys, toTodoListParams, type TodoListQuery } from "./queryKeys";

export interface Todo {
  id: string;
  title: string;
  description: string | null;
  completed: boolean;
  user_id: string;
  created_at: string;
  updated_at: string;
  tags: TagSummary[];
}

export interface TodoListResponse {
  items: Todo[];
  total: number;
  page: number;
  /** Old name for page_size, still sent by the API. */
  size: number;
  page_size: number;
  pages: number;
}

interface CreateTodoRequest {
  title: string;
  description?: string;
}

interface UpdateTodoRequest {
  title?: string;
  description?: string;
  completed?: boolean;
}

export interface BulkStatusRequest {
  todo_ids: string[];
  completed: boolean;
}

interface BulkStatusResponse {
  updated: number;
}

/**
 * One page of todos. The query is already normalized (see queryKeys.ts), and
 * the same object is both the key and the request params.
 */
export function useTodos(query: TodoListQuery, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: todoKeys.list(query),
    queryFn: async (): Promise<TodoListResponse> => {
      const response = await api.get("/todos", {
        params: toTodoListParams(query),
      });
      return response.data;
    },
    // Keep showing the previous page while the next one loads, instead of
    // dropping back to the loading state on every page or filter change.
    placeholderData: keepPreviousData,
    enabled: options.enabled ?? true,
  });
}

/**
 * Every todo list variant (any page, any filters) is stale after a write, so
 * invalidate by the common prefix rather than by one exact key.
 */
function invalidateTodoLists() {
  return queryClient.invalidateQueries({ queryKey: todoKeys.all });
}

export function useCreateTodo() {
  return useMutation({
    mutationFn: async (data: CreateTodoRequest): Promise<Todo> => {
      const response = await api.post("/todos", data);
      return response.data;
    },
    onSuccess: () => {
      invalidateTodoLists();
      toast.success("Todo created successfully!");
    },
    onError: () => {
      toast.error("Failed to create todo");
    },
  });
}

export function useUpdateTodo() {
  return useMutation({
    mutationFn: async ({
      id,
      data,
    }: {
      id: string;
      data: UpdateTodoRequest;
    }): Promise<Todo> => {
      const response = await api.put(`/todos/${id}`, data);
      return response.data;
    },
    onMutate: async ({ id, data }) => {
      // The todo can sit in several cached lists (other pages, other
      // filters), so the optimistic change goes into all of them, and each
      // one's previous value is kept to put back if the request fails.
      await queryClient.cancelQueries({ queryKey: todoKeys.lists() });
      const previous = queryClient.getQueriesData<TodoListResponse>({
        queryKey: todoKeys.lists(),
      });
      queryClient.setQueriesData<TodoListResponse>(
        { queryKey: todoKeys.lists() },
        (list) =>
          list && {
            ...list,
            items: list.items.map((todo) =>
              todo.id === id ? { ...todo, ...data } : todo
            ),
          }
      );
      return { previous };
    },
    onError: (_error, _variables, context) => {
      context?.previous.forEach(([key, list]) => {
        queryClient.setQueryData(key, list);
      });
      toast.error("Failed to update todo");
    },
    onSettled: () => {
      invalidateTodoLists();
    },
  });
}

export function useDeleteTodo() {
  return useMutation({
    mutationFn: async (id: string): Promise<void> => {
      await api.delete(`/todos/${id}`);
    },
    onSuccess: () => {
      invalidateTodoLists();
      toast.success("Todo deleted successfully!");
    },
    onError: () => {
      toast.error("Failed to delete todo");
    },
  });
}

export function useToggleTodo() {
  const updateTodo = useUpdateTodo();

  return {
    ...updateTodo,
    mutate: (todo: Todo) => {
      updateTodo.mutate({
        id: todo.id,
        data: { completed: !todo.completed },
      });
    },
  };
}

export function useAttachTag() {
  return useMutation({
    mutationFn: async ({
      todoId,
      tagId,
    }: {
      todoId: string;
      tagId: string;
    }): Promise<void> => {
      await api.post(`/todos/${todoId}/tags`, { tag_id: tagId });
    },
    onSuccess: () => {
      invalidateTodoLists();
    },
    onError: (error) => {
      toast.error(apiErrorMessage(error, "Failed to add tag"));
    },
  });
}

export function useDetachTag() {
  return useMutation({
    mutationFn: async ({
      todoId,
      tagId,
    }: {
      todoId: string;
      tagId: string;
    }): Promise<void> => {
      await api.delete(`/todos/${todoId}/tags/${tagId}`);
    },
    onSuccess: () => {
      invalidateTodoLists();
    },
    onError: (error) => {
      toast.error(apiErrorMessage(error, "Failed to remove tag"));
    },
  });
}

/**
 * No optimistic update: the API applies all or none, and a partial local
 * guess would be wrong on exactly the failure case (404 for one id).
 */
export function useBulkUpdateStatus() {
  return useMutation({
    mutationFn: async (data: BulkStatusRequest): Promise<BulkStatusResponse> => {
      const response = await api.patch("/todos/bulk-status", data);
      return response.data;
    },
    onSuccess: ({ updated }, { completed }) => {
      invalidateTodoLists();
      toast.success(
        `Marked ${updated} ${updated === 1 ? "todo" : "todos"} as ${
          completed ? "completed" : "active"
        }`
      );
    },
  });
}
