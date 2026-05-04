from sqlalchemy.orm import Session
from .abstract_repositories import RecipeRepository, UserRepository, CategoryRepository, IngredientRepository

class UnitOfWork:
    def __init__(self, session_factory):
        self.session_factory = session_factory  # Guarda el sessionmaker, no la sessió en si

    """ Quant s'entre al bloc with... """
    def __enter__(self):
        self.session = self.session_factory() # Crea una nova sessió
        
        # Inicialitza tots els repositoris compartint la mateixa sessió
        # Així totes les operacions formen part de la mateixa transacció
        self.recipes = RecipeRepository(self.session)
        self.users = UserRepository(self.session)
        self.categories = CategoryRepository(self.session)
        self.ingredients = IngredientRepository(self.session)
        
        return self # Retorna l'objecte UnitOfWork perquè estigui accessible amb 'as uow'

    """ Quant es surt del bloc with... """
    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None: # Si ha ocorregut una excepció dins del bloc 'with'...
            self.rollback() # desfà tots els canvis de la transacció
        else:
            self.commit() # Si tot ha anat bé, guarda els canvis a la BD
        self.session.close() # Tanca la sessio

    def commit(self):
        self.session.commit() # Confirma i guarda tots els canvis pendents a la BD

    def rollback(self):
        self.session.rollback() # Desfà tots els canvis pendents de la transacció actual