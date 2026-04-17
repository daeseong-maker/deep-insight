FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app

# All environment variables in one layer
ENV UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_PROGRESS=1 \
    PYTHONUNBUFFERED=1 \
    DOCKER_CONTAINER=1 \
    AWS_REGION=us-west-2 \
    AWS_DEFAULT_REGION=us-west-2



COPY requirements.txt requirements.txt
# Install from requirements file
RUN uv pip install -r requirements.txt




RUN uv pip install aws-opentelemetry-distro==0.12.2


# Signal that this is running in Docker for host binding logic
ENV DOCKER_CONTAINER=1

# Create non-root user
RUN useradd -m -u 1000 bedrock_agentcore

# Create skill directories with proper ownership
RUN mkdir -p /app/skills /app/src/utils/skills /app/src/tools && \
    chown -R bedrock_agentcore:bedrock_agentcore /app

# Copy skill system components (before user switch to ensure they're included)
COPY --chown=bedrock_agentcore:bedrock_agentcore src/utils/skills/ /app/src/utils/skills/
COPY --chown=bedrock_agentcore:bedrock_agentcore src/tools/skill_tool.py /app/src/tools/skill_tool.py
COPY --chown=bedrock_agentcore:bedrock_agentcore skills/ /app/skills/

USER bedrock_agentcore

EXPOSE 9000
EXPOSE 8000
EXPOSE 8080

# Copy entire project (respecting .dockerignore)
COPY --chown=bedrock_agentcore:bedrock_agentcore . .

# Use the full module path

CMD ["opentelemetry-instrument", "python", "-m", "agentcore_runtime"]
