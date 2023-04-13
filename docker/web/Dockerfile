FROM python:3.8-bullseye

# install dir
WORKDIR /opt/decider

# for CRLF -> LF
RUN apt-get update && \
    apt-get install dos2unix

# pip reqs
COPY ["./requirements-pre.txt", "./requirements.txt", "./"]
RUN pip install --no-cache-dir -r requirements-pre.txt && \
    pip install --no-cache-dir -r requirements.txt

# app files
COPY ["./app", "./app"]
COPY ["./decider.py", "./docker/web/root_files/*", "./"]

# perform CRLF -> LF
RUN dos2unix entrypoint.sh

ENTRYPOINT ["/bin/sh", "entrypoint.sh"]
