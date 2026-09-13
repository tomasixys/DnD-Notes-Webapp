# syntax=docker/dockerfile:1.7

FROM node:24.12.0-bookworm-slim AS frontend-build

WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY CHANGELOG.md /build/CHANGELOG.md
COPY frontend/ ./
RUN npm run type-check && npm run build


FROM python:3.11.9-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN groupadd --system --gid 10001 dndnotes \
    && useradd --system --uid 10001 --gid dndnotes --home /app dndnotes

WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY --chown=dndnotes:dndnotes backend/ ./backend/
COPY --from=frontend-build --chown=dndnotes:dndnotes \
    /build/frontend/dist/ ./backend/app/frontend_dist/
COPY --chown=dndnotes:dndnotes deploy/hosted/embedded-profile.txt \
    ./backend/app/_embedded_profile.txt
COPY --chown=dndnotes:dndnotes deploy/hosted/hosted.toml \
    /etc/dnd-notes/hosted.toml
RUN cd backend \
    && python validate_build.py \
        --profile hosted \
        --config /etc/dnd-notes/hosted.toml

USER 10001:10001
WORKDIR /app/backend

EXPOSE 8000

CMD ["python", "run.py", "--config", "/etc/dnd-notes/hosted.toml", "--no-browser"]
