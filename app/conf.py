# Database connection

from app.env_vars import DB_USER_NAME, DB_USER_PASS

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
    SQLALCHEMY_DATABASE_URI = sqlalch.engine.URL.create(
        drivername="postgresql",
        username=DB_USER_NAME,
        password=DB_USER_PASS,
        host="decider-db",
        port=5432,
        database="production_5000_all_mii",
    )


class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = sqlalch.engine.URL.create(
        drivername="postgresql",
        username=DB_USER_NAME,
        password=DB_USER_PASS,
        host="decider-db",
        port=5432,
        database="production_5000_all_mii",
    )


class StagingConfig(Config):
    SQLALCHEMY_DATABASE_URI = sqlalch.engine.URL.create(
        drivername="postgresql",
        username=DB_USER_NAME,
        password=DB_USER_PASS,
        host="decider-db",
        port=5432,
        database="staging_9000_cti_only",
    )


class DevelopmentConfig(Config):
    SQLALCHEMY_DATABASE_URI = sqlalch.engine.URL.create(
        drivername="postgresql",
        username=DB_USER_NAME,
        password=DB_USER_PASS,
        host="decider-db",
        port=5432,
        database="staging_9000_cti_only",
    )
    LOG_LEVEL = "DEBUG"
    TESTING = True
    DEBUG = True
    WTF_CSRF_CHECK_DEFAULT = False


class PytestConfig(Config):
    SQLALCHEMY_DATABASE_URI = sqlalch.engine.URL.create(
        drivername="postgresql",
        username=DB_USER_NAME,
        password=DB_USER_PASS,
        host="decider-db",
        port=5432,
        database="staging_9000_cti_only",
    )
    WTF_CSRF_CHECK_DEFAULT = False


conf_configs = [
    DefaultConfig,
    ProductionConfig,
    StagingConfig,
    DevelopmentConfig,
    PytestConfig,
]
