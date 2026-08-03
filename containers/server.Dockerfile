FROM node:22-bookworm-slim

ARG CODEX_VERSION=0.145.0

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates python3 \
    && npm install --global "@openai/codex@${CODEX_VERSION}" \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --chown=node:node server.py newton_mcp.py agent_prompt.txt response_schema.json ./
# newton_mcp.py imports emulator.client for instance port lookup; see
# docs/agent-tools.md for what that can and cannot do from inside this image.
COPY --chown=node:node emulator/__init__.py emulator/client.py ./emulator/

RUN mkdir -p /state /home/node/.codex \
    && chown -R node:node /state /home/node/.codex

USER node

ENV NEWTON_PORT=6801 \
    NEWTON_STATE_DIR=/state \
    PYTHONUNBUFFERED=1

EXPOSE 6801

CMD ["python3", "/app/server.py"]
