# Database connection

from app.env_vars import (
    # connect to db
    DB_HOSTNAME,
    DB_PORT,
    DB_DATABASE,
    # db admin user
    DB_ADMIN_NAME,
    DB_ADMIN_PASS,
    # db kiosk user
    DB_KIOSK_NAME,
    DB_KIOSK_PASS,
)

import sqlalchemy as sqlalch


class Config:
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DECIDER_LOG = "./decider.log"
    LOG_LEVEL = "INFO"
    START_QUESTION = "What is the adversary trying to do?"
    BASE_TECHNIQUE_ANSWER = (
        "There was **not enough context** to identify a sub-technique, but the **base technique still applies**."
    )
    WTF_CSRF_TIME_LIMIT = None


class DefaultConfig(Config):
    """Database Administration Config
    - This class must always exist
    - Do not modify this class - as Docker sets it via env_vars
    - (not always, but) This class is commonly used as a default if not specified
    """

    SQLALCHEMY_DATABASE_URI = sqlalch.engine.URL.create(
        drivername="postgresql",
        username=DB_ADMIN_NAME,
        password=DB_ADMIN_PASS,
        host=DB_HOSTNAME,
        port=DB_PORT,
        database=DB_DATABASE,
    )


class KioskConfig(Config):
    """Kiosk-Mode
    - This class must always exist
    - Puts Decider into a read-only mode w/ logins disabled
    - Disables auth / editing / user related routes
    - Uses limited DB Kiosk user
    """

    KIOSK_MODE = True
    SQLALCHEMY_DATABASE_URI = sqlalch.engine.URL.create(
        drivername="postgresql",
        username=DB_KIOSK_NAME,
        password=DB_KIOSK_PASS,
        host=DB_HOSTNAME,
        port=DB_PORT,
        database=DB_DATABASE,
    )


conf_configs = Config.__subclasses__()
