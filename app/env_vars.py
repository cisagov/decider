from dotenv import load_dotenv
import sys
import os

# loads .env into the environment and attempts to read needed variables
# allows for variables to be provided by environment itself even (they just need to exist somehow)


load_dotenv()

try:
    DB_USER_NAME = os.environ["DB_USER_NAME"]
    DB_USER_PASS = os.environ["DB_USER_PASS"]
    CART_ENC_KEY = os.environ["CART_ENC_KEY"]
except KeyError:
    print(
        "Failed to find all of the required environment variables: DB_USER_NAME, DB_USER_PASS, CART_ENC_KEY.\n"
        "Either modify .env using .env.example as a template, or edit the environment variables before launch."
    )
    sys.exit(1)
