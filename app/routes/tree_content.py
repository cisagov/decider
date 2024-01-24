import logging
from flask import Blueprint, jsonify, render_template, g, request

from app.routes.utils import ErrorDuringAJAXRoute, ErrorDuringHTMLRoute, incoming_markdown, is_attack_version, outedit_markdown, outgoing_markdown, wrap_exceptions_as
from app.routes.utils_db import VersionPicker

from collections import defaultdict
from dataclasses import dataclass
from typing import List, Tuple, Dict, Union, Literal

from sqlalchemy import asc, desc
from app.models import db, Tactic, Technique

from itertools import chain as iter_chain

logger = logging.getLogger(__name__)
tree_content_ = Blueprint("tree_content_", __name__, template_folder="templates")


# [ ] Restrict access of route(s)
# [ ] Add route that renders passed markdown


@dataclass
class TreeNode:
    """
    Represents a Node (Tactic or Technique) of the Question Tree
    """
    type: Literal["tactic", "technique"]
    id: str
    name: str
    answer_edit: str
    answer_view: str
    question_edit: str
    question_view: str
    has_children: bool


@tree_content_.route("/api/render_md", methods=["POST"])
@wrap_exceptions_as(ErrorDuringAJAXRoute)
def render_md():
    """
    Markdown rendering service
    """
    g.route_title = "Render MD"

    try:
        data = request.json
        if not isinstance(data, dict):
            raise Exception()
        md = data.get("md")
        if not isinstance(md, str):
            raise Exception()
    except Exception:
        error_msg = "Request was malformed"
        logger.error(error_msg)
        return jsonify(message=error_msg), 400

    escaped = incoming_markdown(md)
    html = outgoing_markdown(escaped)

    return jsonify(html=html), 200


@tree_content_.route("/tree_content/<version>", methods=["GET"])
@wrap_exceptions_as(ErrorDuringHTMLRoute)
def tree_content(version):
    """
    Displays all Tree Content with Local Editing + Dump Feature
    """
    g.route_title = "Tree Content"

    # version - format check
    if not is_attack_version(version):
        return render_template("status_codes/404.html", reason_for_404="Malformed ATT&CK Version"), 404

    # version - existence check
    if not VersionPicker(version).set_vars():
        return render_template("status_codes/404.html", reason_for_404="Non-existent ATT&CK Version"), 404

    # tactics - query in matrix order
    tactics = (
        db.session.query(
            Tactic.tact_id,
            Tactic.tact_name,
            Tactic.tact_answer,
            Tactic.tact_question,
        )
        .filter(Tactic.attack_version == version)
        .order_by(asc(Tactic.uid))
    ).all()

    # techniques - query in asc id order
    techniques = (
        db.session.query(
            Technique.tech_id,
            Technique.tech_name,
            Technique.tech_answer,
            Technique.tech_question,
        )
        .filter(Technique.attack_version == version)
        .order_by(asc(Technique.tech_id))
    ).all()

    # parents of subs have kids - all else have none
    has_children: defaultdict[str, bool] = defaultdict(lambda: False)
    for tech_id, *_ in techniques:
        if "." in tech_id:
            base_tech_id = tech_id.split(".")[0]
            has_children[base_tech_id] = True

    node_lookup: Dict[str, TreeNode] = {
        id: TreeNode(
            type="tactic" if id.startswith("TA") else "technique",
            id=id,
            name=name,
            answer_edit=outedit_markdown(answer or ""),
            answer_view=outgoing_markdown(answer or ""),
            question_edit=outedit_markdown(question or ""),
            question_view=outgoing_markdown(question or ""),
            has_children=True if id.startswith("TA") else has_children[id],
        )
        for id, name, answer, question in iter_chain(tactics, techniques)
    }

    node_order: List[str] = list(node_lookup.keys())

    return render_template("tree_content.html", version=version, node_lookup=node_lookup, node_order=node_order)
