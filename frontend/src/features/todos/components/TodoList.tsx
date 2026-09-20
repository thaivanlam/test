import { useState } from "react";
import type { Tag } from "@/features/tags/api/tags";
import { TodoItem } from "./TodoItem";
import { TodoForm } from "./TodoForm";
import type { Todo } from "../api/todos";
import {
  useAttachTag,
  useDeleteTodo,
  useDetachTag,
  useToggleTodo,
} from "../api/todos";

interface TodoListProps {
  todos: Todo[];
  tags: Tag[];
  filtered: boolean;
  selectedIds: ReadonlySet<string>;
  onSelectChange: (todo: Todo, selected: boolean) => void;
  onDeleted: (id: string) => void;
}

export function TodoList({
  todos,
  tags,
  filtered,
  selectedIds,
  onSelectChange,
  onDeleted,
}: TodoListProps) {
  const [editingTodo, setEditingTodo] = useState<Todo | null>(null);
  const deleteTodo = useDeleteTodo();
  const toggleTodo = useToggleTodo();
  const attachTag = useAttachTag();
  const detachTag = useDetachTag();
  const tagPending = attachTag.isPending || detachTag.isPending;

  const handleDelete = (id: string) => {
    deleteTodo.mutate(id, { onSuccess: () => onDeleted(id) });
  };

  if (todos.length === 0) {
    return filtered ? (
      <div className="text-center py-12 text-muted-foreground">
        <p className="text-lg">No todos match your filters</p>
        <p className="text-sm mt-1">Try changing or clearing the filters</p>
      </div>
    ) : (
      <div className="text-center py-12 text-muted-foreground">
        <p className="text-lg">No todos yet</p>
        <p className="text-sm mt-1">Create your first todo to get started</p>
      </div>
    );
  }

  return (
    <>
      <div className="space-y-2">
        {todos.map((todo) => (
          // Keyed by id, not position: with selection and paging, a row that
          // moves must keep its own state rather than inherit its neighbour's.
          <TodoItem
            key={todo.id}
            todo={todo}
            availableTags={tags}
            selected={selectedIds.has(todo.id)}
            tagPending={tagPending}
            onSelectChange={onSelectChange}
            onToggle={toggleTodo.mutate}
            onEdit={setEditingTodo}
            onDelete={handleDelete}
            onAttachTag={(target, tagId) =>
              attachTag.mutate({ todoId: target.id, tagId })
            }
            onDetachTag={(target, tagId) =>
              detachTag.mutate({ todoId: target.id, tagId })
            }
          />
        ))}
      </div>

      {editingTodo && (
        <TodoForm
          mode="edit"
          todo={editingTodo}
          open={!!editingTodo}
          onClose={() => setEditingTodo(null)}
        />
      )}
    </>
  );
}
