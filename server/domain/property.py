class Property:
    """Propietat d'un ingredient. Classe de domini pura."""

    def __init__(self, name, description=None):
        self.id = None
        self.name = name
        self.description = description
        self.plants = []             # M a N -> Ingredient
