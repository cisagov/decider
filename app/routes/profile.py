import logging.config

from flask_principal import Permission, RoleNeed
from flask import Blueprint, request, redirect, flash, url_for, jsonify, g
from flask_login import current_user
from flask import render_template
import json
from datetime import datetime
import bcrypt

from sqlalchemy import desc
from app.models import AttackVersion, db, Cart
from app.routes.utils import DictValidator, is_tact_id, is_tech_id, password_validator
from app.routes.utils import ErrorDuringHTMLRoute, ErrorDuringAJAXRoute, wrap_exceptions_as

logger = logging.getLogger(__name__)
profile_ = Blueprint("profile_", __name__, template_folder="templates")

# a role mentioned in permission means it has access there
admin_permission = Permission(RoleNeed("admin"))
edit_permission = Permission(RoleNeed("admin"), RoleNeed("editor"))
member_permission = Permission(RoleNeed("admin"), RoleNeed("editor"), RoleNeed("member"))


@profile_.route("/profile", methods=["GET"])
@wrap_exceptions_as(ErrorDuringHTMLRoute)
def profile():
    """Returns the user's profile page (HTML response)

    - Shows their saved carts
    - Shows content editing / user management features if they have editor / admin permissions respectively
    """
    g.route_title = "User Profile Page"

    logger.debug("querying user's carts")
    carts = Cart.query.filter_by(user=current_user.email).order_by(desc(Cart.last_modified)).all()
    cart_list = [{"id": c.cart_id, "name": c.cart_name, "version": c.attack_version} for c in carts]
    logger.debug(f"got {len(cart_list)} Carts")

    logger.info("serving profile page")
    return render_template(
        "profile.html",
        **{
            "data": {
                "user": current_user.email,
                "edit_permission": edit_permission.can(),
                "admin_permission": admin_permission.can(),
                "carts": cart_list,
            }
        },
    )


@profile_.route("/profile/save_cart", methods=["POST"])
@wrap_exceptions_as(ErrorDuringAJAXRoute)
def save_cart():
    """Saves a cart to the DB

    JSON Request:
    - dict of cart title, version, and entries
    - entries is a list of dicts

    JSON Response:
    - 500 -> DB save / server error
    - 400 -> bad request
    - 200 -> saved / updated
    """
    g.route_title = "Save Cart"

    # ensure base request fields exist
    # - stripped title isn't "" (still allows leading/trailing space)
    # - version exists
    # - cart cannot be empty
    try:
        data = request.json
        if not isinstance(data, dict):
            raise Exception()
    except Exception:
        logger.error("request failed - malformed data type")
        return jsonify(message="Request was malformed"), 400

    spec = {
        "title": dict(type_=str, validator=lambda t: len(t.strip()) > 0),
        "version": dict(type_=str, validator=lambda v: AttackVersion.query.get(v) is not None),
        "entries": dict(type_=list, validator=lambda e: len(e) > 0),
    }
    request_validator = DictValidator(data, spec)
    if not request_validator.success:
        logger.error(f"failed to save cart - malformed request: {request_validator.errors}")
        return jsonify(message="Malformed request fields"), 400

    # grab fields
    name = data["title"].strip()
    version = data["version"]
    content = data["entries"]

    # ensure cart entry fields exist and are all strings
    # - index must be a Technique ID
    # - technique "name" musn't be ""
    # - tactic must be a Tactic ID
    # - tacticName musn't be ""
    # NOTE: doesn't actually check presence of the Version-Tactic-Technique combo in DB,
    #       so this could lead to a 404 if somebody manually modifies the cart to use invalid combos / IDs
    for entry_ind, entry in enumerate(content):
        spec = {
            "index": dict(type_=str, validator=lambda i: bool(is_tech_id(i))),
            "name": dict(type_=str, validator=lambda n: len(n) > 0),
            "notes": dict(type_=str),
            "tactic": dict(type_=str, validator=lambda t: bool(is_tact_id(t))),
            "tacticName": dict(type_=str, validator=lambda tn: len(tn) > 0),
        }
        entry_validator = DictValidator(entry, spec)
        if not entry_validator.success:
            logger.error(f"failed to save cart - cart entry #{entry_ind + 1} malformed: {entry_validator.errors}")
            return jsonify(message="Malformed entry found"), 400

    # overwrite existing if found
    logger.debug("querying existing carts to see if user is saving new or updating existing")
    existing_cart = Cart.query.filter_by(user=current_user.email, cart_name=name).first()
    if existing_cart:
        existing_cart.last_modified = datetime.utcnow()
        existing_cart.cart_name = name
        existing_cart.attack_version = version
        existing_cart.cart_content = json.dumps(content)

        try:
            logger.debug("attempting to update existing cart on DB")
            db.session.commit()
            logger.info("successfully updated existing cart on DB")
            return jsonify(message="Overwrote existing cart"), 200

        except Exception:
            db.session.rollback()
            logger.exception("failed to update existing cart on DB")
            return jsonify(message="Database save error"), 500

    # else new cart
    else:
        new_cart = Cart(
            user=current_user.email,
            last_modified=datetime.utcnow(),
            cart_name=name,
            attack_version=version,
            cart_content=json.dumps(content),
        )
        db.session.add(new_cart)

        try:
            logger.debug("attempting to save new cart to DB")
            db.session.commit()
            logger.info("successfully saved new cart to DB")
            return jsonify(message="Saved new cart"), 200

        except Exception:
            db.session.rollback()
            logger.exception("failed to save new cart to DB")
            return jsonify(message="Database save error"), 500


@profile_.route("/profile/load_cart", methods=["POST"])
@wrap_exceptions_as(ErrorDuringAJAXRoute)
def load_cart():
    """Loads a cart given its cart_id (JSON request, JSON response)"""
    g.route_title = "Load Cart"

    # request format validation
    try:
        cart_id = request.json["cart_id"]
    except (TypeError, KeyError):
        logger.exception("failed - malformed request / fields")
        return jsonify(message="Request was malformed."), 400
    if not isinstance(cart_id, int):
        logger.error("failed - cart_id was not an integer")
        return jsonify(message="Cart ID was not an integer."), 400

    # cart existence check
    logger.debug(f"querying for existence of Cart with ID {cart_id}")
    cart = Cart.query.filter_by(cart_id=cart_id).first()
    if cart is None:
        logger.error(f"failed - Cart with ID {cart_id} does not exist")
        return jsonify(message="Specified Cart ID does not exist."), 404
    else:
        logger.debug("cart exists")

    # user owns cart check
    if cart.user != current_user.email:
        logger.error("failed - Cart specified does not belong to the current user")
        return jsonify(message="Specified cart does not belong to you."), 400

    flash("Loaded cart successfully!")
    logger.info("successfully loaded cart")
    return (
        jsonify(
            title=cart.cart_name,
            version=cart.attack_version,
            entries=json.loads(cart.cart_content),
        ),
        200,
    )


@profile_.route("/profile/delete_cart", methods=["POST"])
@wrap_exceptions_as(ErrorDuringAJAXRoute)
def delete_cart():
    """Deletes a cart given its cart_id (JSON request, JSON response)"""
    g.route_title = "Delete Cart"

    # request format validation
    try:
        cart_id = request.json["cart_id"]
    except (TypeError, KeyError):
        logger.exception("failed - malformed request / fields")
        return jsonify(message="Request was malformed."), 400
    if not isinstance(cart_id, int):
        logger.error("failed - cart_id was not an integer")
        return jsonify(message="Cart ID was not an integer."), 400

    # cart existence check
    logger.debug(f"querying for existence of Cart with ID {cart_id}")
    cart = Cart.query.filter_by(cart_id=cart_id).first()
    if cart is None:
        logger.error(f"failed - Cart with ID {cart_id} does not exist")
        return jsonify(message="Specified Cart ID does not exist."), 404
    else:
        logger.debug("cart exists")

    # user owns cart check
    if cart.user != current_user.email:
        logger.error("failed - Cart specified does not belong to the current user")
        return jsonify(message="Specified cart does not belong to you."), 400

    # delete cart
    try:
        logger.debug("attempting to delete cart from DB")
        db.session.delete(cart)
        db.session.commit()
        logger.info("successfully deleted cart from DB")
        return jsonify(), 200

    except Exception:
        db.session.rollback()
        logger.exception("failed to delete cart from DB")
        return jsonify(message="Database commit / update error"), 500


@profile_.route("/profile/carts", methods=["GET"])
@wrap_exceptions_as(ErrorDuringAJAXRoute)
def get_carts():
    """Returns listing of saved carts for logged-in user (JSON response)

    - Each entry has fields "id", "name", "version"
    - 403's for anon user
    """
    g.route_title = "Get Saved Carts"

    logger.debug("querying user's carts")
    carts = Cart.query.filter_by(user=current_user.email).order_by(desc(Cart.last_modified)).all()
    cart_list = [{"id": c.cart_id, "name": c.cart_name, "version": c.attack_version} for c in carts]
    logger.debug(f"got {len(cart_list)} Carts")

    logger.info("serving user a list of the saved Carts they have")
    return jsonify(cart_list), 200


# ---------------------------------------------------------------------------------------------------------------------
# Profile: Password Changing - Page & Post


@profile_.route("/profile/change_password", methods=["GET"])
@wrap_exceptions_as(ErrorDuringHTMLRoute)
def change_password_get():
    """Returns password change page (HTML response)"""
    g.route_title = "Change Password Page"

    logger.info("serving page")
    return render_template("change_password.html", status=200)


@profile_.route("/profile/change_password", methods=["POST"])
@wrap_exceptions_as(ErrorDuringHTMLRoute)
def change_password_post():
    """Processes password change request and redirects user after attempt

    pass -> to profile
    fail -> back to change password page
    """
    g.route_title = "Change Password Request"

    change_pass_url = url_for("profile_.change_password_get")

    # either pass blank
    oldp = request.form.get("old_password", "")
    new1 = request.form.get("new_password_1", "")
    new2 = request.form.get("new_password_2", "")
    if (oldp == "") or (new1 == "") or (new2 == ""):
        flash("One or more fields were left blank, please try again.")
        logger.error("password update failed: 1+ field(s) left blank - front-end checks for this, something's wrong")
        return redirect(change_pass_url)

    # password mismatch
    if new1 != new2:
        flash("Passwords do not match, please try again.")
        logger.error(
            "password update failed: password & confirmation password mismatch "
            "- front-end checks for this, something's wrong"
        )
        return redirect(change_pass_url)

    # password doesn't meet requirements
    if not password_validator(new1):
        flash("Password does not meet requirements, please try again.")
        logger.error(
            "password update failed: proposed password doesn't meet requirements "
            "- front-end checks for this, something's wrong"
        )
        return redirect(change_pass_url)

    # old password doesn't meet requirements (general length check for bcrypt)
    if len(oldp) > 48:
        flash("Old password is malformed.")
        logger.error(
            "password update failed: old password doesn't meet requirements "
            "- front-end checks for this, something's wrong"
        )
        return redirect(change_pass_url)

    # old password doesn't match
    if not bcrypt.checkpw(oldp.encode("utf-8"), current_user.password.encode("utf-8")):
        flash("Old password is incorrect.")
        logger.info("password update skipped: they typed their old password incorrectly")
        return redirect(change_pass_url)

    # all good -> hash and store new pass
    hashed = bcrypt.hashpw(new1.encode("utf-8"), bcrypt.gensalt())
    current_user.password = hashed.decode("utf-8")

    try:
        logger.debug("attempting to save updated password hash to DB")
        db.session.commit()
        logger.info("successfully saved updated password hash to DB")
        flash("Password change successful!")
        return redirect(url_for("profile_.profile"))

    except Exception:
        db.session.rollback()
        logger.exception("failed to save updated password hash to DB")
        flash("Database error - Failed to set new password")
        redirect(change_pass_url)
