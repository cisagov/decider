# CentOS 7


## Install Note
- Assumes terminal bracketed paste mode is off, hence the `;\` everywhere
  - Without these, a sudo prompt eats later lines of a pasted block
- Some files are created during the installation (in current dir)
  - Best to give yourself a temp dir
  - Make sure to delete this temp folder post-intall
```bash
cd ;\
mkdir decider_temp ;\
cd decider_temp
```


## Install Instructions


### Add Yourself to Sudoers
- Administrators are likely already in there
```bash
su
EDITOR=nano visudo

# Comment-block is editor view (Scroll Down)
# user "damion" was added in this example

# ## Allow root to run any commands anywhere
# root    ALL=(ALL)	ALL
# damion  ALL=(ALL)	ALL

exit
```


### Update Package Sources
- Ensures package listing is up-to-date
```bash
yum check-update
```


### Create Decider Service Account + Group
- Dedicated no-home, no-login, shell-less user prevents app from accessing more
```bash
sudo adduser --no-create-home --system --shell /bin/false decider ;\
sudo usermod -L decider ;\
sudo groupadd decider ;\
sudo usermod -aG decider decider
```


### Install PostgreSQL
- Adds postgres to repositories (GPG keys too), then installs and enables it
```bash

sudo yum -y install https://download.postgresql.org/pub/repos/yum/reporpms/EL-7-x86_64/pgdg-redhat-repo-latest.noarch.rpm ;\
sudo yum -y list postgres* ;\
sudo yum -y install postgresql12 postgresql12-server postgresql12-contrib postgresql12-libs ;\
sudo systemctl enable postgresql-12
```


### Initialize &amp; Start Postgres
```bash
sudo /usr/pgsql-12/bin/postgresql-12-setup initdb ;\
sudo systemctl restart postgresql-12 ;\
sudo systemctl status postgresql-12
```


### Clone Repository
```bash
sudo yum install -y git ;\
git clone https://github.com/cisagov/decider.git
```


### Compress Static Assets (JS/CSS/etc)
```bash
find decider/app/static/ -type f -not -name "*.gz" -exec gzip -9fk {} +
```


### Install PCRE (for uWSGI Compressed Static Handling)
```bash
sudo yum install pcre pcre-devel
```


### Copy Repository to Install Directory
```bash
sudo mkdir /opt/decider ;\
sudo cp -a ./decider/. /opt/decider ;\
sudo chown -R decider:decider /opt/decider
```


### Install Python 3.8.10 (as CentOS 7 has Python 3.6.8)
- Useful as a means of isolation as well (never depends on system versions)
- [Build Dependencies Reference](https://devguide.python.org/getting-started/setup-building/index.html#install-dependencies)
```bash
sudo yum groupinstall -y 'Development Tools' ;\
sudo yum install -y yum-utils openssl-devel ;\
sudo yum-builddep -y python3 ;\
wget https://www.python.org/ftp/python/3.8.10/Python-3.8.10.tar.xz ;\
tar -xf Python-3.8.10.tar.xz ;\
cd Python-3.8.10 ;\
./configure --prefix=/opt/decider/python3.8.10 --exec_prefix=/opt/decider/python3.8.10 --enable-optimizations ;\
sudo mkdir /opt/decider/python3.8.10 ;\
sudo make altinstall ;\
sudo chown -R decider:decider /opt/decider/python3.8.10 ;\
cd ..
```


### Create &amp; Populate virtualenv
- Useful instead of installing directly into Decider's own Py3.8.10 - as future versions could change packages in use
```bash
sudo -u decider -g decider /opt/decider/python3.8.10/bin/python3.8 -m \
    venv /opt/decider/venv/ ;\
sudo -u decider -g decider /opt/decider/venv/bin/python -m \
    pip --no-cache-dir install -r /opt/decider/requirements-pre.txt ;\
sudo -u decider -g decider /opt/decider/venv/bin/python -m \
    pip --no-cache-dir install -r /opt/decider/requirements.txt
```


### Create user.json file &amp; Initialize DB
- Set passwords in .env after copy command
```bash
sudo -u decider -g decider cp /opt/decider/.env.manual /opt/decider/.env ;\
sudo -u decider -g decider chmod 660 /opt/decider/.env ;\
sudo -u decider -g decider /opt/decider/venv/bin/python /opt/decider/initial_setup.py ;\
sudo -i -u postgres psql -a -f /opt/decider/init.sql ;\
sudo -u decider -g decider rm /opt/decider/init.sql
```


### Modify Postgres's Authentication Away From Ident
- Our user uses a password, it is not a system account
  - SQLAlchemy connects to Postgres over ipv4 or ipv6 - which is 'host' type
  - Solves problem of `(psycopg2.OperationalError) FATAL:  Ident authentication failed for user "deciderdbuser"`
```bash
# shows file location (already in next command)
sudo -i -u postgres psql -U postgres -c 'SHOW hba_file' ;\
sudo -i -u postgres nano /var/lib/pgsql/12/data/pg_hba.conf ;\
sudo -i -u postgres psql -c 'SELECT pg_reload_conf()';

# EDIT TO MAKE WHEN EDITOR APPEARS (Scroll Down)
#
# # TYPE  DATABASE        USER            ADDRESS                 METHOD
#
# # "local" is for Unix domain socket connections only
# local   all             all                                     peer
# # IPv4 local connections:
# host    all             all             127.0.0.1/32            ident  <---CHANGE-TO- scram-sha-256 --|
# # IPv6 local connections:
# host    all             all             ::1/128                 ident  <---CHANGE-TO- scram-sha-256 --|
# # Allow replication connections from localhost, by a user with the
# # replication privilege.
# local   replication     all                                     peer
# host    replication     all             127.0.0.1/32            ident
# host    replication     all             ::1/128                 ident
```


### Configure Logging
- Logs DEBUG to decider.log and stdout by default
- [Configuring Logging](https://docs.python.org/3.8/howto/logging.html#configuring-logging)
```bash
# (optional)
# sudo -u decider -g decider nano --restricted /opt/decider/config/logging.json
```


### Configure Content to be Built onto the DB (optional)
- ATT&amp;CK Enterprise v11.0 & v12.0 are built by default (as of Mar 2023)
  - This includes co-occurrences for each version (**Frequently Appears With** on Tech success pages)
- Configuration Information
  - Visit the **Admin Guide** (Decider_Admin_Guide_v1.0.0.pdf in docs)
  - Go to the section **Database Setup** (bottom of page 12)


### Build Database
```bash
cd /opt/decider/ ;\
sudo -u decider -g decider /opt/decider/venv/bin/python -m \
    app.utils.db.actions.full_build --config DefaultConfig ;\
sudo -u decider -g decider rm /opt/decider/config/build_sources/user.json
```

### Add Firewall Exception
```bash
sudo firewall-cmd --zone=public --add-port=443/tcp --permanent ;\
sudo firewall-cmd --reload
```


### Generate Self-Signed SSL Cert / Add Your Own
- **If you have your own cert already** - don't run the code, just write these 2 files:
  - /opt/decider/config/certs/decider.key
  - /opt/decider/config/certs/decider.crt
```bash
sudo -u decider -g decider RANDFILE=/opt/decider/config/certs/.rnd openssl genrsa \
    -out /opt/decider/config/certs/decider.key 2048 ;\
sudo -u decider -g decider RANDFILE=/opt/decider/config/certs/.rnd openssl req -new \
    -key /opt/decider/config/certs/decider.key \
    -out /opt/decider/config/certs/decider.csr ;\
sudo -u decider -g decider RANDFILE=/opt/decider/config/certs/.rnd openssl x509 -req -days 365 \
    -in /opt/decider/config/certs/decider.csr \
    -signkey /opt/decider/config/certs/decider.key \
    -out /opt/decider/config/certs/decider.crt
```


### Launch Decider
- Runs as a systemd service
```bash
# (optional - allows tweaking uwsgi threads, decider port, etc)
# sudo -u decider -g decider nano --restricted /opt/decider/uwsgi.ini

# (alternative - Decider can be launched without systemd)
# sudo /opt/decider/venv/bin/uwsgi --ini /opt/decider/uwsgi.ini

sudo cp /opt/decider/decider.service /etc/systemd/system/decider.service ;\
sudo chmod 644 /etc/systemd/system/decider.service ;\
sudo systemctl start decider ;\
sudo systemctl status decider ;\
sudo systemctl enable decider
```
