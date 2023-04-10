FROM python:3.8-bullseye

RUN mkdir -p /opt/decider

COPY ./requirements-pre.txt ./requirements.txt /opt/decider

RUN pip install --no-cache-dir -r /opt/decider/requirements-pre.txt && \
    pip install --no-cache-dir -r /opt/decider/requirements.txt

COPY ./app /opt/decider/app
COPY ./docker/web/root_files/* /opt/decider
COPY ./decider.py /opt/decider/decider.py

ENTRYPOINT ["/bin/sh", "/opt/decider/entrypoint.sh"]
