import logging
from app.models import CoOccurrence, Platform, db, Tactic, Technique, Mismapping, AttackVersion, DataSource
from app.models import technique_platform_map, tactic_technique_map, tactic_ds_map, technique_ds_map

from app.routes.utils import (
    build_url,
    is_attack_version,
    is_base_tech_id,
    is_tact_id,
    is_tech_id,
    outgoing_markdown,
    trim_keys,
    DictValidator,
)
from app.routes.utils import ErrorDuringAJAXRoute, wrap_exceptions_as

from flask import Blueprint, request, current_app, jsonify, g

from flask_login import current_user
from sqlalchemy import asc, func, distinct, and_, or_, literal_column
from sqlalchemy.dialects.postgresql import array
from sqlalchemy.orm.util import aliased

logger = logging.getLogger(__name__)

api_ = Blueprint("api_", __name__)


@api_.route("/api/versions", methods=["GET"])
@wrap_exceptions_as(ErrorDuringAJAXRoute)
def get_versions():
    """Returns a list of strings of ATT&CK versions installed on the server (JSON response)"""
    g.route_title = "Get ATT&CK Versions Installed"

    logger.info("querying versions")

    version_objs = db.session.query(AttackVersion).all()
    version_strs = [v.version for v in version_objs]

    logger.debug(f"got {len(version_strs)} versions installed: {', '.join(version_strs)}")

    return jsonify(version_strs), 200


@api_.route("/api/mismappings", methods=["GET"])
@wrap_exceptions_as(ErrorDuringAJAXRoute)
def get_mismappings():
    """Returns all mismappings for a Technique under an ATT&CK version

    url-based request: .../api/mismappings?version=VERSION&technique=TECH_ID
    JSON response
    """
    g.route_title = "Get Technique's Mismappings"

    version = request.args.get("version")
    technique = request.args.get("technique")

    # validate request arguments
    if (version is None) or (not is_attack_version(version)):
        logger.error("request failed - ATT&CK version field missing / malformed")
        return jsonify(message="'version' field missing / malformed"), 400

    if (technique is None) or (not is_tech_id(technique)):
        logger.error("request failed - Technique ID field missing / malformed")
        return jsonify(message="'technique' field missing / malformed"), 400

    logger.info(f"querying Mismappings of {technique} ({version})")

    technique_alias = aliased(Technique)
    mismappings = (
        db.session.query(Mismapping, Technique, technique_alias)
        .outerjoin(Technique, Mismapping.original == Technique.uid)
        .outerjoin(technique_alias, Mismapping.corrected == technique_alias.uid)
        .filter(Technique.tech_id == technique)
        .filter(Technique.attack_version == version)
    ).all()

    logger.debug(f"got {len(mismappings)} Mismappings")

    # converts the query objects to an array
    mismappings = [
        {
            "original": {
                "technique_id": original.tech_id,
                "technique_name": original.tech_name,
                "uid": original.uid,
            },
            "corrected": {
                "technique_id": corrected.tech_id,
                "technique_name": corrected.tech_name,
                "uid": corrected.uid,
            }
            if corrected is not None
            else None,
            "context": mismap.context,
            "rationale": mismap.rationale,
            "uid": mismap.uid,
        }
        for mismap, original, corrected in mismappings
    ]
    return jsonify(mismappings), 200


@api_.route("/api/tactics", methods=["GET"])
@wrap_exceptions_as(ErrorDuringAJAXRoute)
def get_tactics():
    """Returns all Tatics for a given ATT&CK version, including all fields or a subset if specified

    version is required
    fields[] is optional
    - its absence means all fields are returned
    - invalid fields are ignored
    - specifying only invalid fields yields a list of empty dictionaries

    url-based request: .../api/tactics?version=VERSION&fields[]=FIELD_NAME_1&fields[]=FIELD_NAME_2
    JSON response
    """
    g.route_title = "Get Tactics in Version"

    query_fields = set(request.args.getlist("fields[]"))
    version = request.args.get("version")

    # validate request
    if (version is None) or (not is_attack_version(version)):
        logger.error("request failed - version field missing / malformed")
        return jsonify(message="'version' field missing / malformed"), 400

    logger.info(f"querying Tactics under {version}")

    tactics = (
        db.session.query(Tactic, func.array_agg(array([Technique.tech_id, Technique.tech_name])))
        .order_by(asc(Tactic.uid))
        .filter(Tactic.attack_version == version)
        .join(tactic_technique_map, tactic_technique_map.c.tactic == Tactic.uid)
        .join(Technique, Technique.uid == tactic_technique_map.c.technique)
        .group_by(Tactic.uid)
    ).all()

    logger.debug(f"got {len(tactics)} Tactics")

    dictified = [
        {
            "uid": tactic.uid,
            "tactic_id": tactic.tact_id,
            "tactic_name": tactic.tact_name,
            "url": f"/question/{version}/{tactic.tact_id}",
            "techniques": [{"technique_id": technique[0], "technique_name": technique[1]} for technique in techniques],
        }
        for tactic, techniques in tactics
    ]

    trimmed = trim_keys(query_fields, dictified)
    return jsonify(trimmed), 200


@api_.route("/api/techniques", methods=["GET"])
@wrap_exceptions_as(ErrorDuringAJAXRoute)
def get_techniques():
    """Returns all Techniques for a given ATT&CK version, including all fields or a subset if specified

    version is required
    fields[] is optional
    - its absence means all fields are returned
    - invalid fields are ignored
    - specifying only invalid fields yields a list of empty dictionaries

    url-based request: .../api/techniques?version=VERSION&fields[]=FIELD_NAME_1&fields[]=FIELD_NAME_2
    JSON response
    """
    g.route_title = "Get Techniques in Version"

    # Fields for entries to have (columns)
    query_fields = set(request.args.getlist("fields[]"))
    version = request.args.get("version")

    # validate request
    if (version is None) or (not is_attack_version(version)):
        logger.error("request failed - version field missing / malformed")
        return jsonify(message="'version' field missing / malformed"), 400

    logger.info(f"querying Techniques under {version}")

    # get Techniques from database and dictify
    techs_tacts_platforms = (
        db.session.query(
            Technique,
            func.array_agg(array([Tactic.tact_id, Tactic.tact_name, Tactic.tact_url])),
            func.array_agg(distinct(Platform.readable_name)),
        )
        .order_by(asc(Technique.tech_id))
        .join(tactic_technique_map, tactic_technique_map.c.technique == Technique.uid)
        .join(Tactic, Tactic.uid == tactic_technique_map.c.tactic)
        .outerjoin(technique_platform_map, technique_platform_map.c.technique == Technique.uid)
        .outerjoin(Platform, Platform.uid == technique_platform_map.c.platform)
        .distinct(Technique.tech_id)
        .group_by(Technique.uid)
    ).all()

    logger.debug(f"got {len(techs_tacts_platforms)} Techniques")

    dictified = [
        {
            "technique_id": tech.tech_id,
            "technique_name": tech.tech_name,
            "attack_url": tech.tech_url,
            "decider_url": build_url(tech, "TA0000", version),  # /no_tactic/ URLs, implicit end=True
            "description": tech.tech_description,
            "platforms": platforms,
            "uid": tech.uid,
            "tactics": [{"tactic_id": tact[0], "tactic_name": tact[1], "attack_url": tact[2]} for tact in tactics],
        }
        for tech, tactics, platforms in techs_tacts_platforms
    ]

    trimmed = trim_keys(query_fields, dictified)
    return jsonify(trimmed), 200


@api_.route("/api/user_version_change", methods=["PATCH"])
@wrap_exceptions_as(ErrorDuringAJAXRoute)
def user_version_change():
    """Updates the last used ATT&CK version for a logged-in user (JSON request, JSON response)"""
    g.route_title = "Update Personal ATT&CK Version In-Use"

    try:
        data = request.json
        if not isinstance(data, dict):
            raise Exception()
    except Exception:
        logger.error("request failed - malformed data type")
        return jsonify(message="Request was malformed"), 400

    # ensure request for version change is valid
    spec = {"new_version": dict(type_=str, validator=lambda nv: AttackVersion.query.get(nv) is not None)}
    check = DictValidator(data, spec)
    if not check.success:
        logger.error(f"failed - malformed request: {check.errors}")
        return jsonify(message="\n".join(check.errors)), 400

    version_change_text = f"{current_user.last_attack_ver} -> {data['new_version']}"

    # update
    try:
        logger.debug(f"attempt to update version in-use {version_change_text}")
        current_user.last_attack_ver = data["new_version"]
        db.session.commit()

    except Exception:
        db.session.rollback()
        logger.exception(f"failed to update version in-use {version_change_text}")
        return jsonify(status="Failed to update user's att&ck version selection"), 500

    logger.info(f"successfully updated version in-use {version_change_text}")
    return jsonify(status="Successfully updated user's att&ck version selection"), 200


@api_.route("/api/techid_to_valid_tactid_map/<version>", methods=["GET"])
@wrap_exceptions_as(ErrorDuringAJAXRoute)
def techid_to_valid_tactid_map(version):
    """Returns a dict that maps a TechID to a valid TacticID for it

    - This returns all entries and is intended to be called once just after page load
    - One use is for the Technique answer card editing page
      1. User searches for a TechID they want to edit
      2. This mapping gives them a valid TactID to use with it
      3. The correct tabs are clicked to open the editing box specified
    """
    g.route_title = "Get TechID to Valid TactID Mapping"

    # validate format
    if not is_attack_version(version):
        logger.error("A malformed ATT&CK version was requested")
        return jsonify(message="ATT&CK version malformed"), 400

    # validate existence
    logger.debug(f"Checking ATT&CK version existence: {version}")
    if AttackVersion.query.get(version) is None:
        logger.error(f"Checking ATT&CK version existence: {version} - doesn't exist")
        return jsonify(message="ATT&CK version doesn't exist"), 404
    logger.debug(f"Checking ATT&CK version existence: {version} - it exists")

    # query valid Tactic for each Tech
    logger.debug("Running query for all TechID -> (1st)TactID")
    techid_tactid = (
        db.session.query(Technique.tech_id, literal_column("(array_agg(distinct(tactic.tact_id)))[1]"))
        .group_by(Technique.tech_id)
        .filter(Technique.attack_version == version)
        .join(tactic_technique_map, Technique.uid == tactic_technique_map.c.technique)
        .join(Tactic, Tactic.uid == tactic_technique_map.c.tactic)
    ).all()
    logger.debug("Query finished")

    techid_to_tactid = {tech_id: tact_id for tech_id, tact_id in techid_tactid}
    logger.info("Sending mapping to user")
    return jsonify(techid_to_tactid)


# ---------------------------------------------------------------------------------------------------------------------
# Answers Data [GET] & Helper Functions


@api_.route("/api/answers/", methods=["GET"])
@wrap_exceptions_as(ErrorDuringAJAXRoute)
def answers_api():
    """Provides the answer cards for a given position in the question tree

    index
    - is always required
    -      start means the root of the tree
    - TA[0-9]{4} means a Tactic leading to Techniques
    -  T[0-9]{4} means a Technique leading to SubTechniques

    tactic
    - only needed when index=T[0-9]{4} (a Technique)
    - a Technique can live under multiple Tactics, so this specifies that

    version
    - is always required
    - is the ATT&CK version in which to lookup content from

    url-based request: .../api/answers/?index=INDEX&tactic=TACTIC_ID&version=VERSION
    JSON response
    """
    g.route_title = "Get Answer Cards"

    index = request.args.get("index", "")
    tactic_context = request.args.get("tactic", "")
    version_context = request.args.get("version", "")

    # validate version
    if not is_attack_version(version_context):
        logger.error("request failed - version field malformed")
        return jsonify(message="'version' field malformed"), 400

    args = (index, tactic_context, version_context)

    # start -> tactics
    if index == "start":
        answers = answers_api_start(args)
        logger.info("queried start -> Tactic answer cards")

    # tactic -> techniques
    elif is_tact_id(index):
        answers = answers_api_tactic(args)
        logger.info("queried Tactic -> Technique answer cards")

    # technique -> subtechs / self
    elif is_base_tech_id(index):

        # validate tactic
        if not is_tact_id(tactic_context):
            logger.error("request failed - tactic field malformed")
            return jsonify(message="'tactic' field malformed"), 400

        answers = answers_api_technique(args)
        logger.info("queried Technique -> Sub-Technique answer cards")

    # unknown, bad request
    else:
        logger.error("failed - malformed request")
        return (
            jsonify(message='index must be "start", a Tactic ID, or a Technique ID (no SubTechniques allowed).'),
            400,
        )

    logger.debug(f"got {len(answers)} answer cards")
    return jsonify(answers), 200


# start -> tactics
def answers_api_start(args):
    """Returns the Tactic answer cards at the root (index=start) of the tree for a given version

    Input:
    - args = (_, _, version_context)
    - version_context being the version of ATT&CK to get this content from

    Output:
    - a list of dicts
    - in ATT&CK Enterprise Tactic order
    """

    _, _, version_context = args

    # query Tactics, their # of children, and their associated platforms / data sources
    logger.debug(f"querying start -> Tactic answer cards under ATT&CK {version_context}")
    items = (
        db.session.query(
            Tactic,
            func.count(distinct(Technique.uid)),
            func.array_agg(distinct(Platform.internal_name)),
            func.array_agg(distinct(DataSource.internal_name)),
        )
        .filter(Tactic.attack_version == version_context)
        .join(tactic_technique_map, tactic_technique_map.c.tactic == Tactic.uid)
        .join(Technique, tactic_technique_map.c.technique == Technique.uid)
        .filter(Technique.parent_uid == None)
        .join(
            technique_platform_map,
            technique_platform_map.c.technique == Technique.uid,
        )
        .join(Platform, technique_platform_map.c.platform == Platform.uid)
        .outerjoin(tactic_ds_map, tactic_ds_map.c.tactic == Tactic.uid)
        .outerjoin(DataSource, tactic_ds_map.c.data_source == DataSource.uid)
        .group_by(Tactic.uid)
    ).all()

    # form answers
    answers = [
        {
            "id": tactic.tact_id,
            "content": outgoing_markdown(tactic.tact_answer or ""),
            "name": tactic.tact_name,
            "url": tactic.tact_url,
            "path": build_url(None, tactic.tact_id, version_context),
            "platforms": platforms,
            "num": num,
            "data_sources": data_sources,
        }
        for tactic, num, platforms, data_sources in items
    ]

    # order Tactic answers by their ATT&CK ordering
    tact_id_to_uid = {tact.tact_id: tact.uid for tact, *_ in items}
    answers.sort(key=lambda ans: tact_id_to_uid[ans["id"]])
    return answers


# tactic -> techniques
def answers_api_tactic(args):
    """Returns the Technique answer cards living under a Tactic for a given version

    Input:
    - args = (index, _, version_context)
    - index being the Tactic ID to get Technique answer cards for
    - version_context being the version of ATT&CK to get this content from

    Output:
    - a list of dicts
    - in alphabetical order by Technique name
    """

    index, _, version_context = args

    # query Techniques, their # of children, and their associated platforms / data sources
    logger.debug(f"querying Tactic ({index}) -> Technique answer cards under ATT&CK {version_context}")
    technique_alias = aliased(Technique)
    items = (
        db.session.query(
            Technique,
            func.count(distinct(technique_alias.uid)),
            func.array_agg(distinct(Platform.internal_name)),
            func.array_agg(distinct(DataSource.internal_name)),
        )
        .filter(Technique.attack_version == version_context)
        .join(tactic_technique_map, tactic_technique_map.c.technique == Technique.uid)
        .join(Tactic, tactic_technique_map.c.tactic == Tactic.uid)
        .filter(Tactic.tact_id == index)
        .filter(Technique.parent_uid == None)
        .outerjoin(technique_alias, technique_alias.parent_uid == Technique.uid)
        .join(
            technique_platform_map,
            technique_platform_map.c.technique == Technique.uid,
        )
        .join(Platform, technique_platform_map.c.platform == Platform.uid)
        .outerjoin(technique_ds_map, technique_ds_map.c.technique == Technique.uid)
        .outerjoin(DataSource, technique_ds_map.c.data_source == DataSource.uid)
        .group_by(Technique.uid)
    ).all()

    # form answers
    answers = [
        {
            "id": technique.tech_id,
            "content": outgoing_markdown(technique.tech_answer or ""),
            "name": technique.tech_name,
            "url": technique.tech_url,
            "path": build_url(technique, index, version_context, num == 0),  # *
            "platforms": platforms,
            "num": num,
            "data_sources": data_sources,
        }
        for technique, num, platforms, data_sources in items
    ]
    # * in build_url: end=True if Tech has 0 children (no SubTechs),
    #   thus a success link is made; for Techs with Subs - a question view is made

    # order Technique answers alphabetically
    answers.sort(key=lambda ans: ans["name"])
    return answers


# technique -> subtechs / self
def answers_api_technique(args):
    """Returns the SubTechnique answer cards* under the given Technique (under a given Tactic and ATT&CK version)

    * Note:
    - Also returns the Technique itself at the end of the list
    - This is done as the user can see if any specific variant of behavior applies first...
      but they can pick the general case if not

    Input:
    - args = (index, tactic_context, version_context)
    - index being the Technique ID to get SubTechnique answer cards for
    - tactic_context being the Tactic ID of the Tactic this Technique index lives under
    - version_context being the version of ATT&CK to get this content from

    Output:
    - a list of dicts
    - in order of ascending SubTechniques (Twxyz.001, .002, .003) and then the Base Technique itself (Twxyz)
    """

    index, tactic_context, version_context = args

    # query base Technique, its SubTechniques, their # of children, and their associated platforms / data sources
    logger.debug(
        f"querying Technique ({index}) -> Sub-Technique answer cards "
        f"in the context of Tactic {tactic_context} under ATT&CK {version_context}"
    )
    technique_alias = aliased(Technique)
    items = (
        db.session.query(
            Technique,
            technique_alias,
            func.array_agg(distinct(Platform.internal_name)),
            func.array_agg(distinct(DataSource.internal_name)),
        )
        .filter(Technique.tech_id == index)
        .filter(
            and_(
                Technique.attack_version == version_context,
                technique_alias.attack_version == version_context,
            )
        )
        .join(tactic_technique_map, tactic_technique_map.c.technique == Technique.uid)
        .join(Tactic, tactic_technique_map.c.tactic == Tactic.uid)
        .join(
            technique_alias,
            or_(
                technique_alias.parent_uid == Technique.uid,
                technique_alias.tech_id == Technique.tech_id,
            ),
        )
        .join(
            technique_platform_map,
            technique_platform_map.c.technique == Technique.uid,
        )
        .join(Platform, technique_platform_map.c.platform == Platform.uid)
        .outerjoin(technique_ds_map, technique_ds_map.c.technique == Technique.uid)
        .outerjoin(DataSource, technique_ds_map.c.data_source == DataSource.uid)
        .group_by(Technique.uid, technique_alias.uid)
    ).all()

    # form answers
    answers = []
    for technique, sub, platforms, data_sources in items:

        # sub is the BaseTech (general case)
        if sub.uid == technique.uid:
            path = build_url(technique, tactic_context, version_context, True)  # end=True, success page view
            content = outgoing_markdown(current_app.config["BASE_TECHNIQUE_ANSWER"])

        # sub is SubTechnique of BaseTech
        else:
            technique = sub
            path = build_url(technique, tactic_context, version_context)
            content = outgoing_markdown(technique.tech_answer or "")

        answers.append(
            {
                "id": technique.tech_id,
                "content": content,
                "name": technique.tech_name,
                "url": technique.tech_url,
                "path": path,
                "platforms": platforms,
                "num": 0,  # num of children the answer card has, SubTechs have none
                "data_sources": data_sources,
            }
        )

    # order Tech/Subtechs in 001..00N, Base order
    answers.sort(key=lambda ans: int(ans["id"].split(".")[1]) if ("." in ans["id"]) else 999)
    return answers


# ----------------------------------------------------------------------------------------------------------------------


def version_has_co_ocs_data(version):
    """Returns a bool on if the given ATT&CK version has CoOccurrence data for it in the DB"""

    logger.debug(f"checking if ATT&CK {version} has CoOccurrence data or not")
    exists = (
        db.session.query(Technique.attack_version)
        .filter(Technique.attack_version == version)
        .join(CoOccurrence, Technique.uid == CoOccurrence.technique_i)
    ).first()
    return (exists is not None) and (len(exists) == 1) and (exists[0] == version)


@api_.route("/api/cooccurrences", methods=["GET"])
@wrap_exceptions_as(ErrorDuringAJAXRoute)
def cooccurrences_api():
    """Returns CoOccurences for either a single or multiple source Techniques

    version
    - must be defined
    - ATT&CK version to pull from

    tech_ids
    - must be length 1+
    - must be valid Technique IDs

    url-based request: .../api/cooccurrences?version=VERSION&tech_ids=TECH_1&tech_ids=TECH_2
    JSON response
    """
    g.route_title = "Get Techniques' CoOccurrences"

    # get args and ensure format validity
    version = request.args.get("version")
    tech_ids = request.args.getlist("tech_ids")

    if (version is None) or (not is_attack_version(version)):
        logger.error("request failed - version field missing / malformed")
        return jsonify(message="Version must be defined and of correct format."), 400

    if (len(tech_ids) == 0) or (not all(is_tech_id(tid) for tid in tech_ids)):
        logger.error("request failed - the list of Tech IDs is malformed / empty")
        return jsonify(message="Tech_IDs must be a list of strings with a length of 1+."), 400
    tech_ids = set(tech_ids)

    logger.debug(f"requesting CoOccurrences for {len(tech_ids)} Techniques under ATT&CK {version}")

    # check that version exists
    version_obj = AttackVersion.query.get(version)
    if version_obj is None:
        logger.error("request failed - version provided is not on the server")
        return jsonify(message="ATT&CK Version requested must exist."), 400

    # check if co-oc content exists for this version
    if not version_has_co_ocs_data(version):
        logger.error("request failed - version provided has no CoOccurrence data")
        return jsonify(message="No CoOccurrence data exists for this ATT&CK version."), 404

    # Get implied Techniques and their scores
    technique_i = aliased(Technique)
    technique_j = aliased(Technique)
    cooccurrences = (
        db.session.query(technique_i.uid, CoOccurrence.score, technique_j)  # i -implies-> j
        # get success/cart Techniques
        .filter(and_(technique_i.attack_version == version, technique_i.tech_id.in_(tech_ids)))
        # join co-ocs of score 1.0+
        .join(CoOccurrence, technique_i.uid == CoOccurrence.technique_i).filter(CoOccurrence.score >= 1.0)
        # join implied Techniques
        .join(technique_j, technique_j.uid == CoOccurrence.technique_j)
    )

    # don't show implied Techniques already in the cart for the suggestion page
    if len(tech_ids) > 1:
        cooccurrences = cooccurrences.filter(technique_j.tech_id.notin_(tech_ids))

    # build response
    implied_techs = {}
    logger.debug("querying CoOccurrences")
    for _, score, implied_tech in cooccurrences.all():

        # already added - just increase score
        itid = implied_tech.tech_id
        if itid in implied_techs:
            implied_techs[itid]["score"] += score

        # not added yet - add details
        else:
            implied_techs[itid] = {
                "tech_name": implied_tech.tech_name,
                "tech_id": itid,
                "tech_desc": outgoing_markdown(implied_tech.tech_description),
                "url": f'/no_tactic/{version}/{itid.replace(".", "/")}',
                "score": score,
            }
    logger.debug(f"got {len(implied_techs)} CoOccurrences")

    # make into list and order score descending
    implied_techs = list(implied_techs.values())
    implied_techs.sort(key=lambda it: -it["score"])

    logger.info("sending CoOccurrences to user")
    return jsonify(implied_techs), 200
