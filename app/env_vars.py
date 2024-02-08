from dotenv import load_dotenv
import sys
import os

# loads .env into the environment and attempts to read needed variables
# allows for variables to be provided by environment itself even (they just need to exist somehow)

load_dotenv()

try:
    # database
    DB_HOSTNAME = os.environ["DB_HOSTNAME"]
    DB_PORT = os.environ["DB_PORT"]
    DB_DATABASE = os.environ["DB_DATABASE"]

    # db admin user
    DB_ADMIN_NAME = os.environ["DB_ADMIN_NAME"]
    DB_ADMIN_PASS = os.environ["DB_ADMIN_PASS"]

    # db kiosk user
    DB_KIOSK_NAME = os.environ["DB_KIOSK_NAME"]
    DB_KIOSK_PASS = os.environ["DB_KIOSK_PASS"]

    # cart encryption key
    CART_ENC_KEY = os.environ["CART_ENC_KEY"]

    # app admin login
    APP_ADMIN_EMAIL = os.environ["APP_ADMIN_EMAIL"]
    APP_ADMIN_PASS = os.environ["APP_ADMIN_PASS"]

except KeyError:
    print(
        "Failed to find all of the required environment variables mentioned in: app/env_vars.py.\n"
        "Either modify .env using .env.docker / .env.manual as a template, or edit the environment"
        " variables before launch."
    )
    sys.exit(1)
