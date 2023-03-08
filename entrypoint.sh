#!/bin/sh
# ensure environment variables are set 
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
if [ -z "$DB_USERNAME" ]; then
    echo "DB_USERNAME is not set"
    exit 1
fi
if [ -z "$DB_PASSWORD" ]; then
    echo "DB_PASSWORD is not set"
    exit 1
fi
if [ -z "$CART_ENC_KEY" ]; then
    echo "CART_ENC_KEY is not set"
    exit 1
fi
if [ -z "$ADMIN_EMAIL" ]; then
    echo "ADMIN_EMAIL is not set"
    exit 1
fi
if [ -z "$ADMIN_PASS" ]; then
    echo "ADMIN_PASS is not set"
    exit 1
fi

python initial_setup.py

# initialise the database.
# TODO: make sure this doesn't overwrite existing data
python -m app.utils.db.actions.full_build 

# run the app (DEVELOPMENT MODE)
# python decider.py

# run the app (PRODUCTION MODE)
uwsgi --socket 0.0.0.0:5000 --protocol=http -w decider:app