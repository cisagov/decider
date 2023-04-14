import logging.config
from typing import List, Optional, Union
from flask import Blueprint, render_template, request, current_app, jsonify, g
from flask.wrappers import Response

from app.models import db, Tactic, Technique, Mismapping
from app.models import tactic_technique_map
from sqlalchemy import or_, and_, func, distinct
from sqlalchemy.orm import aliased
from sqlalchemy.dialects.postgresql import array

from app.routes.profile import edit_permission

from app.routes.utils_db import VersionPicker
from app.routes.utils import (
    SUB_TECHNIQUE_ID_REGEX_P,
    TECHNIQUE_ID_REGEX_P,
    incoming_markdown,
    is_attack_version,
    is_tact_id,
    outgoing_markdown,
    outedit_markdown,
)
from app.routes.utils import ErrorDuringHTMLRoute, ErrorDuringAJAXRoute, wrap_exceptions_as

import itertools
import re
import json
import bleach

from collections import OrderedDict

logger = logging.getLogger(__name__)
edit_ = Blueprint("edit_", __name__, template_folder="templates")


# ---------------------------------------------------------------------------------------------------------------------
# Edit Mismappings


@edit_.route("/edit/mismapping", methods=["GET"])
@edit_permission.require(http_exception=403)
@wrap_exceptions_as(ErrorDuringHTMLRoute)
def edit_mismapping_get():
    """Returns the mismapping editing page

    url-based request: .../edit/mismapping?index=TECH_ID&name=TECH_NAME
    - index and name are optional

    HTML response
    - (index or name missing) -> returns the mismapping editing page with a blank prompt to add a mismapping
    - (index and name provided) -> the editing page prompts for a mismapping to be added for the specified technique
    """
    g.route_title = "Edit Mismappings Page"

    index = request.args.get("index")
    name = request.args.get("name")

    logger.debug("asking VersionPicker for ATT&CK version to use")
    version_pick = VersionPicker()
    version_pick.set_vars()
    version = version_pick.cur_version
    logger.debug(f"using ATT&CK {version}")

    original = dict(original=None, original_techname=None, version=version, index=index)

    # if the index (technique ID) and the technique name were specified in the url, set
    # the original to be what was found in the url so that the user can go straight into
    # entering data
    if index and name:
        original = dict(original=index, original_techname=name, version=version)

    logger.info("serving page")
    return render_template("edit/mismapping.html", **{"original": original})


@edit_.route("/edit/mismapping", methods=["POST"])
@edit_permission.require(http_exception=403)
@wrap_exceptions_as(ErrorDuringAJAXRoute)
def edit_mismapping_post():
    """Creates a new mismapping or updates an existing one

    General Field Info:
    - "original" is always a valid Tech ID for the provided version
    - "corrected" is either a valid Tech ID (maps to something), or a non-Tech-ID string "N/A" (action unmappable)
    - "context" and "rationale" are user-editable text fields explaining why the original was wrong / new was fine

    JSON request (new):
    - "version" provides scope for what ATT&CK version Tech IDs pertain to
    - "original", "corrected", "context", "rationale" are fields that are to be set for the new mismap

    JSON request (update):
    - "id" is the id of the Mismapping to be updated
    - "version" provides scope for what ATT&CK version Tech IDs pertain to
    - "corrected", "context", "rationale" are fields that can be updated

    JSON response:
    - A dict describing the added / updated Mismapping object
    """
    g.route_title = "Create / Update Mismapping"

    try:
        mismap = request.json
        if not isinstance(mismap, dict):
            raise Exception()
    except Exception:
        logger.error("request failed - malformed data type")
        return jsonify(message="Request was malformed"), 400

    arg_version = request.args.get("version")

    if arg_version:
        if not is_attack_version(arg_version):
            logger.error("request failed - malformed ATT&CK version provided")
            return jsonify(message="'version' field malformed"), 400

        logger.debug(f"querying existence of version {arg_version}")

    version_pick = VersionPicker(version=arg_version)
    if not version_pick.is_valid:
        logger.error(f"request failed - version {arg_version} does not exists")
        return version_pick.get_invalid_message()
    if arg_version:
        logger.debug(f"requested version {arg_version} - it exists")
    else:
        logger.debug(f"VersionPicker provided version {version_pick.cur_version}")

    mismap_id = mismap.get("id")

    # clean user provided content
    context = bleach.clean(mismap.get("context", ""))
    rationale = bleach.clean(mismap.get("rationale", ""))

    # if the provided context has a pattern of technique,
    # it is a technique, otherwise N/A or None
    corrected = TECHNIQUE_ID_REGEX_P.search(mismap.get("corrected", ""))
    corrected = None if corrected is None else corrected.group(0)

    # mismap_id missing means that the user wants to add a new mismapping
    if mismap_id is None:
        try:
            original = TECHNIQUE_ID_REGEX_P.search(mismap.get("original", ""))
            original = None if original is None else original.group(0)

            # original cannot be N/A or None
            if original is None:
                logger.error(
                    "tried adding a new mismapping - however, "
                    "the 'original' Technique field was never defined (it is required)"
                )
                return jsonify(message="Original cannot be empty or is an invalid value"), 400

        except Exception:
            logger.exception("failed to parse the 'original' field")
            return jsonify(message="Error with parsing original and corrected fields"), 400

        logger.debug("querying highest Mismapping ID as a new Mismapping entry will be added")
        last_mismap = db.session.query(Mismapping).order_by(Mismapping.uid.desc()).first()
        if last_mismap is None:
            last_id = 0
        else:
            last_id = last_mismap.uid
        logger.debug(f"query done - it's {last_id}")

        # get the proper uids of the specified techniques
        original_tech_id = original
        logger.debug(
            f"resolving existence of original Tech ({original_tech_id}) under ATT&CK {version_pick.cur_version}"
        )
        original = (
            db.session.query(Technique)
            .filter(
                and_(
                    Technique.tech_id == original,
                    Technique.attack_version == version_pick.cur_version,
                )
            )
            .first()
        )
        logger.debug("query done")

        # uid for the corrected technique
        corrected_tech_id = corrected
        logger.debug(
            f"resolving existence of corrected Tech ({corrected_tech_id}) under ATT&CK {version_pick.cur_version}"
        )
        corrected = (
            db.session.query(Technique)
            .filter(
                Technique.tech_id == corrected,
                Technique.attack_version == version_pick.cur_version,
            )
            .first()
        )
        logger.debug("query done")

        if original is None:
            logger.error(
                f"Original Technique ({original_tech_id}) could not be found in "
                f"{version_pick.cur_version} - cannot add Mismapping"
            )
            return jsonify(message="Original Technique could not be found"), 400

        mismap_obj = Mismapping(
            uid=last_id + 1,
            original=original.uid,
            corrected=corrected.uid if corrected is not None else None,
            context=context,
            rationale=rationale,
        )
        db.session.add(mismap_obj)

    # update mapping since user supplied a mismap_id
    else:
        if not isinstance(mismap_id, int):
            logger.error("request failed - malformed (non-int) Mismapping ID provided")
            return jsonify(message="Mismapping ID was not an integer as expected"), 400

        logger.debug(f"querying for existing Mismapping to update mismap_id={mismap_id}")
        mismap_obj = db.session.query(Mismapping).filter(Mismapping.uid == mismap_id).first()
        if mismap_obj is None:
            logger.debug(f"request failed - could not locate existing Mismapping #{mismap_id}")
            return jsonify(message="Original could not be found"), 404
        logger.debug(f"successfully located existing Mismapping #{mismap_id}")

        corrected_tech_id = corrected
        logger.debug(
            f"querying existence of corrected Technique ({corrected_tech_id}) "
            f"under ATT&CK {version_pick.cur_version}"
        )
        corrected = (
            db.session.query(Technique)
            .filter(
                and_(
                    Technique.tech_id == corrected,
                    Technique.attack_version == version_pick.cur_version,
                )
            )
            .first()
        )
        logger.debug("query done")

        mismap_obj.corrected = corrected.uid if corrected is not None else None
        mismap_obj.context = context
        mismap_obj.rationale = rationale

    # write new Mismapping / updates to an existing one
    try:
        logger.debug(f"attempting to write Mismapping #{mismap_obj.uid}")
        db.session.commit()
        logger.info(f"successfully wrote Mismapping #{mismap_obj.uid}")

    except Exception:
        db.session.rollback()
        logger.exception(f"failed to write Mismapping #{mismap_obj.uid}")
        return jsonify(message="Unable to save mismapping"), 500

    # return details of newly created or updated mismapping
    return (
        jsonify(
            original=mismap_obj.original,
            corrected=mismap_obj.corrected,
            uid=mismap_obj.uid,
            rationale=mismap_obj.rationale,
            context=mismap_obj.context,
        ),
        200,
    )


@edit_.route("/edit/mismapping", methods=["DELETE"])
@edit_permission.require(http_exception=403)
@wrap_exceptions_as(ErrorDuringAJAXRoute)
def edit_mismapping_delete():
    """Deletes an existing Mismapping

    JSON request
    - "id" field is the Mismapping ID

    JSON response
    - success -> 200 + blank
    - error -> 400/404/500 depending on problem + message
    """
    g.route_title = "Delete Mismapping"

    try:
        mismap_id = request.json.get("id")
    except Exception:
        logger.error("request failed - malformed data type")
        return jsonify(message="Request was malformed"), 400

    if mismap_id is None:
        logger.error("request failed - it did not specify a Mismapping ID")
        return jsonify(message="Mismapping ID not provided"), 400

    elif not isinstance(mismap_id, int):
        logger.error("failed - request contained a malformed (non-int) Mismapping ID")
        return jsonify(message="Mismapping ID not an integer as expected"), 400

    try:
        logger.debug(f"attempting to delete Mismapping #{mismap_id}")
        db.session.query(Mismapping).filter(Mismapping.uid == mismap_id).delete()
        db.session.commit()
        logger.debug(f"successfully deleted Mismapping #{mismap_id}")

    except Exception:
        db.session.rollback()
        logger.exception(f"failed to delete Mismapping #{mismap_id}")
        return jsonify(message="Unable to delete from the database"), 500

    return jsonify(), 200


# ---------------------------------------------------------------------------------------------------------------------
# Edit Tree (Question & Answer Card Content)


@edit_.route("/edit/tree", methods=["GET"])
@edit_permission.require(http_exception=403)
@wrap_exceptions_as(ErrorDuringHTMLRoute)
def edit_tree_get():
    """Returns the question/answer tree editing page (HTML response)"""
    g.route_title = "Tree Q/A Editing Page"

    version_pick = VersionPicker()

    # can only fail if user is allowed to specify version
    # as now, VersionPicker uses an always-defined version
    result, _, _ = get_tree("start", version_pick.cur_version)

    logger.info("serving page")
    return (
        render_template(
            "/edit/tree.html",
            **{
                "results": result,
                "missing": get_missing_content(version_pick.cur_version),
            },
        ),
        200,
    )


@edit_.route("/edit/tree/api", methods=["GET"])
@edit_permission.require(http_exception=403)
@wrap_exceptions_as(ErrorDuringAJAXRoute)
def edit_tree_api_get():
    """Returns existing tree content or a listing of missing tree content

    url-based request:
    - "selected_content" field is either "missing_content" or "tree"
      - "missing_content" returns a listing of all missing tree content
      - "tree" returns the question and answers at the specified location in the tree

    - "index" field is needed when using selected_content="tree"
      - this specifies what question will be returned (along with the answers that live directly under it)

    JSON response
    """
    g.route_title = "Get Tree Q/A Content"

    arg_version = request.args.get("version")
    if arg_version:
        if not is_attack_version(arg_version):
            logger.error("failed - request has a malformed 'version' field")
            return jsonify(message="Malformed 'version' field"), 400

        logger.debug(f"checking existence of specified version {arg_version}")

    version_pick = VersionPicker(version=arg_version)
    if not version_pick.is_valid:
        logger.error("requested ATT&CK version does not exist")
        return version_pick.get_invalid_message()

    if arg_version:
        logger.debug("requested ATT&CK version exists")
    else:
        logger.debug(f"VersionPicker provided version {version_pick.cur_version}")

    # retrieve the type of content
    selected_content = request.args.get("selected_content")

    # retireve only missing technique information (no other information is retrieved)
    if selected_content == "missing_content":
        logger.info(f"getting Techniques with missing content (in ATT&CK {version_pick.cur_version})")
        return jsonify(get_missing_content(version_pick.cur_version)), 200

    # retrieve answer/question for index specified (tactic or technique)
    elif selected_content == "tree":
        index = request.args.get("index", "")
        result, message, code = get_tree(index, version_pick.cur_version)

        if result is None:
            logger.error(
                f"failed - request specified an invalid Tactic / Technique ID ({index}) "
                f"under ATT&CK {version_pick.cur_version}"
            )
            return Response(message), code

        logger.info(f"sending answer/question content for {index} in ATT&CK {version_pick.cur_version}")
        return jsonify(result), 200

    logger.error(
        "failed - request specified an invalid value for 'selected_content' - it must be 'missing_content' or 'tree'"
    )
    return jsonify(message="Unsupported selected_content"), 400


@edit_.route("/edit/tree/api", methods=["POST"])
@edit_permission.require(http_exception=403)
@wrap_exceptions_as(ErrorDuringAJAXRoute)
def edit_tree_api_post():
    """Updates a(n) question / answer card at a specified location in the tree

    JSON request
    - a dict with keys "type", "id", "text", "version"
    - "version" field indicates what ATT&CK version this change will occur under
    - "id" field is the ATT&CK ID of the item in the tree to be modified (either a Technique or Tactic)
      - Tactics always have both an answer and a question
      - Techniques always have an answer, and a question too if they have SubTechniques under them
      - SubTechniques always have an answer, but never a question
    - "type" field is either "question" or "answer", depending on the type of content to be updated at that index / id
    - "text" field is the new MD content to exist at the specified destination

    JSON response
    - a dict with keys "name", "index"
    - "name" field is the rendered HTML for the browser to display
    = "index" is the ATT&CK ID of the item that was updated
    """
    g.route_title = "Update Tree Q/A Content"

    try:
        data = request.json
        if not isinstance(data, dict):
            raise Exception()
    except Exception:
        logger.error("request failed - malformed data type")
        return jsonify(message="Request was malformed"), 400

    # field validation - ensure the proper fields are included
    fields = ["type", "id", "text", "version"]
    result, message = validate_fields(data.keys(), fields)
    if not result:
        logger.error(f"failed - request didn't include all required fields: {fields}")
        return jsonify(message=message), 400

    field_type, item_id, text, version = [data.get(field, "") for field in fields]

    if (version is None) or (not is_attack_version(version)):
        logger.error("failed - request had a missing / malformed version field")
        return jsonify(message="'version' field missing / malformed"), 400

    logger.debug(f"checking validity of specified version: {version}")
    version_pick = VersionPicker(version=version)
    if not version_pick.is_valid:
        logger.error(f"failed - checking validity of specified version: {version} - it does not exists")
        return version_pick.get_invalid_message()
    logger.debug(f"checking validity of specified version: {version} - it exists")

    # get a tactic or technique
    item = get_tact_or_tech(item_id, version)

    if item is None:
        logger.error(f"cannot find item {item_id} in ATT&CK {version}")
        return jsonify(message=f"Cannot find content for {item_id}"), 404

    # set the value of the tactic or techniue
    res = set_tact_or_tech_qna(item, text, field_type)

    if res is None:
        logger.error(f"error saving changes to {item_id} in ATT&CK {version}")
        return jsonify(message="Error saving to the database"), 400

    logger.info(f"successfully modified the {field_type} content of {item_id} in ATT&CK {version}")
    return jsonify(res), 200


# ---------------------------------------------------------------------------------------------------------------------
# Audit Answer / Question Cards


@edit_.route("/edit/tree/audit/<version>", methods=["GET"])
@edit_permission.require(http_exception=403)
@wrap_exceptions_as(ErrorDuringHTMLRoute)
def audit_tree_content(version):
    """Returns an HTML page containing a table showing any Q/A cards that do not fit the current format

    Mentions:
    ---------
    - Tactics missing Question or Answer
    - BaseTechniques with subs missing Question or Answer
    - BaseTechniques without subs missing Answer or having Question
    - SubTechniques missing Answer or having Question
    - Presence of "?" in any Answer card
    - Absence of "?" in any Question card
    - Absence of "**" (bolding) in any card
    - Any Technique or Tactic having exactly the same Question and Answer content
    """
    g.route_title = "Audit Tree Content"

    def tech_or_tact_to_dict(t: Union[Technique, Tactic]) -> dict:
        """Creates dict of consistent fields for a Technique or Tactic"""

        if isinstance(t, Technique):
            id_ = t.tech_id
            name = t.full_tech_name
            url = t.tech_url
            answer = t.tech_answer
            question = t.tech_question

        else:  # is Tactic
            id_ = t.tact_id
            name = t.tact_name
            url = t.tact_url
            answer = t.tact_answer
            question = t.tact_question

        return {
            "id": id_,
            "name": name,
            "url": url,
            "answer": answer,
            "question": question,
        }

    def issue_entry(t: Union[Technique, Tactic, dict], issue: str) -> dict:
        """Creates a dict describing an issue with a Technique or Tactic (which gets included as fields in the dict)

        - t is dict: the issue key will be added to a copy of t
        - t is Technique / Tactic: a dict representing the item will be made, then an issue key added
        """

        if isinstance(t, dict):
            item = t.copy()

        else:  # is Technique / Tactic
            item = tech_or_tact_to_dict(t)

        item["issue"] = issue
        return item

    def is_blank(text: Optional[str]) -> bool:
        """Returns True for text that is None or that becomes '' when stripped"""
        if isinstance(text, str):
            return text.strip() == ""
        else:  # is None
            return True

    def score_audit_row(row: dict) -> float:
        """Scoring function for scorting audit rows - order Tactics before Techniques by numerical value"""
        score = 0
        index = row["id"]

        if index.startswith("TA"):
            index = index[2:]
            score -= 10_000

        else:  # .startswith("T")
            index = index[1:]

        score += float(index)
        return score

    # validate format
    if not is_attack_version(version):
        logger.error("A malformed ATT&CK version was requested")
        return render_template("status_codes/404.html"), 404

    # validate existence
    logger.debug(f"Checking ATT&CK version existence: {version}")
    if not VersionPicker(version).set_vars():
        logger.error(f"Checking ATT&CK version existence: {version} - doesn't exist")
        return render_template("status_codes/404.html"), 404
    logger.debug(f"Checking ATT&CK version existence: {version} - it exists")

    # -----------------------------------------------------------------------------------------------------------------
    SubTechnique = aliased(Technique)

    logger.debug(f"Querying all Tactics in ATT&CK {version}")
    tactics: List[Tactic] = db.session.query(Tactic).filter(Tactic.attack_version == version).all()
    logger.debug(f"Got {len(tactics)} Tactics")

    logger.debug(f"Querying all Techniques in ATT&CK {version}")
    techniques_subcnt = (
        db.session.query(Technique, func.count(distinct(SubTechnique.uid)))
        .filter(Technique.attack_version == version)
        .group_by(Technique.uid)
        .outerjoin(SubTechnique, SubTechnique.parent_uid == Technique.uid)
    ).all()
    logger.debug(f"Got {len(techniques_subcnt)} Techniques")

    base_techs_subcnt = [
        [technique, sub_count] for technique, sub_count in techniques_subcnt if ("." not in technique.tech_id)
    ]

    base_techs_without_subs: List[Technique] = [
        technique for technique, sub_count in base_techs_subcnt if (sub_count == 0)
    ]

    base_techs_with_subs: List[Technique] = [
        technique for technique, sub_count in base_techs_subcnt if (sub_count != 0)
    ]

    sub_techs: List[Technique] = [technique for technique, _ in techniques_subcnt if ("." in technique.tech_id)]

    # -----------------------------------------------------------------------------------------------------------------

    audit = []

    # Tactics [A always][Q always]
    for t in tactics:

        if is_blank(t.tact_answer):
            audit.append(issue_entry(t, "Tactic answer is blank"))

        if is_blank(t.tact_question):
            audit.append(issue_entry(t, "Tactic question is blank"))

    # BaseTechnique NO Subs [A always][Q never]
    for t in base_techs_without_subs:

        if is_blank(t.tech_answer):
            audit.append(issue_entry(t, "Technique answer is blank"))

        if not is_blank(t.tech_question):
            audit.append(issue_entry(t, "Technique with no Subs has defined question"))

    # BaseTechnique /w Subs [A always][Q always]
    for t in base_techs_with_subs:

        if is_blank(t.tech_answer):
            audit.append(issue_entry(t, "Technique answer is blank"))

        if is_blank(t.tech_question):
            audit.append(issue_entry(t, "Technique with Subs has blank question"))

    # SubTechnique [A always][Q never]
    for t in sub_techs:

        if is_blank(t.tech_answer):
            audit.append(issue_entry(t, "SubTechnique answer is blank"))

        if not is_blank(t.tech_question):
            audit.append(issue_entry(t, "SubTechnique has defined question"))

    tacts_and_techs = [
        tech_or_tact_to_dict(t)
        for t in itertools.chain(tactics, base_techs_without_subs, base_techs_with_subs, sub_techs)
    ]

    # Answer / Question cards missing bolding ("**" absent)
    for t in tacts_and_techs:

        if (not is_blank(t["answer"])) and ("**" not in t["answer"]):
            audit.append(issue_entry(t, "Answer is missing bolding"))

        if (not is_blank(t["question"])) and ("**" not in t["question"]):
            audit.append(issue_entry(t, "Question is missing bolding"))

    # Answer cards are a question ("?" present), or, Question cards are not a question ("?" absent)
    for t in tacts_and_techs:

        if (not is_blank(t["answer"])) and ("?" in t["answer"]):
            audit.append(issue_entry(t, "Answer contains question mark"))

        if (not is_blank(t["question"])) and ("?" not in t["question"]):
            audit.append(issue_entry(t, "Question is missing a question mark"))

    # Answer and Question for a single item are the same
    for t in tacts_and_techs:

        if (
            (not is_blank(t["answer"]))
            and (not is_blank(t["question"]))
            and (t["answer"].strip() == t["question"].strip())
        ):
            audit.append(issue_entry(t, "Answer and Question for this item are the same"))

    audit.sort(key=lambda audit_row: score_audit_row(audit_row))

    logger.info("Sending generated card content audit to user")
    return render_template("edit/tree_audit.html", audit_rows=audit)


# ---------------------------------------------------------------------------------------------------------------------
# Helper Functions


def validate_fields(selected_fields, fields):
    """Checks if all "fields" specified exist in "selected_fields"

    Output:
    - tuple of (bool, dict)
    - bool: T/F on if all fields were present
    - dict: only populated if bool=F, has message stating missing fields
    """

    diff = set(fields).difference(set(selected_fields))
    if diff:
        return False, {"message": f"Please include the following fields: {','.join(list(diff))}"}
    return True, {}


def get_tact_or_tech(index, version):
    """Retrieves the specified Technique / Tactic

    index: str of Tactic ID or Technique ID to get
    version: str of ATT&CK version to get the item from

    returns Technique or Tactic object
    """

    if is_tact_id(index):
        logger.debug(f"querying Tactic {index} in ATT&CK {version}")
        tact = db.session.query(Tactic).filter(and_(Tactic.attack_version == version, Tactic.tact_id == index)).first()
        logger.debug("query done")
        return tact

    else:
        logger.debug(f"querying Technique {index} in ATT&CK {version}")
        tech = (
            db.session.query(Technique)
            .filter(and_(Technique.attack_version == version, Technique.tech_id == index))
            .first()
        )
        logger.debug("query done")
        return tech


def set_tact_or_tech_qna(item, value, field_type):
    """Updates a Technique or Tactic's question or answer content in the decision tree

    Input:
    - item: a Technique or a Tactic object
    - value: an MD string of new content to be set
    - field_type: either "question" or "answer", specifying what to update on the item

    Output:
    - dict with fields "name", "index"
    - "name" being the MD value rendered as HTML
    - "index" being the TechID / TacticID of the item updated
    - can return None instead if the update fails
    """

    escaped_val = incoming_markdown(value)

    if isinstance(item, Technique):
        type_id = f"Technique {item.tech_id}"

        if field_type == "question":
            item.tech_question = escaped_val
        elif field_type == "answer":
            item.tech_answer = escaped_val
        index = item.tech_id

    elif isinstance(item, Tactic):
        type_id = f"Tactic {item.tact_id}"

        if field_type == "question":
            item.tact_question = escaped_val
        elif field_type == "answer":
            item.tact_answer = escaped_val
        index = item.tact_id

    ret = {"name": outgoing_markdown(escaped_val), "index": index}

    try:
        logger.debug(f"attempting to write {field_type} of {type_id} under {item.attack_version}")
        db.session.commit()
        logger.info(f"successfully wrote {field_type} of {type_id} under {item.attack_version}")
        return ret

    except Exception:
        db.session.rollback()
        logger.exception(f"failed to write {field_type} of {type_id} under {item.attack_version}")
        return None


def get_tree(index, version):
    """Retrieves a portion of the decision tree rooted at the specified index

    index: str of root of question-answer group to get
    - "start": grabs main tree root question and tactic answer cards
    - TA[0-9]{4}: grabs a tactic question and its technique children answer cards
    - TA[0-9]{4}\\.T[0-9]{4}: grabs a technique (under a tactic) question and its subtechnique children answer cards

    version: str of ATT&CK version to pull content from
    - must be validated before calling get_tree()

    returned tuple format is (content, error_msg, http_code)
    - content is either None (err), or a dict containing "question" and answers ("data")
    - error_msg is a dict with message key (err), or an empty str on success
    - http_code any of 404 for not found, 400 for bad request, 200 for success
    """

    node = None
    tree = []

    # Tactic -> get Techniques
    if is_tact_id(index):

        # query tactic
        logger.debug(f"querying Tactic {index} under ATT&CK {version}")
        node = db.session.query(Tactic).filter(and_(Tactic.attack_version == version, Tactic.tact_id == index)).first()
        logger.debug("query done")

        # not found -> 404
        if node is None:
            logger.error(f"can't fulfill request - can't find Tactic {index} within ATT&CK {version}")
            return None, json.dumps({"message": f"{index} could not be found"}), 404

        node_id = node.tact_id
        node_name = node.tact_name
        question = node.tact_question
        technique_alias = aliased(Technique)

        # query Techs
        logger.debug(f"querying Techniques under Tactic {index} under ATT&CK {version}")
        query = (
            db.session.query(Technique, func.count(technique_alias.uid))
            .filter(and_(Technique.attack_version == version, Technique.parent_uid == None))
            .join(tactic_technique_map, tactic_technique_map.c.technique == Technique.uid)
            .join(Tactic, tactic_technique_map.c.tactic == Tactic.uid)
            .filter(Tactic.tact_id == index)
            .outerjoin(technique_alias, technique_alias.parent_uid == Technique.uid)
            .group_by(Technique.uid)
            .order_by(Technique.tech_id)
        ).all()
        logger.debug(f"got {len(query)} Techniques")

        for technique, count in query:
            tree.append((technique.tech_id, technique.tech_answer, technique.tech_name, count))

    # Start -> get Tactics
    elif index == "start":

        # start root
        node = ""
        node_id = "start"
        node_name = "start"
        question = current_app.config["START_QUESTION"]

        # tactic children
        logger.debug(f"querying Tactics under root 'start' under ATT&CK {version}")
        tree = [
            (tactic.tact_id, tactic.tact_answer, tactic.tact_name, 0)
            for tactic in (
                db.session.query(Tactic).filter(Tactic.attack_version == version).order_by(Tactic.uid)
            ).all()
        ]
        logger.debug(f"got {len(tree)} Tactics")

    # Technique (w/ Tactic context) -> get SubTechniques
    elif re.match(r"^TA[0-9]{4}\.T[0-9]{4}$", index):
        tech_id = index.split(".")[1]

        # query Technique
        logger.debug(f"querying Technique {tech_id} under ATT&CK {version}")
        node = (
            db.session.query(Technique)
            .filter(
                and_(
                    Technique.attack_version == version,
                    Technique.tech_id == tech_id,
                )
            )
            .first()
        )
        logger.debug("query done")

        # not found -> 404
        if node is None:
            logger.error(f"can't fulfill request - can't find Technique {tech_id} within ATT&CK {version}")
            return None, json.dumps({"message": f"{tech_id} could not be found"}), 404

        node_id = node.tech_id
        node_name = node.tech_name
        question = node.tech_question
        technique_alias = aliased(Technique)

        # query SubTechs
        logger.debug(f"querying SubTechniques under Technique {tech_id} under ATT&CK {version}")
        query = (
            # techniques in current version
            db.session.query(Technique)
            .filter(Technique.attack_version == version)
            # that have the parent technique with tech_id == node_id
            .join(technique_alias, technique_alias.uid == Technique.parent_uid)
            .filter(technique_alias.tech_id == node_id)
            # ordered by their tech_id
            .order_by(Technique.tech_id)
        ).all()
        logger.debug(f"got {len(query)} SubTechniques")

        for technique in query:
            tree.append((technique.tech_id, technique.tech_answer, technique.tech_name, 0))

    # bad format -> 400
    else:
        logger.debug("the format of the index is not valid")
        return (
            None,
            json.dumps({"message": "The format of the index is not valid."}),
            400,
        )

    # form editing / preview variants of MD
    results = [
        {
            "id": node_id,
            "name": node_name,
            "question_edit": outedit_markdown(question or ""),
            "question_view": outgoing_markdown(question or ""),
        }
    ]
    for id, answer, name, count in tree:
        results.append(
            {
                "id": id,
                "answer_edit": outedit_markdown(answer or ""),
                "answer_view": outgoing_markdown(answer or ""),
                "name": name,
                "has_children": count > 0,
            }
        )
    results = {"question": results[0], "data": results[1:]}

    logger.info(f"sending sub-tree rooted at {index} under ATT&CK {version}")
    return results, "", 200


def get_missing_content(version):
    """Retrieves a list of Techniques missing question or answer content

    version: str of ATT&CK version to get missing content of
    """

    technique_alias = aliased(Technique)

    # subquery to check filter out techniques that do not have subs
    subq = (
        db.session.query(Technique.uid)
        .filter(Technique.attack_version == version)
        .join(technique_alias, technique_alias.parent_uid == Technique.uid)
    )

    logger.debug(f"querying missing content for Tech -> SubTech cards ({version})")

    # technique level content is when accessing the technique question and subtech answer
    technique_level_content = (
        db.session.query(
            Tactic,
            func.array_agg(array([Technique.tech_id, Technique.tech_name, "technique_level", "2"])),
        )
        .filter(Tactic.attack_version == version)
        .join(tactic_technique_map, tactic_technique_map.c.tactic == Tactic.uid)
        .join(Technique, tactic_technique_map.c.technique == Technique.uid)
        .order_by(Tactic.uid)
        .filter(
            or_(
                and_(
                    # if the answer is blank or none and tech is a subtech
                    or_(Technique.tech_answer == "", Technique.tech_answer == None),
                    Technique.parent_uid != None,
                ),
                and_(
                    # if the question is blank or none and the tech is a parent
                    # since technique is in the subquery (which checks for parent techs),
                    # it is a parent
                    or_(Technique.tech_question == "", Technique.tech_question == None),
                    Technique.uid.in_(subq),
                ),
            )
        )
        .group_by(Tactic.uid)
    ).all()

    logger.debug("query done")

    logger.debug(f"querying missing content for Tactic -> Technique cards ({version})")

    # tactic level content is when accessing the tactic question and the tech answers
    tactic_level_content = (
        db.session.query(
            Tactic,
            func.array_agg(array([Technique.tech_id, Technique.tech_name, "tactic_level", "1"])),
        )
        .filter(Tactic.attack_version == version)
        .join(tactic_technique_map, tactic_technique_map.c.tactic == Tactic.uid)
        .join(Technique, tactic_technique_map.c.technique == Technique.uid)
        .order_by(Tactic.uid)
        .filter(
            and_(
                # if the answer is blank or none and tech is not a subtech (includes
                # all techs that have children or are standalone)
                or_(Technique.tech_answer == "", Technique.tech_answer == None),
                Technique.parent_uid == None,
            )
        )
        .group_by(Tactic.uid)
    ).all()

    logger.debug("query done")

    # fields:
    # 0: Tactic object
    # 1: ARRAY(tech_id,tech_name,"which_level","tab_to_open")
    # array is a list of techs that belong to a tactic
    # apply a sorting function to the array of techniques
    data = sorted(
        list(
            map(
                lambda d: (d[0], sorted(d[1], key=lambda t: t[0])),
                technique_level_content + tactic_level_content,
            )
        ),
        key=lambda d: d[0].uid,
    )

    # iterate through each tactic and create a tuple of
    # (tactic object, [tech_id, tech_name, level, tab number])
    # label technique_level objects as techniuqe_level
    # leave tactic_level objects alone
    data = [
        (
            d[0],
            [[i[0], i[1], "technique_level", i[3]] if SUB_TECHNIQUE_ID_REGEX_P.match(i[0]) else i for i in d[1]],
        )
        for d in data
    ]

    result = OrderedDict()

    # iterate through the techniques to group them by tactic
    for d in data:
        index = d[0].uid
        # if the tactic has not yet been added
        if index not in result:
            result[index] = (d[0].tact_id, d[0].tact_name, d[1])
        else:
            # the tactic has been seen before
            # save the previous entry and then append another technique
            t_id, t_name, prev_result = result[index]
            result[index] = (
                t_id,
                t_name,
                sorted(d[1] + prev_result, key=lambda t: (t[0], t[2])),
            )

    logger.info(f"sending Techniques that are missing card content in ATT&CK {version}")
    return list(result.values())
