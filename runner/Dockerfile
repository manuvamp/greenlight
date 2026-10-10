# Toolchain image every upgrade runs in: git, uv, and several Python versions,
# because repos stuck on old majors (pandas 1.x, numpy 1.x) often need Python <= 3.11.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git build-essential ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv==0.11.19
ENV UV_PYTHON_INSTALL_DIR=/opt/uv-python UV_LINK_MODE=copy UV_CACHE_DIR=/root/.cache/uv
RUN uv python install 3.9 3.10 3.11 3.12
RUN git config --global user.email "greenlight@agent.local" && git config --global user.name "Greenlight" \
    && git config --global advice.detachedHead false
WORKDIR /repo
CMD ["sleep", "infinity"]
