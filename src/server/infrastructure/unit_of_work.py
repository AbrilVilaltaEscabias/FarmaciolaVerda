
class UnitOfWork:

    def __init__(self, session_factory):
        self.session_factory = session_factory

    def __enter__(self):
        from .repositories import (
            RecipeRepository,
            UserRepository,
            CategoryRepository,
            IngredientRepository,
        )

        self.session = self.session_factory()

        self.recipes = RecipeRepository(self.session)
        self.users = UserRepository(self.session)
        self.categories = CategoryRepository(self.session)
        self.ingredients = IngredientRepository(self.session)

        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is not None:
                self.rollback()
            else:
                self.commit()
        finally:
            self.session.close()

    def flush(self):
        """Send pending changes (ids, defaults) without committing."""
        self.session.flush()

    def commit(self):
        self.session.commit()

    def rollback(self):
        self.session.rollback()
