from collections.abc import Sequence
from typing import Any, Generic, TypeVar
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Generic base repository providing standard CRUD and query operations."""

    def __init__(self, model: type[ModelType], session: Session) -> None:
        self.model = model
        self.session = session

    def create(self, instance: ModelType) -> ModelType:
        """Add and persist a new model instance."""
        self.session.add(instance)
        self.session.flush()
        return instance

    def get_by_id(self, id_value: Any) -> ModelType | None:
        """Fetch a record by its primary key ID."""
        return self.session.get(self.model, id_value)

    def exists(self, id_value: Any) -> bool:
        """Check whether a record with given ID exists."""
        stmt = select(func.count()).select_from(self.model).where(self.model.id == id_value)  # type: ignore[attr-defined]
        return bool(self.session.scalar(stmt))

    def list(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: Sequence[Any] | None = None,
        order_by: Sequence[Any] | None = None,
    ) -> list[ModelType]:
        """List records with optional filtering, ordering, and pagination."""
        stmt: Select[tuple[ModelType]] = select(self.model)
        if filters:
            for condition in filters:
                stmt = stmt.where(condition)
        if order_by:
            stmt = stmt.order_by(*order_by)
        stmt = stmt.offset(skip).limit(limit)
        return list(self.session.scalars(stmt).all())

    def count(self, filters: Sequence[Any] | None = None) -> int:
        """Count total matching records."""
        stmt = select(func.count()).select_from(self.model)
        if filters:
            for condition in filters:
                stmt = stmt.where(condition)
        count_val = self.session.scalar(stmt)
        return count_val or 0

    def update(self, instance: ModelType, **kwargs: Any) -> ModelType:
        """Update permitted attributes on an existing model instance."""
        for key, value in kwargs.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        self.session.flush()
        return instance

    def delete(self, instance: ModelType) -> None:
        """Delete an instance from the database."""
        self.session.delete(instance)
        self.session.flush()

