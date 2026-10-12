from typing import TYPE_CHECKING
from sqlalchemy import Integer, String, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ...infrastructure.db import Base

if TYPE_CHECKING:
    from .recipe import Recipe
    from .ingredient import Ingredient


class ListIngredients(Base):
    __tablename__ = "list_ingredient"
    __table_args__ = (UniqueConstraint("id_recipe", "id_plant"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    quantity: Mapped[str] = mapped_column(String, nullable=True)
    isoptional: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_checked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # FKs
    id_recipe: Mapped[int] = mapped_column(Integer, ForeignKey("recipe.id"), nullable=False)
    id_plant: Mapped[int] = mapped_column(Integer, ForeignKey("ingredient.id"), nullable=False)

    # Relationships
    recipe: Mapped["Recipe"] = relationship(back_populates="list_ingredients")
    plant: Mapped["Ingredient"] = relationship(back_populates="list_ingredients")