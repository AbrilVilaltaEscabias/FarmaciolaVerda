class ListIngredients:
    """Ingredient dins d'una recepta (amb quantitat). Classe de domini pura."""

    def __init__(self, id_recipe=None, id_plant=None, quantity=None,
                 isoptional=False, is_checked=False):
        self.id = None
        self.quantity = quantity
        self.isoptional = isoptional
        self.is_checked = is_checked
        self.id_recipe = id_recipe
        self.id_plant = id_plant
        self.recipe = None           # -> Recipe
        self.plant = None            # -> Ingredient
