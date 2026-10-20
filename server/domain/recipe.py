class Recipe:
    """Recepta. Classe de domini pura."""

    def __init__(self, name, step_by_step, duration=None, sub_name=None,
                 note=None, dosage=None, description=None, created_at=None):
        self.id = None
        self.name = name
        self.duration = duration
        self.step_by_step = step_by_step
        self.sub_name = sub_name
        self.note = note
        self.dosage = dosage
        self.description = description
        self.created_at = created_at
        self.users = []              # M a N -> User
        self.categories = []         # M a N -> Category
        self.list_ingredients = []   # 1 a M -> ListIngredients
