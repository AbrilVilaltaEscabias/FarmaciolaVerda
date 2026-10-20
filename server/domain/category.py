class Category:
    """Categoria de receptes. Classe de domini pura."""

    def __init__(self, name, description=None):
        self.id = None
        self.name = name
        self.description = description
        self.recipes = []            # M a N -> Recipe
