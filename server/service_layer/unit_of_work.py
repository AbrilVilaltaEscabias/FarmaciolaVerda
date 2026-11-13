from abc import ABC, abstractmethod
from types import TracebackType

from sqlalchemy.orm import sessionmaker

from server.adapters.abstract_repositories import (
    AbstractCategoryRepository,
    AbstractIngredientRepository,
    AbstractRecipeRepository,
    AbstractUserRepository,
)


class AbstractUnitOfWork(ABC):
    """Interfície: els serveis només coneixen això, no SQLAlchemy."""

    recipes: AbstractRecipeRepository
    users: AbstractUserRepository
    categories: AbstractCategoryRepository
    ingredients: AbstractIngredientRepository

    @abstractmethod
    def __enter__(self) -> "AbstractUnitOfWork": ...

    @abstractmethod
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    @abstractmethod
    def flush(self) -> None: ...

    @abstractmethod
    def commit(self) -> None: ...

    @abstractmethod
    def rollback(self) -> None: ...


class SqlAlchemyUnitOfWork(AbstractUnitOfWork):
    def __init__(self, session_factory: sessionmaker | None = None) -> None:
        if session_factory is None:
            from server.db import Session      # sessionmaker per defecte
            session_factory = Session
        self.session_factory = session_factory  # Guarda el sessionmaker, no la sessió en si

    """ Quan s'entra al bloc with... """

    def __enter__(self) -> "SqlAlchemyUnitOfWork":
        # Imports aquí dins perquè només aquest fitxer coneix la implementació SQLAlchemy
        from server.adapters.sqlalchemy_repositories import (
            CategoryRepository, IngredientRepository, RecipeRepository, UserRepository,
        )
        self.session = self.session_factory()   # Crea una nova sessió

        # Tots els repositoris comparteixen la mateixa sessió:
        # així totes les operacions formen part de la mateixa transacció
        self.recipes = RecipeRepository(self.session)
        self.users = UserRepository(self.session)
        self.categories = CategoryRepository(self.session)
        self.ingredients = IngredientRepository(self.session)

        return self

    """ Quan se surt del bloc with... """

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            self.rollback()      # si hi ha hagut una excepció, desfà els canvis
        else:
            self.commit()        # si tot ha anat bé, guarda els canvis a la BD
        self.session.close()

    def flush(self) -> None:
        self.session.flush()     # envia els canvis a la BD sense confirmar (dona l'id)

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()
