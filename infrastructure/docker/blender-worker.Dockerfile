# Blender render worker (ADR 0003). Runs as an unprivileged user with no network access required.
# Status: Sprint 0 spike - build & validate in CI before enabling CV_RENDER_RENDERER=blender.
FROM python:3.12-slim
ARG BLENDER_VERSION=4.2.3
ARG BLENDER_SERIES=4.2
RUN apt-get update && apt-get install -y --no-install-recommends curl xz-utils libxi6 libxrender1 libxkbcommon0 \
      libgl1 libsm6 && rm -rf /var/lib/apt/lists/* \
 && curl -fsSL https://download.blender.org/release/Blender${BLENDER_SERIES}/blender-${BLENDER_VERSION}-linux-x64.tar.xz \
      | tar -xJ -C /opt && ln -s /opt/blender-${BLENDER_VERSION}-linux-x64/blender /usr/local/bin/blender
ENV CV_SHARED_DIR=/srv/shared CV_RENDER_RENDERER=blender
RUN useradd --create-home --uid 10001 app
WORKDIR /srv/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY shared /srv/shared
COPY backend /srv/backend
COPY infrastructure/docker/blender /srv/infrastructure/docker/blender
USER app
CMD ["rq", "worker", "renders", "--with-scheduler", "--url", "redis://redis:6379/0"]
