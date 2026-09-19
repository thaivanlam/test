import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import { Pencil, Trash2 } from "lucide-react";
import type { Tag } from "@/features/tags/api/tags";
import { TagBadge } from "@/features/tags/components/TagBadge";
import type { Todo } from "../api/todos";

interface TodoItemProps {
  todo: Todo;
  /** The user's tags: the only ones offered for attaching. */
  availableTags: Tag[];
  selected: boolean;
  tagPending: boolean;
  onSelectChange: (todo: Todo, selected: boolean) => void;
  onToggle: (todo: Todo) => void;
  onEdit: (todo: Todo) => void;
  onDelete: (id: string) => void;
  onAttachTag: (todo: Todo, tagId: string) => void;
  onDetachTag: (todo: Todo, tagId: string) => void;
}

export function TodoItem({
  todo,
  availableTags,
  selected,
  tagPending,
  onSelectChange,
  onToggle,
  onEdit,
  onDelete,
  onAttachTag,
  onDetachTag,
}: TodoItemProps) {
  const attachedIds = new Set(todo.tags.map((tag) => tag.id));
  const attachable = availableTags.filter((tag) => !attachedIds.has(tag.id));

  return (
    <div
      className={`flex items-start gap-3 p-3 rounded-lg border bg-card hover:bg-accent/50 transition-colors group ${
        selected ? "ring-2 ring-primary/40" : ""
      }`}
    >
      {/* Selection for bulk actions. Its name differs from the completion
          checkbox's (the title alone), so each can be told apart, by
          assistive technology as well as by tests. */}
      <Checkbox
        className="mt-0.5"
        aria-label={`Select "${todo.title}"`}
        checked={selected}
        onCheckedChange={(checked) => onSelectChange(todo, checked === true)}
      />

      <Checkbox
        id={`todo-${todo.id}`}
        className="mt-0.5"
        checked={todo.completed}
        onCheckedChange={() => onToggle(todo)}
      />

      <div className="flex-1 min-w-0 space-y-1">
        <label
          htmlFor={`todo-${todo.id}`}
          className={`text-sm font-medium cursor-pointer ${
            todo.completed ? "line-through text-muted-foreground" : ""
          }`}
        >
          {todo.title}
        </label>
        {todo.description && (
          <p className="text-xs text-muted-foreground truncate">
            {todo.description}
          </p>
        )}
        {(todo.tags.length > 0 || attachable.length > 0) && (
          <div className="flex flex-wrap items-center gap-1">
            {todo.tags.map((tag) => (
              <TagBadge
                key={tag.id}
                tag={tag}
                removeLabel={`Remove tag ${tag.name} from "${todo.title}"`}
                onRemove={() => onDetachTag(todo, tag.id)}
                disabled={tagPending}
              />
            ))}
            {attachable.length > 0 && (
              <select
                aria-label={`Add tag to "${todo.title}"`}
                className="h-6 rounded-full border border-dashed bg-transparent px-2 text-xs text-muted-foreground"
                value=""
                disabled={tagPending}
                onChange={(event) => {
                  if (event.target.value) onAttachTag(todo, event.target.value);
                }}
              >
                <option value="">+ Tag</option>
                {attachable.map((tag) => (
                  <option key={tag.id} value={tag.id}>
                    {tag.name}
                  </option>
                ))}
              </select>
            )}
          </div>
        )}
      </div>

      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity">
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          aria-label={`Edit "${todo.title}"`}
          onClick={() => onEdit(todo)}
        >
          <Pencil className="h-3.5 w-3.5" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 text-destructive hover:text-destructive"
          aria-label={`Delete "${todo.title}"`}
          onClick={() => onDelete(todo.id)}
        >
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  );
}
