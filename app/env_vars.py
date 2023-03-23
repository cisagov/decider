from dotenv import load_dotenv
import sys
import os

# loads .env into the environment and attempts to read needed variables
# allows for variables to be provided by environment itself even (they just need to exist somehow)

load_dotenv()

try:
    DB_USERNAME = os.environ["DB_USERNAME"]
    DB_PASSWORD = os.environ["DB_PASSWORD"]
    DB_HOSTNAME = os.environ["DB_HOSTNAME"]
    DB_PORT = os.environ["DB_PORT"]
    DB_DATABASE = os.environ["DB_DATABASE"]
    CART_ENC_KEY = os.environ["CART_ENC_KEY"]
    ADMIN_EMAIL = os.environ["ADMIN_EMAIL"]
    ADMIN_PASS = os.environ["ADMIN_PASS"]
except KeyError:
    print(
        "Failed to find all of the required environment variables mentioned in: app/env_vars.py.\n"
        "Either modify .env using .env.docker / .env.manual as a template, or edit the environment variables before launch."
    )
    sys.exit(1)
