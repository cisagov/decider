# Decider

A web application that assists network defenders, analysts, and researcher in the process of mapping adversary behaviors to the MITRE ATT&CK® framework.

This project makes use of MITRE ATT&CK - [ATT&CK Terms of Use](https://attack.mitre.org/resources/terms-of-use/)

## Notices & Updates

### All Users - Dockerization in Progress
- Deployment is currently unwieldy
- Decider on Docker is currently underway to make deployment easier
  - Completion is tentatively next week

### MacBook M1 Users - Pip Install Woes
- Before `pip install -r requirements.txt`
  - Run `brew install postgresql`
  - This fixes an issue where *psycopg2-binary* isn't using a pre-built binary and tries to compile from scratch. Compilation fails if *pg_config* isn't found.

## Developer Instructions

Before developing, please set up a virtualenv and install the pre-commit git hook scripts.  
Decider uses Black and Flake8 with a line length of 119.  
Please ensure you are using **Python 3.8.10**.

To do this, after cloning the repository, run:

```
sudo apt install -y python3-pip
python3 -m venv venv/
source venv/bin/activate
pip3 install wheel==0.37.1
pip3 install -r requirements.txt
pip3 install -r requirements_dev.txt
pre-commit install
```

## Introduction

Decider is a tool to help analysts map adversary behavior to the MITRE ATT&CK framework. Decider makes creating ATT&CK mappings easier to get right by walking users through the mapping process. It does so by asking a series of guided questions about adversary activity to help them arrive at the correct tactic, technique, or subtechnique. Decider has a powerful search and filter functionality that enables users to focus on the parts of ATT&CK that are relevant to their analysis. Decider also has a cart functionality that lets users export results to commonly used formats, such as tables and ATT&CK Navigator™ heatmaps.

## Background

There are 3 different components to Decider: the PostgreSQL database, the web server (uWSGI), and the Decider application. Decider and its components are tested on Ubuntu 20.04 / CentOS 7. Installation and management should be done on either of these platforms.

### PostgreSQL

#### Installation

This is documented inside of Decider's Admin Guide.

#### Post Installation

-   The database will need a new login made., This login will be used by Decider to make queries. There is no default login for security purposes.
-   You can create a login by running:
    -   `python3 initial_setup.py`
    -   The **Database Setup** section of the Decider Admin Guide has a detailed set of steps to follow.
    -   This script will prompt the user to create two logins and an encryption key (basically a password).
        -   One login is the account Decider will use to query the database.
        -   The other login is the initial admin account to be made. Users will use this to log-in to the Decider app website itself. From here, they can use the user management feature to add more users.
        -   The encryption key is used by Decider to encrypt carts that are stored in the database.

## Configuration Options

Decider is configured by two files:

-   `.env`

    -   Holds secrets; specifically, a PostgreSQL login used by Decider to query the database, and an encryption key that encrypts carts stored on the database.
    -   All fields in `.env.example` must exist/be defined in either `.env` or the environment itself for Decider to launch/run build scripts.
    -   Run `initial_setup.py` to create this file. The script will ask for the creation of two logins and an encryption key.
        -   Users only need to run this if they are setting up a new database.
        -   More information is available in the **Database Setup** section of the Decider Admin Guide.

-   `app/conf.py`
    -   Holds more general configuration options.
    -   There is a set of config classes; one can be chosen when launching the application / building the database.
        -   The fields used in creation of the `SQLALCHEMY_DATABASE_URI` variable can be tweaked:
            -   `host`/`port`: specify the PostgreSQL server endpoint location.
            -   `database`: specifies which DB on the server to use.

### Running

-   Decider can be launched by running the command below.
    -   `python3 decider.py --config CONFIG`
        -   **Note:** this is not to be used in production. Decider uses uWSGI in production as the Flask server is not recommended; it does work just fine for development and testing however.
-   To run Decider in production mode on a server, consult the Decider Admin Guide.

### Database Creation

_(from the root decider_tool/ directory)_

`python -m app.utils.db.actions.full_build [--config CONF]`: /jsons/source **&#8594;** DB

### Postgres Backup and Restore

`pg_dump -U DB_USER -W -F t -h HOSTNAME DB_NAME > decider.sql`

`pg_restore -U DB_USER -W -h localhost -d DB_NAME < app/utils/decider.sql`
