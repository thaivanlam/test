import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator

# Surrounding whitespace is stripped before the length check, so "  " is
# rejected as empty and " Work " is stored as "Work" — otherwise it would not
# collide with an existing "work" under the case-insensitive unique index.
TagName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)
]


class TagCreate(BaseModel):
    name: TagName
    color: str | None = Field(None, max_length=20)


class TagUpdate(BaseModel):
    name: TagName | None = None
    color: str | None = Field(None, max_length=20)

    @field_validator("name")
    @classmethod
    def name_not_null(cls, value: str | None) -> str:
        # Omitting name keeps the current one; that path never reaches this
        # validator. An explicit null would mean "a tag with no name", which
        # the column does not allow, so reject it here as a 422 rather than
        # letting it fail in the database.
        if value is None:
            raise ValueError("name cannot be null")
        return value


class TagResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    color: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
