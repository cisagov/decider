# Decider

## Notifications
- **Manual Install** for Ubuntu &amp; CentOS is much nicer.
- Will be adding information about hardware requirements soon
- Dependencies updated!
  - Python 3.8.16 preferred over 3.8.10
  - Eyeballing apline over bullseye for a safer and smaller python

## What is it?

### The Short

A web application that assists network defenders, analysts, and researchers in the process of mapping adversary behaviors to the MITRE ATT&CK® framework.

### The Long

Decider is a tool to help analysts map adversary behavior to the MITRE ATT&CK framework. Decider makes creating ATT&CK mappings easier to get right by walking users through the mapping process. It does so by asking a series of guided questions about adversary activity to help them arrive at the correct tactic, technique, or subtechnique. Decider has a powerful search and filter functionality that enables users to focus on the parts of ATT&CK that are relevant to their analysis. Decider also has a cart functionality that lets users export results to commonly used formats, such as tables and ATT&CK Navigator™ heatmaps.

### The Screenshots

#### Decider's Question Tree

\(*you are here*\)**\[Matrix > Tactic\]** > Technique > SubTechnique
![Decider's Question Tree Page](./docs/imgs/question-tree-1.0.0.png)

#### Decider's Full Technique Search

Boolean expressions, prefix-matching, and stemming included.
![Decider's Full Technique Search Page](./docs/imgs/full-search-1.0.0.png)

### The Notice

This project makes use of MITRE ATT&CK - [ATT&CK Terms of Use](https://attack.mitre.org/resources/terms-of-use/)

## Usage
**Read the [User Guide](./docs/Decider_User_Guide_v1.0.0.pdf)**

## Installation

### Docker

**Best option for 99% of people**

```bash
git clone https://github.com/cisagov/decider.git
cd decider
cp .env.docker .env

# if you want HTTPS instead of HTTP
# - edit .env
#   + WEB_HTTPS_ON='yes'
# - populate cert / key files
#   + /app/utils/certs/decider.key
#   + /app/utils/certs/decider.crt

[sudo] docker compose up
# sudo for Linux only
```

It is ready when **Starting uWSGI** appears
![Decider on Docker Boot Terminal Output](./docs/imgs/docker-started-1.0.0.png)

**Default Endpoint**: http://localhost:8001/

**Default Login**:
- Email: admin@admin.com
- Password: admin

**Endpoint Determination** (.env vars):
- `WEB_HTTPS_ON=''` -> http://`WEB_IP`:`WEB_PORT`/
- `WEB_HTTPS_ON='anything'` -> https://`WEB_IP`:`WEB_PORT`/

**HTTPS Cert Location**:
- Write these 2 files before `docker compose up` to set your SSL cert up
  - /app/utils/certs/decider.key
  - /app/utils/certs/decider.crt
- If either file is missing, a self-signed cert is generated and used instead

**DB Persistence Note**: Postgres stores its data in a Docker volume to persist the database.

#### Linux tested on:

- Ubuntu Jammy 22.04.2 LTS
- Docker Engine
  - Not Docker Desktop (couldn't get nested-virt in my VM)

#### Windows tested on:

- Windows 11 Home, version 22H2, build 22621.1344
- Home doesn't support HyperV
  - Thus tested on Docker Desktop [via WSL backend](https://docs.docker.com/desktop/windows/wsl/)

#### macOS (M1) tested on:

- macOS Ventura 13.2.1 (22D68)
- Mac M1 Processor
- On Docker Desktop installed via .dmg

### Manual Install

#### Ubuntu 22.04
[Ubuntu Install Guide](docs/install/Ubuntu_22.04.2.md)

#### CentOS 7
[CentOS Install Guide](docs/install/CentOS_7.md)

#### Other OSes
Read the Ubuntu &amp; CentOS guides and recreate actions according to your platform.

##### Windows
`open()` in Python uses the system's default text encoding
- This is `utf-8` on macOS and Linux
- This is `windows-1252` on Windows
  - This causes issues in reading the jsons for the database build process
  - Adding `encoding='utf-8'` as an arg in each `open()` ***may*** allow Windows deployment

##### macOS
(M1 users at least) Make sure to (1) install Postgres before (2) installing the pip requirements
1. `brew install postgresql`
2. `pip install -r requirements.txt`
