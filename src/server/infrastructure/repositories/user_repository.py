
from sqlalchemy import select

from ..abstract_repositories import AbstractRepository
from ...domain.model.user import User


class UserRepository(AbstractRepository[str, User]):

    def _validate(self, user: User) -> None:
        if user.user_name is None:
            raise ValueError("User name attribute is mandatory")

        if user.alias is None:
            user.alias = user.user_name

        if user.email is None:
            raise ValueError("Email attribute is mandatory")

        if user.password is None:
            raise ValueError("Password attribute is mandatory")

    def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        return self.session.scalars(stmt).first()
