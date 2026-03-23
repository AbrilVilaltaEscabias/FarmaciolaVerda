
from sqlalchemy import create_engine, Integer, String, Boolean, ForeignKey, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, Session, sessionmaker
from farmaciolaverda import engine, DB_URL

class User():
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincremental=True)
    user_name: Mapped[str] = mapped_column(String, nullable=False)
    alias: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    password: Mapped[str] = mapped_column(String, nullable=False)

class UserProfile():
    __tablename__ = "user_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bio: Mapped[str] = mapped_column(String(50), nullable=True)
    img: Mapped[str] = mapped_column(String(1000), nullable=True)

class WishListRecipes():
    __tablename__ = "wish_list_recipes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # RELATIONSHIP
    id_recipe: Mapped[int] = relationship()
    id_user: Mapped[int] = relationship()

class recipe():
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    duration: Mapped[int] = mapped_column(Integer, nullable=False)
    step_by_step: Mapped[list] = mapped_column(list, nullable=False)
    sub_name: Mapped[str] = mapped_column(String(100), nullable=True)
    note: Mapped[str] = mapped_column(String(10000), nullable=True)
    dosage: Mapped[str] = mapped_column(String(100), nullable=True)
    description: Mapped[str] = mapped_column(String(1000), nullable=True)

class Category():
    __tablename__ = "category"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)

class RecipeCategory():
    __tablename__ = "recipe_category"

    # RELATIONSHIP
    id_recipe: Mapped[int] = relationship()
    id_category: Mapped[int] = relationship()

class Ingredient():
    __tablename__ = "ingredient"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scientific_name: Mapped[str] = mapped_column(String(100), nullable=True)
    common_name: Mapped[str] = mapped_column(String(100), nullable=False)
    family: Mapped[str] = mapped_column(String(100), nullable=True)
    description: Mapped[str] = mapped_column(String(1000), nullable=True)
    country_origin: Mapped[str] = mapped_column(String(100), nullable=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)

class WishListPlant():
    __tablename__ = "wish_list_plant"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    #RELATIONSHIP
    id_plant: Mapped[int] = relationship()
    id_user: Mapped[int] = relationship()

class ListIngredients():
    __tablename__ = "list_ingredient"

    #RELATIONSHIP
    id_recipe: Mapped[int] = relationship()
    id_plant: Mapped[int] = relationship()

    quantity: Mapped[str] = mapped_column(String, nullable=True)
    isoptional: Mapped[bool] = mapped_column(Boolean, nullable=False)

class Property():
    __tablename__ = "property"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)

class PlantProperty():
    __tablename__ = "pant_property"

    #RELATIONSHIP
    id_plant: Mapped[int] = relationship()
    id_propery: Mapped[int] = relationship()
