# Crumbs
# -----------------------------------------------------------------------------------
# start
# start / Tactic Name (ID)
# start / Tactic Name (ID) / Technique Name (ID)
# start / Tactic Name (ID) / TeID Questions
# start / Tactic Name (ID) / TeID Questions / Technique Name (ID) / Subtech Name (ID)

# Meaning                                 URL
# -------------------------------------------------------------
# ROOT                                    /
# Tactic Page                             /tactic
# Subless Technique Page                  /tactic/technique
# Technique Question Page (has subs)      /tactic/technique/QnA
# Technique|Sub Page (for tech with Qs)   /tactic/technique/001

from operator import and_
from flask import Blueprint, redirect, render_template, current_app, g
from app.models import (
    AttackVersion,
    Platform,
    db,
    Tactic,
    Technique,
    Aka,
    Mismapping,
    Blurb,
)
from app.models import (
    technique_aka_map,
    technique_platform_map,
    tactic_technique_map,
)
from sqlalchemy import asc, func, distinct
from sqlalchemy.orm import aliased
from sqlalchemy.dialects.postgresql import array

import logging.config

import re

from app.routes.utils_db import VersionPicker
from app.routes.utils import (
    build_url,
    is_attack_version,
    is_base_tech_id,
    is_tact_id,
    is_tech_id,
    outgoing_markdown,
    checkbox_filters_component
)
from app.routes.utils import ErrorDuringHTMLRoute, wrap_exceptions_as

logger = logging.getLogger(__name__)
question_ = Blueprint("question_", __name__, template_folder="templates")


@question_.route("/", methods=["GET"])
@wrap_exceptions_as(ErrorDuringHTMLRoute)
def home():
    """Decider home-page redirect

    - Logged-in users are redirected to /question on the last version they used
    - Logged-out users are redirected to the /login page
      - This is handled earlier by the absense of the @public_route decorator
    """
    g.route_title = "Base Redirect"

    destination = f"/question/{VersionPicker().cur_version}"

    logger.info(f"redirecting from / to {destination}")
    return redirect(destination, code=302)


def crumb_bar(ids, version_context):
    """Builds the navigation crumb bar and checks that each crumb exists

    ids: list[str] of IDs describing the requested location in the question tree
    possible forms for ids:
    - start                    : start     -> tactic       question page
    - start, tactic            : tactic    -> technique    question page
    - start, tactic, tech      : technique -> subtechnique question page (if tech has subs), else tech success page
    - start, tactic, tech, sub : ----------------------------------------------------------,   subtech success page

    version_context: str of ATT&CK version to pull content from

    returns None if any node is missing
    returns {"breadcrumbs": crumbs} on success
    - crumbs is a list of dicts, each having keys "name", "url"
    """

    # invalid range check
    if not (1 <= len(ids) <= 4):
        logger.error("Crumb Bar: failed - request had too little or too many crumbs (invalid format)")
        return None

    # start always present
    crumbs = [{"name": "start", "url": f"/question/{version_context}"}]

    # tactic if present
    if len(ids) > 1:
        logger.debug(f"Crumb Bar: querying Tactic by ID {ids[1]} ({version_context})")
        tactic = db.session.query(Tactic).filter_by(tact_id=ids[1], attack_version=version_context).first()

        if tactic is None:
            logger.error("Crumb Bar: Tactic does not exist")
            return None
        logger.debug("Crumb Bar: Tactic exists")

        crumbs.append(
            {
                "name": f"{tactic.tact_name} ({tactic.tact_id})",
                "url": build_url(None, tactic.tact_id, version_context),
            }
        )

    # techs if present
    if len(ids) > 2:
        if not all(is_tech_id(t) for t in ids[2:]):
            logger.error("Crumb Bar: failed - request had one or more malformed Techniques")
            return None

        logger.debug(f"Crumb Bar: querying Techs by IDs {ids[2:]} ({version_context})")
        techniques = (
            db.session.query(Technique).filter(
                and_(
                    Technique.tech_id.in_(ids[2:]),
                    Technique.attack_version == version_context,
                )
            )
        ).all()

        if len(techniques) != len(ids[2:]):
            logger.error("Crumb Bar: 1+ Techniques do not exist")
            return None
        logger.debug("Crumb Bar: All Techniques exist")

        techniques.sort(key=lambda t: ids[2:].index(t.tech_id))
        for technique in techniques:
            crumbs.append(
                {
                    "name": f"{technique.tech_name} ({technique.tech_id})",
                    "url": build_url(technique, tactic.tact_id, version_context),
                }
            )

    logger.info("Crumb Bar: successfully built")
    return {"breadcrumbs": crumbs}


def get_mismappings(index, version):
    """Gets all mismappings for a Technique

    index: str TechID of the original Technique to get mismappings for
    version: str of ATT&CK version to pull content from

    returns a list[dict] as described in the comprehension below
    """

    logger.debug(f"Tech Mismappings: querying mismaps of {index} ({version})")

    corrected_tech = aliased(Technique)
    mismappings = (
        #                original   -mismap->   corrected
        db.session.query(Technique, Mismapping, corrected_tech)
        # get original tech from version + tech_id
        .filter(and_(Technique.attack_version == version, Technique.tech_id == index))
        # get all mismaps for it, and the corresponding corrected techniques
        .join(Mismapping, Technique.uid == Mismapping.original).outerjoin(
            corrected_tech, Mismapping.corrected == corrected_tech.uid
        )
    ).all()

    logger.debug(f"got {len(mismappings)} mismaps")

    return [
        {
            "corrected": corrected.tech_id if corrected else None,
            "corrected_techname": corrected.tech_name if corrected else None,
            "url": build_url(corrected, "TA0000", version, end=True),
            "context": mismap.context.replace("\n", "<br>"),
            "rationale": mismap.rationale.replace("\n", "<br>"),
        }
        for _, mismap, corrected in mismappings
    ]


def get_tech_and_subs(index, tactic_context, version_context):
    """Retrieves a Technique and its SubTechniques (if they exist)

    index: str of TechID, can also be a SubTechID, the base Tech is located and the group of Base+Subs is grabbed
    tactic_context: str of TacticID that the Technique lives under
    version_context: str of ATT&CK version to pull content from

    returns a tuple of (Base Technique object, dict)
    - dict holding the keys "rows" and "selected"
    - "rows" being a list[dict], each with keys "id", "name", "url" describing each technique in the base+subs group
    - "selected" being an int that is the index of the current row being requested **

    ** This makes "Technique & Sub-Techniques" on the success page, allowing quick jumping between subs/base
    """

    # Get base Technique, query Technique & Subs
    base_technique = index.split(".")[0]

    logger.debug(f"querying Tech & Subs of {base_technique} ({version_context})")
    tech_and_subs = (
        db.session.query(Technique)
        .filter(Technique.tech_id.contains(base_technique))  # get all entries for base_technique
        .filter(Technique.attack_version == version_context)
        .order_by(asc(Technique.tech_id))  # asc tech_id: (base_tech, sub001, sub002, ...)
    ).all()

    number_of_subs = sum(1 for t in tech_and_subs if ("." in t.tech_id))
    logger.debug(f"got {number_of_subs} sub-Techs")

    # Get current selected Technique and its place in
    # the Technique/Subs list; Make dict for Jinja template
    technique, view_index = [(t, ind) for ind, t in enumerate(tech_and_subs) if t.tech_id == index][0]
    tech_and_subs = {
        "selected": view_index,
        "rows": [
            {
                "id": t.tech_id.split(".")[-1],  # Trims base Technique ID off for all sub techniques
                "name": t.tech_name,
                "url": build_url(
                    t,
                    tactic_context,
                    version_context,
                    is_base_tech_id(t.tech_id),
                ),
            }
            for t in tech_and_subs
        ],
    }
    return technique, tech_and_subs


def get_examples(index, version):
    """Retrieves example CTI reports where a Technique has been mapped before

    index: str of TechID of technique to get reports for
    version: str of ATT&CK version to pull content from

    returns list[dict], each dict having keys "file_name", "url", "sentence"
    """
    logger.debug(f"querying CTI examples of {index} ({version})")
    blurbs = (
        db.session.query(Blurb)
        .join(Technique, Technique.uid == Blurb.technique)
        .filter(and_(Technique.tech_id == index, Technique.attack_version == version))
        .order_by(asc(Blurb.uid))
    ).all()
    logger.debug(f"got {len(blurbs)} examples")

    blurbs = [
        {
            "file_name": b.file_name,
            "url": b.url,
            "sentence": outgoing_markdown(b.sentence),
        }
        for b in blurbs
    ]

    logger.info("successfully collected examples")
    return blurbs


# ---------------------------------------------------------------------------------------------------------------------
# Question Page & Helpers - Normal Navigation & Tactic-less Success Page


def question_page_vars(cur_node, index, tactic_context, version_context):
    """Generates variables needed for the Jinja question page template

    cur_node
    - the parent (question) node for the page
    - possible types:
      - Tactic object
      - Technique object
      - a dict representing index="start" that just has a "question" key

    index (str)
    - possible formats:
      - TA[0-9]{4}
      - T[0-9]{4}
      - "start"

    tactic_context (None, str)
    - None when index="start", as we are not under a Tactic yet
    - otherwise str of TacticID of cur_node itself (node is tact), or the parent of cur_node (node is tech)

    version_context: str of ATT&CK version to pull content from
    """

    # Get version - make platform filters for it
    logger.debug(f"querying Platforms and Data Sources in version {version_context}")
    ver = AttackVersion.query.get(version_context)
    ver_platforms = ver.platforms
    ver_data_sources = ver.data_sources
    logger.debug(f"got {len(ver_platforms)} Platforms and {len(ver_data_sources)} Data Sources")

    platform_filters = checkbox_filters_component(
        "platform",
        [p.readable_name for p in ver_platforms],  # platform names
        "questionClearPlatforms()",
        "questionUpdatePlatforms(this)",
    )
    data_source_filters = checkbox_filters_component(
        "data_source",
        [s.readable_name for s in ver_data_sources],
        "questionClearDataSources()",
        "questionUpdateDataSources(this)",
        different_name="data Source",
    )

    if is_tact_id(index):
        question = outgoing_markdown(cur_node.tact_question)
    elif is_tech_id(index):
        question = outgoing_markdown(cur_node.tech_question)
    else:
        question = cur_node["question"]

    return {
        "question": {
            "question": question,
            "id": index,
            "tactic": tactic_context,
            "attack_version": version_context,
        },
        **platform_filters,
        **data_source_filters,
    }


def success_page_vars(index, tactic_context, version_context):
    """Generates variables needed for the Jinja success page template

    index: str of TechID that the success page is for

    tactic_context: str of TacticID the technique lives under
    - techniques can live under multiple tactics, but this is the tactic we navigated through to get to the technique

    version_context: str of the ATT&CK version to pull content from
    """

    # creates sub / base technique selector section
    technique, tech_and_subs = get_tech_and_subs(index, tactic_context, version_context)

    # get tactics, platforms, and akas for the current technique
    logger.debug(f"querying Tactics, Platforms, and AKAs of {index} ({version_context})")
    _, tact_ids_names, platforms, akas = (
        db.session.query(
            Technique,  # 0
            func.array_agg(distinct(array([Tactic.tact_id, Tactic.tact_name]))),  # 1
            func.array_agg(distinct(Platform.readable_name)),  # 2
            func.array_remove(func.array_agg(distinct(Aka.term)), None),  # 3
        )
        .filter(
            and_(
                Technique.attack_version == version_context,
                Technique.tech_id == technique.tech_id,
            )
        )
        .join(tactic_technique_map, tactic_technique_map.c.technique == Technique.uid)
        .join(Tactic, Tactic.uid == tactic_technique_map.c.tactic)
        .outerjoin(technique_platform_map, technique_platform_map.c.technique == Technique.uid)
        .outerjoin(Platform, Platform.uid == technique_platform_map.c.platform)
        .outerjoin(technique_aka_map, technique_aka_map.c.technique == Technique.uid)
        .outerjoin(Aka, technique_aka_map.c.aka == Aka.uid)
        .group_by(Technique.uid)
    ).first()
    logger.debug(f"got {len(tact_ids_names)} Tactics, {len(platforms)} Platforms, and {len(akas)} AKAs")

    # generate dropdown options for tactic selector
    #   this allows selecting which tactic the technique gets added to the cart under
    tactic_entries = [
        {
            "tact_id": tact_id,
            "tact_name": tact_name,
            "tech_url_for_tact": build_url(technique, tact_id, version_context, True),
        }
        for tact_id, tact_name in tact_ids_names
    ]

    # create jinja vars
    return {
        "success": {
            "id": index,
            "name": technique.tech_name,
            "description": outgoing_markdown(technique.tech_description),
            "akas": akas,
            "blurbs": get_examples(index, version_context),
            "url": technique.tech_url,
            "platforms": platforms,
            "tactics": tactic_entries,
            "mismappings": get_mismappings(index, version_context),
            "tech_and_subs": tech_and_subs,
            "tactic_context": tactic_context,
            "version": version_context,
        }
    }


@question_.route("/question/", methods=["GET"])
@question_.route("/question/<version>", methods=["GET"])
@wrap_exceptions_as(ErrorDuringHTMLRoute)
def question_start_page(version=None):
    """Route of Decider's "home" question page (start -> tactics) (HTML response)

    version: str of ATT&CK version to pull content from
    """
    g.route_title = "Start -> Tactics Question Page"

    # validate version / derive from last used
    if version:
        if not is_attack_version(version):
            logger.error("failed - request had a malformed ATT&CK version")
            return render_template("status_codes/404.html"), 404

        logger.debug(f"querying existence of version {version}")

    version_pick = VersionPicker(version=version)
    if not version_pick.set_vars():
        logger.error("requested ATT&CK version does not exist")
        return render_template("status_codes/404.html"), 404
    version_context = version_pick.cur_version

    if version:
        logger.debug("requested ATT&CK version exists")
    else:
        logger.debug(f"version not provided in URL, using user's last used version {version_context}")

    # top bar and page for question root
    crumbs = crumb_bar(["start"], version_context)
    cur_node = {"question": current_app.config["START_QUESTION"]}

    qna = question_page_vars(cur_node, "start", None, version_context)

    logger.info("serving page")
    return render_template("questionlist.html", **qna, **crumbs)


@question_.route("/question/<version>/<tactic_id>", methods=["GET"])
@wrap_exceptions_as(ErrorDuringHTMLRoute)
def question_tactic_page(version, tactic_id):
    """Route of Tactic -> Techniques question page (HTML response)

    version: str of ATT&CK version to pull content from

    tactic_id: str of TacticID of Tactic that is the root (question) of the page
    """
    g.route_title = "Tactic -> Techniques Question Page"

    # validate version given
    if not is_attack_version(version):
        logger.error("failed - request had a malformed ATT&CK version")
        return render_template("status_codes/404.html"), 404

    logger.debug(f"querying existence of version {version}")
    version_pick = VersionPicker(version=version)
    if not version_pick.set_vars():
        logger.error("requested ATT&CK version does not exist")
        return render_template("status_codes/404.html"), 404
    version_context = version_pick.cur_version
    logger.debug("requested ATT&CK version exists")

    # validate tactic
    if not is_tact_id(tactic_id):
        logger.error("request failed - it had a malformed Tactic ID")
        return render_template("status_codes/404.html"), 404

    # crumbs for bar (checks tactic existence as well)
    crumbs = crumb_bar(["start", tactic_id], version_context)
    if crumbs is None:
        logger.error(f"request for Tactic {tactic_id} failed - Tactic does not exit in version {version_context}")
        return render_template("status_codes/404.html"), 404

    # tactic exists as crumb bar formation validated it
    logger.debug(f"querying Tactic {tactic_id} ({version_context})")
    cur_node = db.session.query(Tactic).filter_by(attack_version=version_context, tact_id=tactic_id).first()
    logger.debug("query done")

    qna = question_page_vars(cur_node, tactic_id, tactic_id, version_context)

    logger.info("serving page")
    return render_template("questionlist.html", **qna, **crumbs)


@question_.route("/question/<version>/<tactic_id>/<path:dest>", methods=["GET"])
@wrap_exceptions_as(ErrorDuringHTMLRoute)
def question_further_page(version, tactic_id, dest=""):
    """Route of base-tech success, sub-tech success, or base->sub tech question page (HTML response)

    version: str of ATT&CK version to pull content from
    tactic_id: str of TacticID that is the parent of the Tech/SubTechs we are visiting

    dest: str path describing resource being accessed
    dest formats and their meaning:
    - T[0-9]{4}/          : success page for Technique
    - T[0-9]{4}/[0-9]{3}/ : success page for SubTechnique
    - T[0-9]{4}/QnA/      : question page from Technique to its Subs
    """
    g.route_title = "Tech -> Sub Question / Success Page"

    # validate version given
    if not is_attack_version(version):
        logger.error("failed - request had a malformed ATT&CK version")
        return render_template("status_codes/404.html"), 404

    logger.debug(f"querying existence of version {version}")
    version_pick = VersionPicker(version=version)
    if not version_pick.set_vars():
        logger.error("requested ATT&CK version does not exist")
        return render_template("status_codes/404.html"), 404
    version_context = version_pick.cur_version
    logger.debug("requested ATT&CK version exists")

    # determine target: "TNNNN", "TNNNN/QnA", "TNNNN/NNN"
    dest_parts = dest.strip().strip("/").split("/")
    if len(dest_parts) == 1:  # base tech page
        technique_id = dest_parts[0]
        sub = None
    elif len(dest_parts) == 2:  # sub tech / tech->sub question
        technique_id, sub = dest_parts
    else:  # invalid length
        logger.error(
            "request URL was malformed - only expecting 1 or 2 "
            "tokens after Tactic ID (valid forms: 'Tabcd', 'Tabcd/QnA', 'Tabcd/xyz')"
        )
        return render_template("status_codes/404.html"), 404

    # validate Tactic, Technique, and SubTechnique fit expected formats
    attack_id_checks = [
        is_tact_id(tactic_id),
        is_base_tech_id(technique_id),
        re.fullmatch(r"QnA|[0-9]{3}", sub) if (sub is not None) else True,
    ]
    if any(x is None for x in attack_id_checks):
        logger.error("request URL contained malformed ATT&CK IDs")
        return render_template("status_codes/404.html"), 404

    # form crumb bar (validates node existence too)
    if (sub is None) or (sub == "QnA"):
        crumb_ids = ["start", tactic_id, technique_id]
    else:  # sub is [0-9]{3} format
        crumb_ids = ["start", tactic_id, technique_id, f"{technique_id}.{sub}"]
    index = crumb_ids[-1]
    crumbs = crumb_bar(crumb_ids, version_context)
    if crumbs is None:
        logger.error(f"request URL contained ATT&CK IDs that do not exist under {version_context}")
        return render_template("status_codes/404.html"), 404

    # no end path -> base tech success
    # [0-9]{3} end -> sub tech success
    if (sub is None) or re.fullmatch(r"[0-9]{3}", sub):
        success = success_page_vars(index, tactic_id, version_context)
        logger.info("serving page")
        return render_template("success.html", **success, **crumbs)

    # known: sub = QnA -> Tech->SubTech question page .. if question exists
    logger.debug(f"querying Technique {technique_id} under ATT&CK {version_context}")
    cur_node = db.session.query(Technique).filter_by(attack_version=version_context, tech_id=technique_id).first()
    logger.debug("query done")

    if cur_node.tech_question:
        qna = question_page_vars(cur_node, index, tactic_id, version_context)
        logger.info("serving page")
        return render_template("questionlist.html", **qna, **crumbs)

    # requesting question page for tech without a question (has no subs) -> 404
    logger.error(
        "failed - user requested '/QnA' a (Tech -> SubTech) question page for"
        "a Technique without Sub-Techniques - sending 404"
    )
    return (
        render_template(
            "status_codes/404.html",
            reason_for_404=(
                "This Technique has no Sub-Techniques. You requested /QnA, which is the question page "
                "that would lead to this Technique's Sub-Techniques. Please remove the /QnA from the URL."
            ),
        ),
        404,
    )


@question_.route("/no_tactic/<version>/<path:subpath>", methods=["GET"])
@wrap_exceptions_as(ErrorDuringHTMLRoute)
def notactic_success(version, subpath=""):
    """Route of (Sub/)Technique success page without a tactic context (HTML response)

    The utility of a success page without a Tactic context is in search results.
    A user searching for a certain keyword / behavior can land on a (Sub/)Technique page.
    However, the goal the adversary had was not yet considered.
    The user can select what Tactic (goal) applies on this page to allow adding it to their cart.

    version: str of ATT&CK version to pull content from

    subpath: str path describing resource being accessed
    subpath formats and their meaning:
    - T[0-9]{4}/         : Technique no-tactic success page
    - T[0-9]{4}/[0-9]{3} : SubTechnique no-tactic success page
    """
    g.route_title = "No-Tactic Success Page"

    path = subpath.strip().strip("/").split("/")

    if not is_attack_version(version):
        logger.error("failed - request contained a malformed ATT&CK version")
        return render_template("status_codes/404.html"), 404

    logger.debug(f"querying existence of version {version}")
    version_pick = VersionPicker(version=version)
    if not version_pick.set_vars():
        logger.error("requested ATT&CK version does not exists")
        return render_template("status_codes/404.html"), 404
    logger.debug("requested ATT&CK version exists")

    version_context = version_pick.cur_version

    # doesn't match Tabcd(/xyz) -> 404
    if re.fullmatch(r"T[0-9]{4}(\/[0-9]{3})?", subpath) is None:
        logger.error("failed - request had a malformed TechID path - it should be of the form 'Tabcd(/xyz)'")
        return (
            render_template(
                "status_codes/404.html",
                reason_for_404="The requested Technique does not match the form: Tabcd(.xyz)",
            ),
            404,
        )

    tactic_context = "TA0000"
    technique = f"{path[0]}.{path[1]}" if (len(path) > 1) else path[-1]

    if not is_tech_id(technique):
        logger.error("failed - request had a malformed Technique ID")
        return render_template("status_codes/404.html"), 404

    # if Technique doesn't exist (version change can cause this) -> 404
    logger.debug(f"querying exitence of {technique} in ATT&CK {version_context}")
    cur_node = db.session.query(Technique).filter_by(attack_version=version_context, tech_id=technique).first()

    if cur_node is None:
        logger.error(f"{technique} in ATT&CK {version_context} does not exist")
        return (
            render_template(
                "status_codes/404.html",
                reason_for_404="The requested Technique does not exist for this ATT&CK version",
            ),
            404,
        )
    logger.debug(f"{technique} in ATT&CK {version_context} exists")

    success = success_page_vars(technique, tactic_context, version_context)

    logger.info("serving page")
    return render_template("no_tactic_success.html", **success)
