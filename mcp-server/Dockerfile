FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir "mcp>=1.2.0,<2"
COPY server.py .
# Kept alive so the harness can speak MCP over stdio via `docker compose exec -T`.
CMD ["sleep", "infinity"]
