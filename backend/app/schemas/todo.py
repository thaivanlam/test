import uuid
from datetime import datetime

from pydantic import BaseModel, Field, StrictBool

from app.schemas.tag import TagSummary


class TodoCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = None


class TodoUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    completed: bool | None = None


# Same ceiling as the list's page_size: bulk actions apply to a selection made
# on one page of the list, so a request never needs more ids than a page holds.
MAX_BULK_TODO_IDS = 100


class TodoBulkStatusUpdate(BaseModel):
    todo_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=MAX_BULK_TODO_IDS)
    # StrictBool: plain bool would also take "yes", "1" or 0, and a bulk write
    # is the wrong place to guess what a malformed value meant.
    completed: StrictBool


class TodoBulkStatusResponse(BaseModel):
    # Distinct todos changed; duplicates in the request are counted once.
    updated: int


class TodoResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    completed: bool
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    user_email: str | None = None
    tags: list[TagSummary] = []

    model_config = {"from_attributes": True}


class TodoListResponse(BaseModel):
    items: list[TodoResponse]
    total: int
    page: int
    # size is the original name and stays for existing clients; page_size is
    # the same value under the name the query parameter now uses.
    size: int
    page_size: int
    pages: int
