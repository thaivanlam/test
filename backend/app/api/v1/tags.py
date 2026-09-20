import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_redis
from app.core.redis import RedisClient
from app.db.session import get_db
from app.models.tag import Tag
from app.models.user import User
from app.schemas.tag import TagCreate, TagResponse, TagUpdate
from app.services.tag_service import (
    create_tag,
    delete_tag,
    get_tag_by_id,
    get_tags,
    update_tag,
)
from app.services.todo_cache import commit_and_bump_todo_list_generation

router = APIRouter()


async def get_own_tag_or_404(
    db: AsyncSession, tag_id: uuid.UUID, user_id: uuid.UUID
) -> Tag:
    tag = await get_tag_by_id(db, tag_id, user_id)
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found",
        )
    return tag


@router.get("", response_model=list[TagResponse])
async def list_tags(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List the current user's tags, by name."""
    return await get_tags(db, current_user.id)


@router.post("", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
async def create_new_tag(
    tag_data: TagCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a tag. 409 if the user already has one with this name, in any case."""
    return await create_tag(db, tag_data, current_user.id)


@router.get("/{tag_id}", response_model=TagResponse)
async def get_tag(
    tag_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get one of the current user's tags."""
    return await get_own_tag_or_404(db, tag_id, current_user.id)


@router.patch("/{tag_id}", response_model=TagResponse)
async def update_existing_tag(
    tag_id: uuid.UUID,
    tag_data: TagUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Rename a tag and/or change its color. Omitted fields are kept."""
    tag = await get_own_tag_or_404(db, tag_id, current_user.id)
    # exclude_unset, as in the todo update: an omitted field keeps its value,
    # while an explicit "color": null clears the color.
    updated = await update_tag(db, tag, tag_data.model_dump(exclude_unset=True))
    # Cached todo lists embed each tag's name and color.
    await commit_and_bump_todo_list_generation(db, redis, current_user.id)
    return updated


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_tag(
    tag_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Delete a tag. It is removed from every todo; the todos are kept."""
    tag = await get_own_tag_or_404(db, tag_id, current_user.id)
    await delete_tag(db, tag)
    # Cached todo lists still show the tag on the todos it was attached to.
    await commit_and_bump_todo_list_generation(db, redis, current_user.id)
    return None
