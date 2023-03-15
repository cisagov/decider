# Decider

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

```
git clone https://github.com/cisagov/decider.git
cd decider
cp .env.example .env
[sudo] docker compose up
```
*sudo for Linux only*

It is ready when **Starting uWSGI** appears
![Decider on Docker Boot Terminal Output](./docs/imgs/docker-started-1.0.0.png)

Then visit http://localhost:8001/

(Endpoint set via .env vars: http://`WEB_IP`:`WEB_PORT`/)

Default Login:
- Email: admin@admin.com
- Password: admin

And note: Postgres stores its data in a Docker volume to persist the database.

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

**Read the [Admin Guide](./docs/Decider_Admin_Guide_v1.0.0.pdf)**

There are some issues in the instructions... ***Working on it, simplifying them***

Help Tips:
- Use Python 3.8.10 / 3.8.x on Linux / mac
- Follow the order of instructions
- Watch out using `sudo` with `python` - it won't keep the venv you're in by default
- If just running for yourself locally:
  - Don't create a system account for decider
  - Don't use uWSGI
  - Use the built-in debug Flask server
- Mac M1 users should install Postgres before installing the pip requirements
  - `brew install postgresql`
  - **Explained:** *psycopg2-binary* isn't using a pre-built binary and tries to compile from scratch, and it can't find *pg_config*.
