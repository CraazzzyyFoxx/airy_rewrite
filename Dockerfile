FROM python:3.11

RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH "$PATH:/root/.local/bin"

COPY pyproject.toml poetry.lock ./

RUN poetry config virtualenvs.create false
RUN poetry install -n --only main

COPY . ./
CMD ["python3.11", "-O", "starter.py", "run"]