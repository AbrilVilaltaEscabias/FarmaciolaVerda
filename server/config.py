import os
from dotenv import load_dotenv

load_dotenv()

ENVIROMENT = os.getenv("ENVIRONMENT", "development")

DB_URL = {
    "development" : os.getenv("DB_URL_DEVELOPMENT"),
    "test" : os.getenv("DB_URL_TEST"),
    "production" : os.getenv("DB_URL_PRODUCTION")
}.get(ENVIROMENT)