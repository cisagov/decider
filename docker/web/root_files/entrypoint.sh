#!/bin/sh

# Colors
COLOR_OFF="\033[0m"
COLOR_IRED="\033[0;91m"
COLOR_IGREEN="\033[0;92m"
COLOR_ICYAN="\033[0;96m"

print_started_text () {
    # https://patorjk.com/software/taag/#p=display&f=ANSI%20Regular&t=Started
    echo "███████ ████████  █████  ██████  ████████ ███████ ██████  "
    echo "██         ██    ██   ██ ██   ██    ██    ██      ██   ██ "
    echo "███████    ██    ███████ ██████     ██    █████   ██   ██ "
    echo "     ██    ██    ██   ██ ██   ██    ██    ██      ██   ██ "
    echo "███████    ██    ██   ██ ██   ██    ██    ███████ ██████  "
    return 0
}

# Required Env Var Presence Check ----------------------------------------------

# database to [connect to, build]
if [ -z "$DB_HOSTNAME" ]; then
    echo "DB_HOSTNAME is not set"
    exit 1
fi
if [ -z "$DB_PORT" ]; then
    echo "DB_PORT is not set"
    exit 1
fi
if [ -z "$DB_DATABASE" ]; then
    echo "DB_DATABASE is not set"
    exit 1
fi

# db admin user (full-access, used in db scripts / normal modes)
if [ -z "$DB_ADMIN_NAME" ]; then
    echo "DB_ADMIN_NAME is not set"
    exit 1
fi
if [ -z "$DB_ADMIN_PASS" ]; then
    echo "DB_ADMIN_PASS is not set"
    exit 1
fi

# db kiosk user (limited read-only, used in kiosk mode)
if [ -z "$DB_KIOSK_NAME" ]; then
    echo "DB_KIOSK_NAME is not set"
    exit 1
fi
if [ -z "$DB_KIOSK_PASS" ]; then
    echo "DB_KIOSK_PASS is not set"
    exit 1
fi

# cart encryption key
if [ -z "$CART_ENC_KEY" ]; then
    echo "CART_ENC_KEY is not set"
    exit 1
fi

# default app admin login
if [ -z "$APP_ADMIN_EMAIL" ]; then
    echo "APP_ADMIN_EMAIL is not set"
    exit 1
fi
if [ -z "$APP_ADMIN_PASS" ]; then
    echo "APP_ADMIN_PASS is not set"
    exit 1
fi

# kiosk mode is off (only kiosk is supported)
if [ -z "$KIOSK_MODE" ]; then
    echo "You set KIOSK_MODE='', this is ignored, as only kiosk is supported in this build."
fi

# ------------------------------------------------------------------------------

cd /opt/decider
. ./venv/bin/activate

# sync config
# - user.json: only copy updates
# - others   : copy updated / new / deleted
echo "Syncing config files"
SOURCES_CHANGED="no"
if rsync -rLKt --delete --exclude 'build_sources/user.json' --out-format='%n' ro_config/* config | grep -q 'build_sources'; then
    SOURCES_CHANGED="yes"
fi
if rsync -rLKt --ignore-missing-args --out-format='%n' ro_config/build_sources/user.json config/build_sources | grep -q 'build_sources'; then
    SOURCES_CHANGED="yes"
fi

# - user-specified additional HTML

if [ -f ro_config/user_additions.html ]; then
    # external present

    echo "user_additions.html in config, copying over"
    cp -f ro_config/user_additions.html app/templates/user_additions.html

else
    # external missing

    if [ -f app/templates/user_additions.html ]; then
        # internal present
        echo "user_additions.html missing in config, present internally, skipping"

    else
        # internal missing
        echo "ERROR: user_additions.html missing in config, and missing internally, please copy default_config/ -> config/"
        exit 1

    fi
fi

# (general) correct ownership
chown -R decider:decider config

# (general) correct permissions
find config -type d -exec chmod 0755 {} +
find config -type f -exec chmod 0644 {} +

# (certs) correct ownership / perms
chown -R root:root config/certs
if [ -f config/certs/decider.crt ]; then
    chmod 644 config/certs/decider.crt
fi
if [ -f config/certs/decider.key ]; then
    chmod 600 config/certs/decider.key
fi

# ------------------------------------------------------------------------------

# create user.json from .env if missing
if [ ! -f config/build_sources/user.json ]; then
    echo "user.json is missing, creating it from env vars."
    python create_user_json.py
fi

# sources changed -> build database
if [ "$SOURCES_CHANGED" = "yes" ]; then
    echo "build_sources changed, rebuilding database."
    python -m app.utils.db.actions.full_build --config DefaultConfig
fi

# HTTP:
if [ -z "$WEB_HTTPS_ON" ]; then

    echo ""
    print_started_text
    echo "Decider as a Kiosk in ${COLOR_IRED}HTTP${COLOR_OFF} mode"
    echo "${COLOR_ICYAN}http://${WEB_IP}:${WEB_PORT}/${COLOR_OFF}\n"
    uwsgi --ini uwsgi-http-kiosk.ini

# HTTPS:
else

    echo "Running in HTTPS mode"

    # Cert Found:
    if [ -f config/certs/decider.crt ] && [ -f config/certs/decider.key ]; then

        echo "SSL Cert Found"

    # Cert Missing:
    else

        echo "SSL Cert Missing - Generating new one"

        # clear (1 could still exist, and .csr to be sure)
        rm -f config/certs/decider.crt config/certs/decider.key config/certs/decider.csr

        # generate
        openssl req \
            -x509 \
            -newkey rsa:4096 \
            -keyout config/certs/decider.key \
            -out config/certs/decider.crt \
            -nodes \
            -sha256 \
            -days 365 \
            -subj "/C=US/ST=Virginia/L=McLean/O=Company Name/OU=Org/CN=www.example.com"
    fi

    echo ""
    print_started_text
    echo "Decider as a Kiosk in ${COLOR_IGREEN}HTTPS${COLOR_OFF} mode"
    echo "${COLOR_ICYAN}https://${WEB_IP}:${WEB_PORT}/${COLOR_OFF}\n"
    uwsgi --ini uwsgi-https-kiosk.ini
fi
