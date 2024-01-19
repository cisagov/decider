import logging
from flask import Blueprint, render_template, g

from app.routes.utils import is_attack_version, outedit_markdown, outgoing_markdown
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
    answer_md: str
    question_md: str
    has_children: bool


@tree_content_.route("/tree_content/<version>", methods=["GET"])
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

    nodes: List[TreeNode] = [
        TreeNode(
            type="tactic" if id.startswith("TA") else "technique",
            id=id,
            name=name,
            answer_md=outedit_markdown(answer or ""),
            question_md=outedit_markdown(question or ""),
            has_children=True if id.startswith("TA") else has_children[id],
        )
        for id, name, answer, question in iter_chain(tactics, techniques)
    ]

    for n in nodes:
        print(n)

    return render_template("tree_content.html")
