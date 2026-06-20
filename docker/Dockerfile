FROM python:3.13-alpine

WORKDIR /opt/dtm
COPY pyproject.toml ./
COPY src ./src
COPY rules ./rules
COPY scenarios ./scenarios
COPY fixtures ./fixtures
RUN pip install --no-cache-dir .

ENV DTM_ROOT=/opt/dtm
ENTRYPOINT ["dtm"]

