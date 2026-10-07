# Сервіс рішень (redact → classify → read-side → policy → act(mock)).
# Без кредів на запис: act-side лише пише журнал з dry_run=true.
FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir "pyyaml>=6.0" "anthropic>=0.40"
COPY src ./src
COPY config ./config
COPY mocks ./mocks
COPY data ./data
COPY prompts ./prompts
COPY demo/sample.yaml ./demo/sample.yaml
COPY tests/golden_routes.json ./tests/golden_routes.json
COPY tools/stand.py tools/stand.html ./tools/

ENV STAND_HOST=0.0.0.0 STAND_PORT=8765 PYTHONUNBUFFERED=1 KB_RUNTIME_PATH=/app/runtime/kb.json LLM_CACHE_DIR=/app/runtime/cache
# код і конфіг — лише читання для сервісу (права з хоста можуть бути 600); писати можна тільки в /app/runtime
RUN chmod -R a+rX,go-w /app && useradd --uid 10001 --no-create-home triage && mkdir -p /app/runtime && chown triage /app/runtime
USER triage
EXPOSE 8765
CMD ["python", "tools/stand.py"]
