# 1. Base image
FROM python:latest
# 2. Copy files
COPY ./app/ /src
# 3. Install dependencies
RUN pip install --upgrade pip
RUN pip install -r /src/requirements.txt
