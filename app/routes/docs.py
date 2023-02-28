from flask import Blueprint, render_template, g
import logging

from app.routes.utils import ErrorDuringHTMLRoute, wrap_exceptions_as

logger = logging.getLogger(__name__)
docs_ = Blueprint("docs_", __name__, template_folder="templates")


@docs_.route("/changelog", methods=["GET"])
@wrap_exceptions_as(ErrorDuringHTMLRoute)
def changelog():
    """Returns the changelog (HTML response)"""
    g.route_title = "Change-log Page"

    logger.info("serving page")
    return render_template("change-log.html")
