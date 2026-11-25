# Time Travel Inc. Service Desk: the incident management tool, on port 8080.
FROM python:3.13-slim
WORKDIR /app
RUN pip install --no-cache-dir "fastapi>=0.115" "uvicorn>=0.30" "jinja2>=3.1"
COPY servicedesk ./servicedesk
EXPOSE 8080
# Generates the incident data on first start, then serves.
CMD ["sh", "-c", "python -m servicedesk.generate --if-missing && exec uvicorn servicedesk.app:app --host 0.0.0.0 --port 8080"]
