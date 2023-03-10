from flask import Flask

from app.models import db
from sqlalchemy import inspect

from app.utils.db.source_loader import SourceManager
import app.utils.db.create as db_create
import app.utils.db.destroy as db_destroy
import app.utils.db.read as db_read
from app.utils.db.util import app_config_selector

import argparse
import os
import time

import sys

# ---------------------------------------------------------------------------------------------------------------------


def main():

    # optional avenue of command-line instead of text-ui
    parser = argparse.ArgumentParser("Builds the DB with all content from the local disk JSONs.")
    parser.add_argument("--config", help="The database configuration to use (from app/conf.py).")
    args = parser.parse_args()

    # perform config selection, can fail on bad cmdline pick
    try:
        app_config = app_config_selector(args.config)
    except Exception as ex:
        print(f"Invalid command-line selection made:\n{ex}")
        sys.exit(1)

    print("\n------------------------------------------------\n")

    app = Flask(__name__)
    app.config.from_object(app_config)
    db.init_app(app)
    with app.app_context():

        # BUILD MODE --------------------------------------------------------------------------------------------------
        full_build_mode = os.getenv("FULL_BUILD_MODE", "overwrite")

        # "preserve" : don't touch DB if it has at least 1 version already
        if full_build_mode == "preserve":

            print(f"FULL_BUILD_MODE = {full_build_mode} -> Checking DB Content")
            try:
                inspector = inspect(db.engine)
                attack_ver_exists = inspector.has_table("attack_version")
                if attack_ver_exists:
                    versions_installed = db_read.attack.versions()
                else:
                    versions_installed = []
            except Exception as ex:
                print(f"Failed to read what ATT&CK content is currently installed in the DB - due to:\n{ex}")
                sys.exit(1)
            print(f"  - Versions Present: {', '.join(versions_installed) or '<none>'}")

            # leave content alone
            if len(versions_installed) != 0:
                print("  - Preserving DB content")
                print("\n------------------------------------------------\n")
                sys.exit(0)

            # will install
            else:
                print("  - Will populate DB")

        # *missing* : Overwrite DB
        else:
            print(f"FULL_BUILD_MODE = {full_build_mode} -> Overwriting DB")

        print("\n------------------------------------------------\n")

        # RESOURCE LOADING --------------------------------------------------------------------------------------------

        utils_dir = os.path.dirname(os.path.realpath(__file__))
        sources_dir = os.path.join(utils_dir, "../../jsons/source/")
        src_mgr = SourceManager(sources_dir)

        print("Loading sources..")

        print("\n------------------------------------------------\n")
        # Role - required

        if src_mgr.role.load_validate():
            print("Role loaded.")
        else:
            print("Role is needed for Decider to function. Exiting.")
            sys.exit(2)

        print("\n------------------------------------------------\n")
        # User - required

        if not src_mgr.user.load_validate():
            print("User is needed for Decider to function. Exiting.")
            sys.exit(3)
        elif len(src_mgr.user.get_data()) == 0:
            print("At least one user must be defined in the user.json file. Exiting.")
            sys.exit(4)
        else:
            print("User loaded.")

        print("\n------------------------------------------------\n")
        # ATT&CK content - 1+ required

        attack_versions = {v for v in src_mgr.attack.keys() if src_mgr.attack[v].load_validate()}
        if len(attack_versions) == 0:
            print("Failed to load any ATT&CK versions. At least one is needed for Decider to work. Exiting.")
            sys.exit(5)
        else:
            print(f"Loaded ATT&CK content for versions: {attack_versions}")

        print("\n------------------------------------------------\n")
        # Tree content - 1+ (after intersection with ATT&CK content) required

        tree_versions = {v for v in src_mgr.tree.keys() if src_mgr.tree[v].load_validate()}
        install_versions = attack_versions.intersection(tree_versions)
        if len(install_versions) == 0:
            print("Failed to load ATT&CK content and Tree content (questions / answers) for the same ATT&CK version.")
            print("These datasets must be loaded in pairs.")
            print(f"ATT&CK Versions Loaded: {attack_versions}")
            print(f"Tree Versions Loaded: {tree_versions}")
            print("Exiting.")
            sys.exit(6)
        else:
            print(f"Loaded Tree content (questions / answers) for versions: {tree_versions}")
            print(
                f"Will be installing versions: {install_versions}."
                "\nAs both ATT&CK data and Tree data must exist to install a version."
            )

        print("\n------------------------------------------------\n")
        # CoOccurrences - optional per-version (only installs if version will install with ATT&CK+Tree content)

        co_oc_versions = {
            v
            for v in set(install_versions).intersection(
                set(src_mgr.co_ocs.keys())
            )  # only try and load CoOcs for versions to install
            if src_mgr.co_ocs[v].load_validate()  # ensure load passes
        }
        if len(co_oc_versions) != 0:
            print(f"Loaded and will install CoOccurrences for versions: {co_oc_versions}")
        else:
            print("CoOccurrences will not be installed for any versions.")

        print("\n------------------------------------------------\n")
        # AKAs - optional per-version (only installs if version will install with ATT&CK+Tree content)

        akas_versions = {
            v
            for v in set(install_versions).intersection(
                set(src_mgr.akas.keys())
            )  # only try and load AKAs for versions to install
            if src_mgr.akas[v].load_validate()  # ensure load passes
        }
        if len(akas_versions) != 0:
            print(f"Loaded and will install AKAs for versions: {akas_versions}")
        else:
            print("AKAs will not be installed for any versions.")

        print("\n------------------------------------------------\n")
        # Mismappings - optional per-version (only installs if version will install with ATT&CK+Tree content)

        mismap_versions = {
            v
            for v in set(install_versions).intersection(
                set(src_mgr.mismaps.keys())
            )  # only try and load Mismaps for versions to install
            if src_mgr.mismaps[v].load_validate()  # ensure load passes
        }
        if len(mismap_versions) != 0:
            print(f"Loaded and will install Mismappings for versions: {mismap_versions}")
        else:
            print("Mismappings will not be installed for any versions.")

        print("\n------------------------------------------------\n")
        # Carts - optional and across all versions

        carts_loaded = src_mgr.cart.load_validate()
        if carts_loaded:
            print("Provided carts will be added to the DB as possible")
            print("    (as carts depend on users and attack versions)")
        else:
            print("Carts did not load and will not be added to the DB during this build.")

        print("\n------------------------------------------------\n")

        # INSTALL INFO PRINT-OUT --------------------------------------------------------------------------------------

        print("Install Detail:")
        print(" + Role")
        print(" + User")
        for version in install_versions:
            print(f" + ATT&CK Version {version}:")
            if version in co_oc_versions:
                print("    + CoOccurrences")
            if version in akas_versions:
                print("    + AKAs")
            if version in mismap_versions:
                print("    + Mismappings")
        if carts_loaded:
            print(" + Cart")

        print("\n------------------------------------------------\n")

        # BUILDING PROCESS --------------------------------------------------------------------------------------------

        t0 = time.time()

        # remake tables
        try:
            db_destroy.all_tables()
            db_create.all_tables()
        except Exception as ex:
            tfail = time.time() - t0
            print(f"Failed to recreate tables at {tfail:.1f}s into build - due to:\n{ex}")
            sys.exit(7)

        # add Roles and Users
        try:
            db_create.role.add_all(src_mgr)
            db_create.user.add_all(src_mgr)
        except Exception as ex:
            tfail = time.time() - t0
            print(f"Failed to add Roles and Users at {tfail:.1f}s into build - due to:\n{ex}")
            sys.exit(8)

        for version in install_versions:
            print(f"\nAdding ATT&CK content for version {version}\n")

            # ATT&CK + Tree content
            try:
                db_create.attack.add_version(version, src_mgr)
            except Exception as ex:
                tfail = time.time() - t0
                print(
                    f"Failed to add ATT&CK/Tree content for version {version}"
                    f" at {tfail:.1f}s into build - due to:\n{ex}"
                )
                sys.exit(9)

            # AKAs
            if version in akas_versions:
                try:
                    db_create.akas.add_version(version, src_mgr)
                except Exception as ex:
                    tfail = time.time() - t0
                    print(f"Failed to add AKAs for version {version} at {tfail:.1f}s into build - due to:\n{ex}")
                    sys.exit(10)

            # CoOccurrences
            if version in co_oc_versions:
                try:
                    db_create.coocs.add_version(version, src_mgr)
                except Exception as ex:
                    tfail = time.time() - t0
                    print(
                        f"Failed to add ATT&CK/Tree content for version {version}"
                        f" at {tfail:.1f}s into build - due to:\n{ex}"
                    )
                    sys.exit(11)

            # Mismappings
            if version in mismap_versions:
                try:
                    db_create.mismaps.add_version(version, src_mgr)
                except Exception as ex:
                    tfail = time.time() - t0
                    print(
                        f"Failed to add ATT&CK/Tree content for version {version}"
                        f" at {tfail:.1f}s into build - due to:\n{ex}"
                    )
                    sys.exit(12)

        # carts
        if carts_loaded:
            try:
                print("\nAdding Carts\n")
                db_create.cart.add_all(src_mgr)
            except Exception as ex:
                tfail = time.time() - t0
                print(f"Failed to add Carts at {tfail:.1f}s into build - due to:\n{ex}")
                sys.exit(13)

        print("\n------------------------------------------------\n")
        tdone = time.time() - t0
        print(f"SUCCESS - Full Build Complete In: {tdone:.1f}s!")


if __name__ == "__main__":
    main()
