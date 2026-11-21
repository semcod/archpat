FROM python:3.12-slim@sha256:05a994d2344eb364cc186910f4fc8786a38215f39f00d0acc25bff33a08f4177
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN python -m pip install --no-cache-dir . && useradd --uid 10001 --create-home archpat
COPY examples ./examples
COPY tests ./tests
COPY scripts ./scripts
RUN mkdir /out && chown 10001:10001 /out
USER 10001
ENTRYPOINT ["archpat"]
CMD ["synthesize", "examples/story-local.json", "--out", "/out/demo"]

