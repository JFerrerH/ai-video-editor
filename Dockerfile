# The engine on Linux (CPU only): every local tool, run through tools/run_job.py.
#
#   docker build -t video-engine .                                  # weights baked in (offline start)
#   docker build -t video-engine --build-arg WITH_MODELS=0 .        # smaller; weights download on first use
#   docker run --rm video-engine --self-check
#   docker run --rm -i -v "$PWD/footage:/engine/footage" video-engine - < job.json
#
# Multi-arch by construction (linux/amd64, linux/arm64). See CLAUDE.md, "Linux / Docker".

ARG PYTHON_IMAGE=python:3.12-slim-trixie
ARG NODE_IMAGE=node:22-trixie-slim
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.13.0

FROM ${UV_IMAGE} AS uv
FROM ${NODE_IMAGE} AS node

FROM ${PYTHON_IMAGE}

ARG VIDEO_USE_REF=43cfc566833548093455c9d4a46bd69913b7e552
ARG AUTO_EDITOR_VERSION=31.7.2
ARG WITH_MODELS=1

# ffmpeg 7.1 (Debian trixie: libass, freetype, libx264), the Chrome Headless Shell libraries Remotion
# documents for Debian, the GL/EGL/GLib runtime mediapipe's native library and OpenCV link against,
# fonts, git for video-use.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg ca-certificates curl git \
        libnss3 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 libgbm1 libasound2t64 libxrandr2 \
        libxkbcommon0 libxfixes3 libxcomposite1 libxdamage1 libpango-1.0-0 libcairo2 libcups2t64 \
        libgl1 libegl1 libgles2 libglib2.0-0 \
        fontconfig fonts-dejavu-core fonts-liberation fonts-noto-core fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /uvx /usr/local/bin/
COPY --from=node /usr/local/bin/node /usr/local/bin/
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

RUN case "$(uname -m)" in x86_64) a=x86_64 ;; aarch64) a=aarch64 ;; *) echo "unsupported arch" >&2; exit 1 ;; esac \
    && curl -fsSL -o /usr/local/bin/auto-editor \
       "https://github.com/WyattBlue/auto-editor/releases/download/${AUTO_EDITOR_VERSION}/auto-editor-linux-$a" \
    && chmod +x /usr/local/bin/auto-editor

RUN useradd --create-home --uid 1000 engine \
    && mkdir -p /engine /opt/models && chown engine:engine /engine /opt/models
USER engine
WORKDIR /engine

ENV UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_CACHE=1 \
    HF_HOME=/opt/models/hf \
    ENGINE_MODELS_DIR=/opt/models \
    HF_HUB_DISABLE_TELEMETRY=1 \
    PYTHONUNBUFFERED=1

# Python deps first (cached unless the lock changes): the voice, transcription and matte groups.
COPY --chown=engine:engine pyproject.toml uv.lock ./
RUN uv sync --frozen --group gen --group asr --group matte

# Remotion deps + its headless browser (cached unless the lockfile changes).
COPY --chown=engine:engine tools/motion/package.json tools/motion/package-lock.json tools/motion/
RUN cd tools/motion && npm ci --no-audit --no-fund && npx remotion browser ensure

RUN git clone --quiet https://github.com/browser-use/video-use vendor/video-use \
    && git -C vendor/video-use checkout --quiet "${VIDEO_USE_REF}" \
    && rm -rf vendor/video-use/.git

COPY --chown=engine:engine . .
RUN mkdir -p footage exports brands assets/music assets/sfx \
    && uv run --no-sync tools/sfx_synth.py >/dev/null \
    && uv run --no-sync tools/overlay_schema.py --export > tools/motion/overlay_schema.json

RUN if [ "${WITH_MODELS}" = "1" ]; then uv run --no-sync tools/run_job.py --prefetch; fi
ENV HF_HUB_OFFLINE=${WITH_MODELS}

VOLUME ["/engine/footage", "/engine/brands", "/engine/exports", "/engine/assets/music"]
ENTRYPOINT ["uv", "run", "--no-sync", "tools/run_job.py"]
CMD ["--self-check"]
