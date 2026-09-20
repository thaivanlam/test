import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Pencil, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { apiErrorMessage } from "@/lib/apiError";
import {
  useCreateTag,
  useDeleteTag,
  useTags,
  useUpdateTag,
  type Tag,
} from "../api/tags";
import { tagSchema, toTagPayload, type TagFormData } from "../schemas/tag";
import { TagBadge } from "./TagBadge";

interface TagFormProps {
  /** Prefix for input ids, so two forms on screen do not share them. */
  idPrefix: string;
  tag?: Tag;
  submitLabel: string;
  pendingLabel: string;
  onSubmit: (data: TagFormData) => Promise<unknown>;
  onDone?: () => void;
  onCancel?: () => void;
}

function TagForm({
  idPrefix,
  tag,
  submitLabel,
  pendingLabel,
  onSubmit,
  onDone,
  onCancel,
}: TagFormProps) {
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<TagFormData>({
    resolver: zodResolver(tagSchema),
    defaultValues: { name: tag?.name ?? "", color: tag?.color ?? "" },
  });

  const submit = async (data: TagFormData) => {
    try {
      await onSubmit(data);
      reset({ name: tag ? data.name : "", color: tag ? data.color : "" });
      onDone?.();
    } catch (error) {
      // A duplicate name is only detectable on the server (409); show it on
      // the field it concerns.
      setError("name", {
        message: apiErrorMessage(error, "Failed to save tag"),
      });
    }
  };

  const nameId = `${idPrefix}-name`;
  const colorId = `${idPrefix}-color`;

  return (
    <form onSubmit={handleSubmit(submit)} className="space-y-2" noValidate>
      <div className="flex flex-wrap items-end gap-2">
        <div className="flex-1 min-w-32 space-y-1">
          <Label htmlFor={nameId}>Tag name</Label>
          <Input
            id={nameId}
            placeholder="e.g. Work"
            aria-invalid={!!errors.name}
            {...register("name")}
          />
        </div>
        <div className="w-36 space-y-1">
          <Label htmlFor={colorId}>Color (optional)</Label>
          <Input
            id={colorId}
            placeholder="#3b82f6"
            aria-invalid={!!errors.color}
            {...register("color")}
          />
        </div>
        <Button type="submit" size="sm" disabled={isSubmitting}>
          {isSubmitting ? pendingLabel : submitLabel}
        </Button>
        {onCancel && (
          <Button type="button" size="sm" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
        )}
      </div>
      {errors.name && (
        <p role="alert" className="text-sm text-destructive">
          {errors.name.message}
        </p>
      )}
      {errors.color && (
        <p role="alert" className="text-sm text-destructive">
          {errors.color.message}
        </p>
      )}
    </form>
  );
}

interface TagManagerProps {
  open: boolean;
  onClose: () => void;
  /** Lets the page drop a tag filter that points at a deleted tag. */
  onTagDeleted?: (tagId: string) => void;
}

export function TagManager({ open, onClose, onTagDeleted }: TagManagerProps) {
  const { data: tags, isLoading, error } = useTags();
  const createTag = useCreateTag();
  const updateTag = useUpdateTag();
  const deleteTag = useDeleteTag();
  const [editingId, setEditingId] = useState<string | null>(null);

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Manage Tags</DialogTitle>
          <DialogDescription>
            Tags are private to your account.
          </DialogDescription>
        </DialogHeader>

        <TagForm
          idPrefix="new-tag"
          submitLabel="Add tag"
          pendingLabel="Adding..."
          onSubmit={(data) => createTag.mutateAsync(toTagPayload(data))}
        />

        <div className="space-y-2 max-h-72 overflow-y-auto">
          {isLoading && (
            <p className="text-sm text-muted-foreground">Loading tags...</p>
          )}
          {error && (
            <p className="text-sm text-destructive">Failed to load tags.</p>
          )}
          {tags && tags.length === 0 && (
            <p className="text-sm text-muted-foreground">No tags yet.</p>
          )}
          {tags?.map((tag) =>
            editingId === tag.id ? (
              <div key={tag.id} className="rounded-md border p-2">
                <TagForm
                  idPrefix={`edit-tag-${tag.id}`}
                  tag={tag}
                  submitLabel="Save"
                  pendingLabel="Saving..."
                  onSubmit={(data) =>
                    updateTag.mutateAsync({
                      id: tag.id,
                      data: toTagPayload(data),
                    })
                  }
                  onDone={() => setEditingId(null)}
                  onCancel={() => setEditingId(null)}
                />
              </div>
            ) : (
              <div
                key={tag.id}
                className="flex items-center justify-between rounded-md border p-2"
              >
                <TagBadge tag={tag} />
                <div className="flex gap-1">
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label={`Rename tag ${tag.name}`}
                    onClick={() => setEditingId(tag.id)}
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    className="text-destructive hover:text-destructive"
                    aria-label={`Delete tag ${tag.name}`}
                    disabled={deleteTag.isPending}
                    onClick={() =>
                      deleteTag.mutate(tag.id, {
                        onSuccess: () => onTagDeleted?.(tag.id),
                      })
                    }
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            )
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
