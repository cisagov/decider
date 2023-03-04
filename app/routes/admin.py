import logging
from flask import Blueprint, render_template, request, jsonify, g

from app.models import Cart, db, User, Role
from sqlalchemy import asc, func

from app.routes.profile import admin_permission

from flask_login import current_user
import bcrypt

from app.routes.utils import DictValidator, email_validator, password_validator
from app.routes.utils import ErrorDuringHTMLRoute, ErrorDuringAJAXRoute, wrap_exceptions_as

logger = logging.getLogger(__name__)
admin_ = Blueprint("admin_", __name__, template_folder="templates")


# ---------------------------------------------------------------------------------------------------------------------
# Admin Panel for Adding/Editing/Removing Users


@admin_.route("/admin/user", methods=["GET"])
@admin_permission.require(http_exception=403)
@wrap_exceptions_as(ErrorDuringHTMLRoute)
def admin_user_get():
    """Returns the user editing page (HTML response)"""
    g.route_title = "Admin User Editing Page"

    # get all users, roles they can be, populate template
    logger.debug("querying all Users / Roles")
    users = db.session.query(User).order_by(asc(User.id)).all()
    roles = db.session.query(Role).order_by(asc(Role.role_id)).all()
    logger.debug(f"got {len(users)} Users and {len(roles)} Roles")

    logger.info("serving page")
    return render_template("/edit/users.html", users=users, roles=roles, cur_user_id=current_user.id)


@admin_.route("/admin/user", methods=["POST"])
@admin_permission.require(http_exception=403)
@wrap_exceptions_as(ErrorDuringAJAXRoute)
def admin_user_post():
    """Creates a new user account given email, password, role_id (JSON request, JSON response)"""
    g.route_title = "Admin Create New User"

    try:
        data = request.json
        if not isinstance(data, dict):
            raise Exception()
    except Exception:
        logger.error("request failed - malformed data type")
        return jsonify(message="Request was malformed"), 400

    # ensure all fields present and that password/email meet format
    spec = {
        "email": dict(type_=str, validator=email_validator),
        "password": dict(type_=str, validator=password_validator),
        "role_id": dict(type_=int),
    }
    check = DictValidator(data, spec)
    if not check.success:
        logger.error(f"request failed - malformed fields: {check.errors}")
        return jsonify(message="\n".join(check.errors)), 400

    email = data["email"].lower()
    password = data["password"]
    role_id = data["role_id"]

    # ensure email is new
    logger.debug("querying Users to see if the specified email is already in-use")
    if User.query.filter_by(email=email).first() is not None:
        logger.error(f"request failed - user with email {email} already exists")
        return jsonify(message="A user by this email already exists."), 400

    # validate role existence
    logger.debug("querying Roles to ensure the specified role exists")
    new_user_role = Role.query.filter_by(role_id=role_id).first()
    if new_user_role is None:
        logger.error("request failed - non-existent role_id specified")
        return jsonify(message="Specified role does not exist."), 400

    # get new id, hash pass, add user
    max_user_id = db.session.query(func.max(User.id)).scalar()
    new_user_id = 0 if (max_user_id is None) else (max_user_id + 1)
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    new_user = User(id=new_user_id, email=email, password=hashed.decode("utf-8"), role_id=role_id)
    db.session.add(new_user)

    # attempt to commit
    logger.debug(f"attempting to create a new user [Role: {new_user_role.name}] {email}")
    try:
        db.session.commit()

    except Exception:
        db.session.rollback()
        logger.exception(f"failed to create a new user [Role: {new_user_role.name}] {email}")
        return jsonify(message="Unable to add user"), 400
    logger.info(f"successfully created a new user [Role: {new_user_role.name}] {email}")
    return jsonify({"email": new_user.email, "id": new_user_id}), 200


@admin_.route("/admin/user", methods=["PATCH"])
@admin_permission.require(http_exception=403)
@wrap_exceptions_as(ErrorDuringAJAXRoute)
def admin_user_patch():
    """Updates an existing user's password or role_id given their email (JSON request, JSON response)"""
    g.route_title = "Admin Update User"

    try:
        data = request.json
        if not isinstance(data, dict):
            raise Exception()
    except Exception:
        logger.error("request failed - malformed data type")
        return jsonify(message="Request was malformed"), 400

    # ensure all fields present and that password/email meet format (password can be empty or defined & valid)
    spec = {
        "email": dict(type_=str, validator=email_validator),
        "password": dict(type_=str, validator=lambda p: (not p) or password_validator(p)),
        "role_id": dict(type_=int),
    }
    check = DictValidator(data, spec)
    if not check.success:
        logger.error(f"request failed - fields malformed: {check.errors}")
        return jsonify(message="\n".join(check.errors)), 400

    email = data["email"].lower()
    password = data["password"]
    role_id = data["role_id"]

    # ensure email is of an existing user
    logger.debug("querying Users to ensure the email exists")
    user = User.query.filter_by(email=email).first()
    if user is None:
        logger.error("request failed - specified email does not belong to a user")
        return jsonify(message="A user by this email does not exist."), 400

    # validate new role exists (might be unchanged)
    logger.debug("querying Roles to ensure the role_id exists")
    new_role_obj = Role.query.filter_by(role_id=role_id).first()
    if new_role_obj is None:
        logger.error("request failed - specified role_id does not exist")
        return jsonify(message="Specified role does not exist."), 400

    # same role given, no pass given ... they just clicked "Submit" for no reason
    if (user.role_id == new_role_obj.role_id) and (not password):
        logger.info("request ignored - no new role / password were provided")
        return jsonify(message="The role and password haven't been changed."), 400

    # get old Role name to form descriptive logs
    logger.debug(f"querying old Role name of {user.email}")
    old_role_obj = Role.query.filter_by(role_id=user.role_id).first()

    # log statement portions that describe what changed
    if old_role_obj.role_id != new_role_obj.role_id:
        role_change = f"[Role: {old_role_obj.name} -> {new_role_obj.name}]"
    else:
        role_change = ""
    pass_change = "[Pass Updated]" if password else ""

    # attempt change
    user.role_id = new_role_obj.role_id
    if password:
        hashed_pass = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
        user.password = hashed_pass.decode("utf-8")

    logger.debug(f"attempting to update {user.email}'s details: {role_change}{pass_change}")
    try:
        db.session.commit()

    except Exception:
        db.session.rollback()
        logger.exception(f"failed to update {user.email}'s details: {role_change}{pass_change}")
        return jsonify(message="Unable to save user."), 400
    logger.info(f"successfully updated {user.email}'s details: {role_change}{pass_change}")
    return jsonify(email=user.email), 200


@admin_.route("/admin/user", methods=["DELETE"])
@admin_permission.require(http_exception=403)
@wrap_exceptions_as(ErrorDuringAJAXRoute)
def admin_user_delete():
    """Deletes an existing user given their email (JSON request, JSON response)"""
    g.route_title = "Admin Delete User"

    try:
        email = request.json["email"]
    except Exception:
        logger.error("request failed - malformed data type / fields")
        return jsonify(message="Request was malformed"), 400

    # email missing / undefined
    if not isinstance(email, str):
        logger.error("request failed - user email field must be a string")
        return jsonify(message="email must be a string."), 400

    email = email.lower()

    # validate email & user presence
    if not email_validator(email):
        logger.error("request failed - email field didn't fit the format used by app")
        return jsonify(message="The format of this email is invalid."), 400

    logger.debug("querying to see if User by this email exists")
    user_to_delete = User.query.filter_by(email=email).first()
    if user_to_delete is None:
        logger.error("request failed - email field doesn't match any user")
        return jsonify(message="There is no user with this email."), 400

    # prevent self-deletion
    if current_user.id == user_to_delete.id:
        logger.error(
            "admin undisabled the delete button and edited the page to try and delete themself... ask them why"
        )
        return jsonify(message="No deleting yourself!"), 400

    # clear carts and the user for this email
    db.session.query(Cart).filter(Cart.user == email).delete()
    logger.debug(f"attempting to delete the Carts of {user_to_delete.email}")
    try:
        db.session.commit()
        logger.info(f"successfully deleted the Carts of {user_to_delete.email}")

    except Exception:
        db.session.rollback()
        logger.exception(f"failed to delete the Carts of {user_to_delete.email}")
        return jsonify(message="Failed to delete their carts, user deletion cancelled - please retry"), 500

    db.session.query(User).filter(User.email == email).delete()
    logger.debug(f"attempting to delete {user_to_delete.email}")
    try:
        db.session.commit()
        logger.info(f"successfully deleted {user_to_delete.email}")

    except Exception:
        db.session.rollback()
        logger.exception(f"failed to delete {user_to_delete.email}")
        return jsonify(message="Failed to delete user (did delete their carts though) - please retry"), 500

    return jsonify(), 200


# ---------------------------------------------------------------------------------------------------------------------
