from sqlalchemy import select
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
