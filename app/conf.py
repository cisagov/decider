# Database connection

from app.env_vars import DB_USERNAME, DB_PASSWORD, DB_HOSTNAME, DB_PORT, DB_DATABASE

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
    """Default Profile / Database Config
    - This class must always exist
    - Do not modify this class - as Docker sets it via env_vars
    - (not always, but) This class is commonly used as a default if not specified
    """
    SQLALCHEMY_DATABASE_URI = sqlalch.engine.URL.create(
        drivername="postgresql",
        username=DB_USERNAME,
        password=DB_PASSWORD,
        host=DB_HOSTNAME,
        port=DB_PORT,
        database=DB_DATABASE,
    )


class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = sqlalch.engine.URL.create(
        drivername="postgresql",
        username=DB_USERNAME,
        password=DB_PASSWORD,
        host=DB_HOSTNAME,
        port=DB_PORT,
        database=DB_DATABASE,
    )


conf_configs = [
    DefaultConfig,
    ProductionConfig,
]
