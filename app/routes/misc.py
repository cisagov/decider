from flask import Blueprint, request, send_from_directory, jsonify, render_template, g

import logging

from collections import defaultdict

from sqlalchemy import func, tuple_
from sqlalchemy.dialects.postgresql import array, aggregate_order_by

from app.models import db, Tactic, Technique, tactic_technique_map

from app.routes.utils import DictValidator, is_attack_version, is_tact_id, is_tech_id
from app.routes.utils import ErrorDuringHTMLRoute, ErrorDuringAJAXRoute, wrap_exceptions_as
from app.routes.utils_db import VersionPicker
from app.version import DECIDER_APP_VERSION

logger = logging.getLogger(__name__)
misc_ = Blueprint("misc_", __name__)


@misc_.route("/favicon.ico", methods=["GET"])
@wrap_exceptions_as(ErrorDuringAJAXRoute)
def favicon():
    """Returns the static Decider favicon"""
    return send_from_directory("app/static", "favicon.ico", mimetype="image/vnd.microsoft.icon")


@misc_.route("/suggestions/<version>", methods=["GET"])
@wrap_exceptions_as(ErrorDuringHTMLRoute)
def suggestions(version):
    """Route providing CoOccurrence suggestions based upon the contents of the user's cart (HTML response)

    version: str of ATT&CK version to pull content from
    """
    g.route_title = "Cartwide CoOccurrences Page"

    if not is_attack_version(version):
        logger.error("failed - request has a malformed ATT&CK version")
        return render_template("status_codes/404.html"), 404

    logger.debug(f"checking if version {version} exists")
    if not VersionPicker(version=version).set_vars():
        logger.error("requested ATT&CK version does not exist")
        return render_template("status_codes/404.html"), 404
    logger.debug("requested ATT&CK version exists")

    logger.info("serving page")
    return render_template("multi-cooccurrences.html")


def is_cart_entry_format_valid(entry):

    if not isinstance(entry, dict):
        return False

    dv = DictValidator(
        entry,
        {
            "index": dict(type_=str, validator=is_tech_id),
            "tactic": dict(type_=str, validator=is_tact_id),
            "notes": dict(type_=str, optional=True),
            # unused in report building - must be mentioned for DictValidator
            "name": dict(type_=str, optional=True),
            "tacticName": dict(type_=str, optional=True),
        },
    )

    return dv.success


def is_cart_format_valid(cart):

    if not isinstance(cart, dict):
        return False

    dv = DictValidator(
        cart,
        {
            "title": dict(type_=str, optional=True),
            "version": dict(type_=str),
            "entries": dict(type_=list, validator=lambda es: all((is_cart_entry_format_valid(e) for e in es))),
        },
    )

    return dv.success


def query_db_for_cart_content(cart):

    id_pairs = set()
    for entry in cart["entries"]:
        id_pairs.add((entry["tactic"], entry["index"]))

    # Tactics in matrix-order
    # listing their Techniques in 'Base: Sub' name alphabetical order
    # filtered by cart version + entries
    tacts_and_techs = (
        db.session.query(
            Tactic.tact_id,
            Tactic.tact_name,
            Tactic.tact_url,
            func.array_agg(
                aggregate_order_by(
                    array([Technique.tech_id, Technique.full_tech_name, Technique.tech_url]), Technique.full_tech_name
                )
            ),
        )
        # match cart version
        .filter(Tactic.attack_version == cart["version"])
        # join Techs
        .join(tactic_technique_map, tactic_technique_map.c.tactic == Tactic.uid)
        .join(Technique, tactic_technique_map.c.technique == Technique.uid)
        # match cart version (redundant)
        .filter(Technique.attack_version == cart["version"])
        # filter to cart contents
        .filter(tuple_(Tactic.tact_id, Technique.tech_id).in_(id_pairs))
        # matrix-order and aggregate Techs into Tact groups
        .order_by(Tactic.uid)
        .group_by(Tactic.uid)
    ).all()

    tacts_and_techs = [list(row) for row in tacts_and_techs]

    return tacts_and_techs


def is_query_db_for_cart_successful(cart, tacts_and_techs):

    db_tact_to_techs = defaultdict(set)
    for tact_id, _, _, techs in tacts_and_techs:
        for tech_id, _, _ in techs:
            db_tact_to_techs[tact_id].add(tech_id)

    # checks that each entry's Tact-Tech pair exists (in the version queried)
    for entry in cart["entries"]:
        tech_id = entry["index"]
        tact_id = entry["tactic"]
        if tech_id not in db_tact_to_techs[tact_id]:
            return False

    return True


@misc_.route("/word_export", methods=["POST"])
@wrap_exceptions_as(ErrorDuringAJAXRoute)
def export_cart_to_word():
    """Returns data (Tech/Tacts ID/Name/URLs in sorted order) to help with MS Docx report generation
       given a users cart (posted data)

    JSON request:
    - dict with at least "version" and "entries" keys ("title" optional)
    - version being an ATT&CK version the entries are for
    - entries being a list of dicts (items in the cart)
      - each entry has keys: "index", "tactic"
      - optional entry keys: "notes", "tacticName", "name"

    JSON response:
    - data is sent back instead of a file as JavaScript docx is now used instead of python-docx
      - has support for links & coloration without making you manage raw XML
    - data structure below
      - appVersion is just the app version string - allowing marking it in the report header
      - usages is a lookup allowing all entry notes to be accessed by Tact+Tech
      - tactsAndTechs's root level is in matrix tactic order
        - techniques within a tactic are in name alphabetical order
    {
        appVersion: "1.0.0",

        usages: {
            "tactId--techId": [
                "Mapping rationale 1",
                "Mapping rationale 2",
                ...
            ],
            ...
        },

        tactsAndTechs: [
            ...,
            [tactId, tactName, tactUrl, [
                [techId, techName, techUrl],
                [techId, techName, techUrl],
                ...
            ]],
            ...
        ]
    }
    """
    g.route_title = "Export Cart as Docx"

    # grab cart & validate structure
    try:
        cart = request.json
        if not is_cart_format_valid(cart):
            raise Exception("cart format invalid")
        if len(cart["entries"]) == 0:
            raise Exception("cart is empty")
    except Exception:
        logger.warning("request body missing, or misshaped, or 0 entries - malformed request")
        return jsonify(message="Failed to make report - malformed request."), 400

    # query DB for cart entries & check that all were located
    tacts_and_techs = query_db_for_cart_content(cart)
    if not is_query_db_for_cart_successful(cart, tacts_and_techs):
        logger.warning("cart contained 1+ invalid Tactic-Technique combinations - malformed request")
        return jsonify(message="Failed to make report - malformed request."), 400

    # index usages for fast grab in doc building
    lookup_usages = defaultdict(list)
    for entry in cart["entries"]:
        tact_id = entry["tactic"]
        tech_id = entry["index"]
        usage = entry.get("notes", "") or "-"  # handles missing / blank
        lookup_usages[f"{tact_id}--{tech_id}"].append(usage)

    return jsonify(tactsAndTechs=tacts_and_techs, usages=lookup_usages, appVersion=DECIDER_APP_VERSION)
