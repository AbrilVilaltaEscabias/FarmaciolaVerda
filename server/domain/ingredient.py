class Ingredient:
    """Ingredient (planta). Classe de domini pura."""

    def __init__(self, common_name, type, scientific_name=None, family=None,
                 description=None, country_origin=None, image_url=None):
        self.id = None
        self.scientific_name = scientific_name
        self.common_name = common_name
        self.family = family
        self.description = description
        self.country_origin = country_origin
        self.type = type
        self.image_url = image_url
        self.users = []              # M a N -> User
        self.properties = []         # M a N -> Property
        self.list_ingredients = []   # 1 a M -> ListIngredients
