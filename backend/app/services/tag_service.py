import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tag import Tag
from app.schemas.tag import TagCreate

DUPLICATE_TAG_DETAIL = "Tag with this name already exists"


async def _flush_or_conflict(db: AsyncSession) -> None:
    """Flush pending changes, turning a duplicate name into a 409.

    The unique index uq_tags_user_id_lower_name is what decides a duplicate.
    A SELECT beforehand could not: two concurrent requests would both see no
    match and both insert. Any IntegrityError here is that index, since the
    other constraints on tags (primary key, user_id foreign key) cannot be
    violated by values the API accepts.

    The session is rolled back before raising: after a failed flush it cannot
    be used again until it is, and nothing else in these requests has been
    written that would need keeping.
    """
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=DUPLICATE_TAG_DETAIL,
        )


async def get_tags(db: AsyncSession, user_id: uuid.UUID) -> list[Tag]:
    result = await db.execute(
        select(Tag).where(Tag.user_id == user_id).order_by(Tag.name, Tag.id)
    )
    return list(result.scalars().all())


async def get_tag_by_id(
    db: AsyncSession, tag_id: uuid.UUID, user_id: uuid.UUID
) -> Tag | None:
    """Get a tag by id, scoped to its owner.

    Same rule as get_todo_by_id: user_id is required, and is part of the
    WHERE clause, so another user's tag is indistinguishable from a missing one.
    """
    result = await db.execute(
        select(Tag).where(Tag.id == tag_id, Tag.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def create_tag(db: AsyncSession, tag_data: TagCreate, user_id: uuid.UUID) -> Tag:
    tag = Tag(name=tag_data.name, color=tag_data.color, user_id=user_id)
    db.add(tag)
    await _flush_or_conflict(db)
    await db.refresh(tag)
    return tag


async def update_tag(db: AsyncSession, tag: Tag, update_data: dict) -> Tag:
    for key, value in update_data.items():
        setattr(tag, key, value)
    await _flush_or_conflict(db)
    await db.refresh(tag)
    return tag


async def delete_tag(db: AsyncSession, tag: Tag) -> None:
    # The todo_tags rows go with it through ON DELETE CASCADE; the todos
    # themselves are untouched.
    await db.delete(tag)
    await db.flush()
