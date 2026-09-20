import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { apiErrorMessage } from "@/lib/apiError";
import { queryClient } from "@/lib/queryClient";
import { todoKeys } from "@/features/todos/api/queryKeys";

/** A tag as embedded in a todo. */
export interface TagSummary {
  id: string;
  name: string;
  color: string | null;
}

export interface Tag extends TagSummary {
  created_at: string;
  updated_at: string;
}

export interface TagPayload {
  name: string;
  color: string | null;
}

export const tagKeys = {
  all: ["tags"] as const,
};

export function useTags() {
  return useQuery({
    queryKey: tagKeys.all,
    queryFn: async (): Promise<Tag[]> => {
      const response = await api.get("/tags");
      return response.data;
    },
  });
}

export function useCreateTag() {
  return useMutation({
    mutationFn: async (data: TagPayload): Promise<Tag> => {
      const response = await api.post("/tags", data);
      return response.data;
    },
    // A new tag is on no todo yet, so the todo lists are still correct.
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: tagKeys.all });
      toast.success("Tag created");
    },
  });
}

export function useUpdateTag() {
  return useMutation({
    mutationFn: async ({
      id,
      data,
    }: {
      id: string;
      data: Partial<TagPayload>;
    }): Promise<Tag> => {
      const response = await api.patch(`/tags/${id}`, data);
      return response.data;
    },
    // Todos embed each tag's name and color, so their lists are stale too.
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: tagKeys.all });
      queryClient.invalidateQueries({ queryKey: todoKeys.all });
      toast.success("Tag updated");
    },
  });
}

export function useDeleteTag() {
  return useMutation({
    mutationFn: async (id: string): Promise<void> => {
      await api.delete(`/tags/${id}`);
    },
    // Deleting a tag removes it from every todo it was on.
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: tagKeys.all });
      queryClient.invalidateQueries({ queryKey: todoKeys.all });
      toast.success("Tag deleted");
    },
    onError: (error) => {
      toast.error(apiErrorMessage(error, "Failed to delete tag"));
    },
  });
}
