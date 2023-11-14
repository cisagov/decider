from flask import Flask, session, redirect, request, g, jsonify, has_app_context
from flask.globals import current_app
from flask.helpers import url_for
from flask.templating import render_template
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect
from flask_principal import (
    Principal,
    identity_loaded,
    RoleNeed,
    UserNeed,
)

from sqlalchemy_utils.types.encrypted.encrypted_type import InvalidCiphertextError

from sqlalchemy.exc import OperationalError as SQLAlchOperationalError
from psycopg2 import OperationalError as psycopgOperationalError
from app.routes.utils import ErrorDuringRoute, ErrorDuringHTMLRoute

from app.models import AttackVersion, db, User

from app.routes.auth import auth_
from app.routes.profile import profile_
from app.routes.question import question_
from app.routes.search import search_
from app.routes.utils_db import VersionPicker
from app.routes.edit import edit_
from app.routes.docs import docs_
from app.routes.admin import admin_
from app.routes.api import api_
from app.routes.misc import misc_

from app.utils.db.util import get_config_option_map

import string
import random
import argparse
import logging.config
import os
from datetime import timedelta
import sys
import importlib
import json
import traceback

from app.version import DECIDER_APP_VERSION

# frontend template config - from `config/frontend.json`
FRONTEND_CONF = dict(
    base_url_href="/",
    use_minified_srcs=True,
    classification_level="",
    classification_message="",
    use_cdn_resources=False,
)
with open("config/frontend.json", "rt") as fh:
    try:
        frontend_conf_file = json.load(fh)
        for key in FRONTEND_CONF.keys():
            if key in frontend_conf_file:
                FRONTEND_CONF[key] = frontend_conf_file[key]
    except Exception:
        print(f"** ERROR loading or applying config/frontend.json\n{traceback.format_exc()}")
        sys.exit(1)

# logging config - get from `config/logging.json` and convert to dict
with open("config/logging.json", "rt") as fh:
    try:
        log_conf_dict = json.load(fh)
        logging.config.dictConfig(log_conf_dict)  # apply logging config
    except Exception:
        print(f"** ERROR loading or applying config/logging.json\n{traceback.format_exc()}")
        sys.exit(1)

# ---------------------------------------------------------------------------------------------------------------------
# Flask Request ID & current_user.email log field

old_factory = logging.getLogRecordFactory()


def record_factory(*args, **kwargs):
    record = old_factory(*args, **kwargs)
    record.request_id_email = ""  # start empty unless conditions met

    # must be in app
    if not has_app_context():
        return record

    # must have id available
    flask_request_id = g.get("request_id")
    if not flask_request_id:
        return record

    # if a route defines a route title, use it in logs as such "{before fields} - {route title}: {message}"
    route_title = g.get("route_title", "")
    route_title = f"{route_title}: " if route_title else ""

    # identify email or anon, add field to record
    user_email = current_user.email if current_user.is_authenticated else "AnonymousUser"
    record.request_id_email = f"{flask_request_id} ({user_email}) - {route_title}"
    return record


logging.setLogRecordFactory(record_factory)


def make_request_id():
    """Generates a random ID to be included in all log statements for a single Flask request-response pair"""
    return "".join(random.choice(string.ascii_letters) for _ in range(8))


# ---------------------------------------------------------------------------------------------------------------------

logger = logging.getLogger(__name__)


def app_setup(config):
    """Creates the Flask app instance itself - sets / loads configuration"""

    app = Flask(__name__, template_folder="./app/templates", static_folder="./app/static")
    app.url_map.strict_slashes = False
    app.secret_key = os.urandom(24)
    app.config.from_object(config)
    return app


def security_setup(app):
    """Sets up CSRF protection and login settings"""

    csrf = CSRFProtect()
    csrf.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = "auth_.login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(session_token):  # works in tandem with: app.models.User.get_id() -> self.session_token
        login_manager.session_protection = "strong"
        return User.query.filter_by(session_token=session_token).first()


def register_blueprints(app):
    """Register application blueprints"""
    app.register_blueprint(auth_)
    app.register_blueprint(profile_)
    app.register_blueprint(question_)
    app.register_blueprint(search_)
    app.register_blueprint(edit_)
    app.register_blueprint(docs_)
    app.register_blueprint(admin_)
    app.register_blueprint(misc_)
    app.register_blueprint(api_)


def kiosk_mode(app):
    """Configures the app for Kiosk Mode
    - Auth/login/logout are disabled
    - Routes related to user state/editing/admin are disabled
    - Templates hide anything related to logged-in users
    - Limited read-only database user is used
    """

    logging.basicConfig(
        filename=current_app.config["DECIDER_LOG"],
        level=getattr(logging, current_app.config["LOG_LEVEL"].upper()),
    )

    @app.before_request
    def before_request():
        g.request_id = make_request_id()
        g.kiosk_mode = True

        # unknown URL requested -> 404
        if request.endpoint is None:
            logger.warning("Invalid URL requested - sending 404 page")
            return render_template("status_codes/404.html"), 404

        # Kiosk-disabled URL requested -> 404 w/ note
        elif getattr(app.view_functions[request.endpoint], "disabled_in_kiosk", False):
            logger.warning("Kiosk-disabled URL requested - sending 404 page")
            return render_template("status_codes/404.html", reason_for_404="This URL is disabled in Kiosk-Mode"), 404

        # accessible route
        return

    @identity_loaded.connect_via(app)
    def on_identity_loaded(sender, identity):
        # Set the identity user object
        identity.user = current_user

        # everybody is a member now
        identity.provides.add(RoleNeed("member"))


def prod_mode(app):
    """Configures the environment for production mode"""

    logging.basicConfig(
        filename=current_app.config["DECIDER_LOG"],
        level=getattr(logging, current_app.config["LOG_LEVEL"].upper()),
    )

    @app.before_request
    def before_request():
        g.request_id = make_request_id()
        g.kiosk_mode = False

        session.permanent = True
        app.permanent_session_lifetime = timedelta(minutes=2880)

        # permission checking for routes
        if request.endpoint is None:
            logger.warning("Invalid URL requested - sending 404 page")
            return render_template("status_codes/404.html"), 404
        elif request.endpoint is not None and any(
            [
                request.endpoint.startswith("static"),
                current_user.is_authenticated,
                getattr(app.view_functions[request.endpoint], "is_public", False),
            ]
        ):
            # if the user is logged in, if the endpoint is for static content, or the endpoint is public
            return
        else:
            logger.info("Requested endpoint requires auth login.")
            return redirect(url_for("auth_.login"))

    @identity_loaded.connect_via(app)
    def on_identity_loaded(sender, identity):
        # Set the identity user object
        identity.user = current_user

        # Add the UserNeed to the identity
        if hasattr(current_user, "id"):
            identity.provides.add(UserNeed(current_user.id))

        # Assuming the User model has a list of roles, update the
        # identity with the roles that the user provides
        if hasattr(current_user, "role"):
            identity.provides.add(RoleNeed(current_user.role.name))


# helper function for prod/dev mode
def set_mode(app):
    with app.app_context():
        if current_app.config.get("KIOSK_MODE"):
            kiosk_mode(app)
        else:
            logger.error("Only the Kiosk (KioskConfig) is supported in this build! Exiting!")
            sys.exit(1)
            # prod_mode(app)


def context_setup(app):
    """
    Setup context_processor to feed variables needed across all pages
    Some variables may already be set, others are exclusivly provided here
    """

    @app.context_processor
    def manage_context_vars():
        g.decider_app_version = DECIDER_APP_VERSION

        if g.get("version_picker") is None:
            version_found = VersionPicker().set_vars()

            # no versions on server
            if not version_found:
                logger.error("There are no ATT&CK versions installed! Need at least 1 to run! Exiting!")
                sys.exit(1)

        return dict(frontend_conf=FRONTEND_CONF)


def error_handlers(app):
    """
    Register handlers for errors / exceptions produced during the operation of the Flask app

    ErrorDuringRoute (error occurred in request-response cycle)
    - ErrorDuringHTMLRoute -> send HTTP code page
    - ErrorDuringAJAXRoute -> send JSON toast message

    Exception (error occurred outside of request-response cycle)
    """

    @app.errorhandler(ErrorDuringRoute)
    def handle_route_error(wrap_ex):
        """
        Handles unexpected errors that arise from within a route function
        Uses error wrappers to signal what return type should be used for the response

        Error Wrapper           Response to Use
        ErrorDuringHTMLRoute -> HTTP Code Template
        ErrorDuringAJAXRoute -> jsonify(message=""), code
        """
        base_ex = wrap_ex.__cause__

        # DB Issue
        if isinstance(base_ex, (psycopgOperationalError, SQLAlchOperationalError)):
            logger.exception("Database error occurred")
            error_num = 0

        # Cart Encryption Key Mismatch - Extremely Bad
        elif isinstance(base_ex, InvalidCiphertextError):
            logger.critical(
                "Cart encryption key doesn't work for an existing cart. "
                "It must have been changed. Fix now or risk data loss",
                exc_info=True,
            )
            error_num = 1

        # General Case
        else:  # Exception
            logger.exception("A general unexpected error occurred")
            error_num = 2

        # ---------------------------------------------------------------------

        # HTML response
        if isinstance(wrap_ex, ErrorDuringHTMLRoute):
            error_num_to_template = {
                0: "status_codes/500.html",
                1: "status_codes/cart_enc_key_invalid.html",
                2: "status_codes/500.html",
            }
            return render_template(error_num_to_template[error_num]), 500

        # JSON response
        else:  # ErrorDuringAJAXRoute
            error_num_to_message = {
                0: "Database error occurred.",
                1: "Cart Enc Key Mismatch - Contact Admin ASAP.",
                2: "General Internal Server Error.",
            }
            return jsonify(message=error_num_to_message[error_num]), 500

    @app.errorhandler(Exception)
    def handle_nonroute_error(ex):
        """Handles unexpected errors that occurred outside of a request-response cycle"""

        # DB Issue
        if isinstance(ex, (psycopgOperationalError, SQLAlchOperationalError)):
            logger.exception("Database error occurred")

        # Cart Encryption Key Mismatch - Extremely Bad
        elif isinstance(ex, InvalidCiphertextError):
            logger.critical(
                "Cart encryption key doesn't work for an existing cart. "
                "It must have been changed. Fix now or risk data loss",
                exc_info=True,
            )

        # General Case
        else:  # Exception
            logger.exception("A general unexpected error occurred")

        # no response should technically exist here since this should be prompted without a request
        return "", 204  # no content

    # general HTTP code handlers

    @app.errorhandler(404)
    def page_not_found(ex):
        return render_template("status_codes/404.html"), 404

    @app.errorhandler(403)
    def not_authorized(ex):
        return render_template("status_codes/403.html"), 403

    @app.errorhandler(500)
    def internal_server_error(ex):
        return render_template("status_codes/500.html"), 500


def create_app(config):
    logger.debug("Creating the App.")
    app = app_setup(config)

    Principal(app)
    security_setup(app)
    db.init_app(app)
    register_blueprints(app)
    set_mode(app)
    context_setup(app)
    error_handlers(app)

    return app


parser = argparse.ArgumentParser(
    description="Decider is a web application that helps analysts with navigating the ATT&CK framework."
)
parser.add_argument(
    "--config",
    default="KioskConfig",
    help=(
        "Configuration class to start Decider with. "
        f'Current configurations: {", ".join(list(get_config_option_map().keys()))}'
    ),
)
args = parser.parse_args()

try:
    config = getattr(importlib.import_module("app.conf"), args.config)
except Exception:
    logger.exception(
        "Missing config. Please add the configuration name provided to app/conf.py or use an existing configuration."
    )
    sys.exit(1)

app = create_app(config)

if __name__ == "__main__":
    # at least 1 AttackVersion is required to function at all
    with app.app_context():
        if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
            if db.session.query(AttackVersion).count() == 0:
                logger.error("There are no ATT&CK versions installed! Need at least 1 to run! Exiting!")
                sys.exit(1)
    logger.info("Starting the App.")
    app.run(host="0.0.0.0")
