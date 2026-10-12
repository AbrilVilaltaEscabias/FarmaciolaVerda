from typing import TYPE_CHECKING
from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ...infrastructure.db import Base

if TYPE_CHECKING:
    from .user import User

class UserProfile(Base):
    __tablename__ = "user_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bio: Mapped[str] = mapped_column(String(500), nullable=True)
    img: Mapped[str] = mapped_column(String(1000), nullable=True)
    country: Mapped[str] = mapped_column(String, nullable=True)

    # 1 to 1 — FK amb unique=True
    id_user: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    user: Mapped["User"] = relationship(back_populates="profile")