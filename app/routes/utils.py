"""
This variant of utils CANNOT import anything from app.models / use app variables, but utils_db.py can
This allows the functions here to be usable in app-less / model-less contexts (like initial_setup.py)
"""

import re
import markdown
import bleach
import html
from bs4 import BeautifulSoup

from functools import wraps as functools_wraps

import logging

logger = logging.getLogger(__name__)

# 1-10 digit limits to prevent logs of purposely invalid requests with fake versions, should last many eternities
ATTACK_VERSION_REGEX_P = re.compile(r"v[0-9]{1,10}\.[0-9]{1,10}")  # v{int}.{int}

TACTIC_ID_REGEX_P = re.compile(r"TA[0-9]{4}")  # TAnnnn

TECHNIQUE_ID_REGEX_P = re.compile(r"T[0-9]{4}(\.[0-9]{3})?")  # Tnnnn(.nnn)
BASE_TECHNIQUE_ID_REGEX_P = re.compile(r"T[0-9]{4}")  # Tnnnn
SUB_TECHNIQUE_ID_REGEX_P = re.compile(r"T[0-9]{4}\.[0-9]{3}")  # Tnnnn.nnn


def is_attack_version(s):
    """Returns Match/None on if 's' fits the format of an ATT&CK version string"""
    return ATTACK_VERSION_REGEX_P.fullmatch(s)


def is_tact_id(s):
    """Returns Match/None on if 's' fits the format of an ATT&CK Tactic ID string"""
    return TACTIC_ID_REGEX_P.fullmatch(s)


def is_tech_id(s):
    """Returns Match/None on if 's' fits the format of an ATT&CK Technique ID string"""
    return TECHNIQUE_ID_REGEX_P.fullmatch(s)


def is_base_tech_id(s):
    """Returns Match/None on if 's' fits the format of an ATT&CK BaseTechnique ID string
    - "Base" meaning any Technique that isn't a SubTechnique
    """
    return BASE_TECHNIQUE_ID_REGEX_P.fullmatch(s)


def is_sub_tech_id(s):
    """Returns Match/None on if 's' fits the format of an ATT&CK SubTechnique ID string"""
    return SUB_TECHNIQUE_ID_REGEX_P.fullmatch(s)


# old python regex: r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)"
# the regex below is the more comprehensive one from the front-end
EMAIL_REGEX_P = re.compile(
    r"""(([^<>()\[\]\\.,;:\s@"]+(\.[^<>()\[\]\\.,;:\s@"]+)*)|(".+"))@"""
    r"""((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))"""
)


def build_url(technique, tactic_context, version_context, end=False):
    """Forms URL pointing to a Technique success/question page
    - The Tactic and Version in which the Technique lives are to be specified
    - end denotes whether the success page (end=True) or the question page (end=False) is shown for Techs with subs
      - end can also be truthy / falsey

    technique       : Twxyz, Twxyz.abc
    tactic_context  : TAwxyz, TA0000 (no_tactic page, accessed via search)
    version_context : whatever valid version strings exist in the DB
    """

    # Tactic page
    if technique is None:
        return f"/question/{version_context}/{tactic_context}"
    tech_id = technique.tech_id

    # Tactic-less Tech/Sub, always a success page (no question page exists without being in-tree)
    if tactic_context == "TA0000":
        return f"/no_tactic/{version_context}/{tech_id.replace('.', '/')}"

    # Subtech, always a success page (no children to navigate to)
    if "." in tech_id:
        return f"/question/{version_context}/{tactic_context}/{tech_id.replace('.', '/')}"

    # Tech success page (end reqested OR tech has no question leading to subtechs)
    if end or (not technique.tech_question):
        return f"/question/{version_context}/{tactic_context}/{tech_id}"

    # Tech to Subtech question page
    return f"/question/{version_context}/{tactic_context}/{tech_id}/QnA"


def incoming_markdown(unsafe_html):
    """Escapes MD HTML-wise (as it is intended to be displayed on the site at some point)"""
    return html.escape(unsafe_html)


def outgoing_markdown(database_md):
    """Renders MD to an HTML subset

    - Only text, lists, links, and codeblocks can be used
    - Prevents XSS vulns as well
    """

    # Gives us some control on spacing
    spaced_out = "\n".join(("<br>" if ln == "\\ " else ln) for ln in database_md.split("\n"))

    # Converts stored MarkDown into HTML to be used
    # with Jinja |safe in template rendering / JS inserting into DOM
    gen_html = markdown.markdown(spaced_out, extensions=["sane_lists"])  # Renders MD to HTML
    clean_html = bleach.clean(  # Keep only the generated tags we want
        gen_html,
        tags=[
            "br",
            "b",
            "strong",
            "i",
            "em",
            "code",
            "a",
            "p",
            "ul",
            "ol",
            "li",
            "sup",
        ],
        attributes={"a": ["href"]},
        strip=True,
    )

    # Adds [target="_blank" rel="noreferrer noopener"] attributes to external links
    soup = BeautifulSoup(clean_html, "lxml")
    for link in soup.find_all("a"):
        if not link.attrs.get("href", "").startswith("/"):
            link.attrs["target"] = "_blank"
            link.attrs["rel"] = "noreferrer noopener"

    # Allows for contents of code tags to not be double escaped
    for code in soup.find_all("code"):
        code.string = html.unescape(code.string or "")

    # Warn if content missing
    return soup.find("body").decode_contents() if soup.find("body") else "<mark>MISSING CONTENT</mark>"


def outedit_markdown(database_md):
    """Unescapes MD (as it is to be used in an editing box)"""
    return html.unescape(database_md)


def trim_keys(keep_keys, list_of_dict):
    """Returns a modified list of dicts to where each dict only has keys specified in keep_keys

    keep_keys: set
    - specifies what keys to keep for each entry in list_of_dict
    - when empty, all keys are kept

    list_of_dict: list[dict]
    - list of dictionaries that will be trimmed by keep_keys

    returns list[dict]
    """

    # trim specified
    if len(keep_keys) > 0:
        trimmed = [{k: v for k, v in entry.items() if k in keep_keys} for entry in list_of_dict]

    # keep all keys
    else:
        trimmed = list_of_dict
    return trimmed


def email_validator(email):
    """Returns a bool describing if an email address is valid (length <= 320 and passes regex)"""
    if len(email) > 320:
        return False
    return bool(EMAIL_REGEX_P.fullmatch(email))


def password_validator(password, max_len=48):
    """Returns a bool describing if a password is valid

    Imposed Requirements:
    - 8 <= Length <= max_len (48 for Decider App passwords)
    - Only contains " " through "~" in an ASCII table
    - Has 2 lower-case
    - Has 2 upper-case
    - Has 2 numbers
    - Has 2 specials
    """

    plen = len(password)

    if plen not in range(8, max_len + 1):
        return False

    filtered_len = sum(1 for c in password if ("\x20" <= c <= "\x7E"))
    if plen != filtered_len:
        return False

    num_lowers = sum(1 for c in password if c.islower())
    if num_lowers < 2:
        return False

    num_uppers = sum(1 for c in password if c.isupper())
    if num_uppers < 2:
        return False

    num_numbers = sum(1 for c in password if c.isnumeric())
    if num_numbers < 2:
        return False

    num_specials = plen - (num_lowers + num_uppers + num_numbers)
    if num_specials < 2:
        return False

    return True


class DictValidator:
    """Validates a dictionary given a schema specifying fields, their types, and validation functions

    spec is a dictionary, where keys are expected fields and the values are dictionaries describing requirements
    fields in dict_ but not present in spec are considered unexpected fields - and cause success=False and error msgs

    example_spec = {
        "email": dict(optional=False, type_=str, validator=email_validator),
        "password": dict(optional=False, type_=str, validator=password_validator),
        "role": dict(optional=False, type_=int),
    }

    All spec fields themselves are optional, {} is a valid spec value

    optional  : (default=False), Specifies if the field is allowed to be missing from the dict_
    type_     : (default unchecked), Specifies if the field is required to be a type, or within a list/tuple of types
    validator : (default unchecked), Specifies a function to call with the value of the field to further check it
        A validator() function can return either of 2 formats
        - bool : A basic True/False check, an error message saying the field is invalid will be added on fail
        - dict : True/False check + list of string errors to report: {"success": False, "errors": ["Password..", ..]}

    Usage: call this with a dict_ and spec - then access .success, .errors for branching logic / logging
    """

    def __init__(self, dict_, spec):
        self.dict_ = dict_
        self.spec = spec

        self.success = True
        self.errors = []

        # all fields in spec are checked (dependency: presence -> type -> validity)
        for field in spec.keys():
            if self.check_field_presence(field):
                if self.check_field_type(field):
                    self.check_field_validity(field)

        # presence of field not in spec is bad (add to spec with optional=True if it sometimes appears)
        for unexpected_field in set(dict_.keys()) - set(spec.keys()):
            self.success = False
            self.errors.append(f'Unexpected field "{unexpected_field}" was present.')

    def check_field_presence(self, field):
        # fails if the field is not in the dict_ (if field isn't optional)

        optional = self.spec[field].get("optional", False)
        if (field not in self.dict_) and (not optional):
            self.success = False
            self.errors.append(f'Field "{field}" was missing - however, it must be present.')
            return False

        return True

    def check_field_type(self, field):
        # fails if the field isn't the specified type / in the specified list|tuple of types (pass if not provided)

        type_ = self.spec[field].get("type_", None)
        if type_:
            type_ = tuple(type_) if isinstance(type_, (tuple, list)) else (type_,)  # tuplify
            value = self.dict_[field]

            if not isinstance(value, type_):
                self.success = False
                types_allowed = f"[{', '.join([t.__name__ for t in type_])}]"  # ex: [int, str, ..]
                self.errors.append(
                    f'Field "{field}" was a(n) {type(value).__name__} - which is not in {types_allowed}.'
                )
                return False

        return True

    def check_field_validity(self, field):
        # fails if the provided validator() function fails (pass if not provided)

        validator_func = self.spec[field].get("validator", None)
        if validator_func is not None:
            value = self.dict_[field]
            valid_check = validator_func(value)

            # basic True/False test response
            if isinstance(valid_check, bool):
                self.success = self.success and valid_check
                if not valid_check:
                    self.errors.append(f'Field "{field}" is invalid.')
                    return False

            # test response with T/F 'success' field and list of strings 'errors' field
            elif isinstance(valid_check, dict):
                self.success = self.success and valid_check["success"]
                if not valid_check["success"]:
                    self.errors.extend(valid_check["errors"])
                    return False

        return True


def checkbox_filters_component(kind, options, clear_func, update_func, different_name=None):
    """List-of-checkboxes-based HTML component intended for filtering information on the page

    Used in tandem with a Jinja template and JS functionality

    kind: (str) provides a namespace for the component
    - keeping these unique app-wide is important as they are persisted via session-storage
      - keeping filtering options page-to-page is common, this makes that easy

    different_name: (str, None) allows setting a customized title not based-on "kind"
    - not setting this results in the component having the title: "Filter {kind}s"

    options: list[str] of toggleable checkbox names

    clear_func:  (str) JavaScript for onclick of "Reset Selections" button
    update_func: (str) JavaScript for onclick of each individual checkbox

    -- Example Appearance Below --

    Filter Platforms  <- generated title when kind="Platform"
    -----------------
    ( ) Linux
    ( ) Windows       <- clicking this calls update_func as JS (use func(this) to track the clicked checkbox in JS)
    ( ) macOS
    ( ) ...
    ( ) Azure AD
    -----------------
    [Reset Selection] <- clicking this calls clear_func as JS
    """

    return {
        f"{kind}_filters": {
            "kind": kind,
            "title_name": different_name if different_name else kind,
            "items": [{"internal_name": o.replace(" ", "_").lower(), "human_name": o} for o in options],
            "funcs": {"clear": clear_func, "update": update_func},
        }
    }


class ErrorDuringRoute(Exception):
    """
    Base Exception for ErrorDuringHTMLRoute / ErrorDuringAJAXRoute
        that wraps an error thrown during the processing of a route function
    Children of this are named after the response type that the routes they decorate have
    This signals informing the client of an error in the proper format
    """

    pass


class ErrorDuringHTMLRoute(ErrorDuringRoute):
    """
    Exception wrapper signaling that an error occurred when trying to form an HTML response
    This instructs global error handling to send an HTML response after handling the error

    If a jsonify(message="..."), 500 were sent instead - the user would have a plaintext page... bad
    """

    pass


class ErrorDuringAJAXRoute(ErrorDuringRoute):
    """
    Exception wrapper signaling that an error occurred when trying to form an AJAX/JSON/Partial-Page response
    This instructs global error handling to send a JSON response after handling the error

    If a render_template("..."), 500 were sent instead - the user would get a whole page inside of a Bulma Toast... bad
    """

    pass


def wrap_exceptions_as(new_ex):
    """
    Decorator that will catch any uncaught exceptions from the function it decorates and wrap them as new_ex
    Routes either produce a whole HTML page, or an AJAX/JSON/Partial-Page response
    Wrapping uncaught exceptions with context means that the appropriate response type (JSON vs HTML) can be
        used to convey the error to the client
    See ErrorDuringHTMLRoute & ErrorDuringAJAXRoute for explanation as to why wrong response types are bad
    """

    def decorator(fn):
        @functools_wraps(fn)  # prevents modifying the function signature (becomes wrapper(), which kills Flask routes)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception as old_ex:
                raise new_ex from old_ex  # ErrorDuring____.__cause__ is the wrapped Exception

        return wrapper

    return decorator
