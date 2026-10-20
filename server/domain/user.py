class User:
    """Usuari. Classe de domini pura: no sap res de SQLAlchemy ni de la BD."""

    def __init__(self, user_name, email, password, alias=None, phone=None):
        self.id = None
        self.user_name = user_name
        self.alias = alias
        self.email = email
        self.phone = phone
        self.password = password
        self.profile = None     # 1 a 1 -> UserProfile
        self.recipes = []       # M a N -> Recipe (llista de desitjos)
        self.plants = []        # M a N -> Ingredient (llista de desitjos)


class UserProfile:
    def __init__(self, id_user=None, bio=None, img=None, country=None):
        self.id = None
        self.bio = bio
        self.img = img
        self.country = country
        self.id_user = id_user
        self.user = None        # 1 a 1 -> User
