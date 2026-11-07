from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.repositories.base import BaseRepository


class CustomerRepository(BaseRepository[Customer]):
    def __init__(self, session: Session) -> None:
        super().__init__(Customer, session)

    def get_by_email(self, email: str) -> Customer | None:
        """Fetch customer by unique email address."""
        stmt = select(Customer).where(Customer.email == email.strip().lower())
        return self.session.scalars(stmt).first()

    def list_paginated(
        self,
        skip: int = 0,
        limit: int = 20,
        kyc_status: str | None = None,
        risk_profile: str | None = None,
        search: str | None = None,
    ) -> tuple[list[Customer], int]:
        """Fetch paginated customers with database-level filtering."""
        stmt = select(Customer)
        count_stmt = select(func.count()).select_from(Customer)

        filters = []
        if kyc_status:
            filters.append(Customer.kyc_status == kyc_status)
        if risk_profile:
            filters.append(Customer.risk_profile == risk_profile)
        if search:
            filters.append(
                (Customer.first_name.ilike(f"%{search}%"))
                | (Customer.last_name.ilike(f"%{search}%"))
                | (Customer.email.ilike(f"%{search}%"))
            )

        if filters:
            stmt = stmt.where(*filters)
            count_stmt = count_stmt.where(*filters)

        total = self.session.scalar(count_stmt) or 0
        items = list(
            self.session.scalars(
                stmt.order_by(Customer.created_at.desc(), Customer.id.desc()).offset(skip).limit(limit)
            ).all()
        )
        return items, total

