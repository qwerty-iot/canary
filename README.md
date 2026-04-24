# Canary Monitoring Service

Canary is a lightweight monitoring companion that evaluates a configurable set of checks, publishes their status over HTTP, and sends alerts via Pushover when something goes wrong.

## Features
- YAML-based configuration for checks, server settings, and Pushover credentials
- Pluggable checker architecture with an initial HTTP checker implementation
- Azure App Registration secret expiry monitoring with warning/error thresholds
- Cron-style schedules for check execution
- Pushover notifications on service startup, failure, and recovery events
- Minimal status dashboard plus JSON API endpoint for integrations
- Ready-to-run Docker image

## Getting Started
1. Install dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Prepare a configuration file:
   ```bash
   cp config.example.yaml config.yaml
   # Edit config.yaml with real Pushover credentials and checks
   ```
3. Run the service:
   ```bash
   python -m app.main --config config.yaml
   ```
   You can also set the `CANARY_CONFIG` environment variable instead of passing `--config`.

The HTTP interface exposes:
- `GET /` – human-friendly dashboard (title defaults to `Canary Status`, override with `server.title`)
- `GET /status` – JSON payload with all check states and configured title

## Docker Usage
Build and run the container:
```bash
docker build -t canary .
docker run -p 8000:8000 \
  -e CANARY_CONFIG=/config/config.yaml \
  -v $(pwd)/config.yaml:/config/config.yaml:ro \
  canary
```

Mount your production configuration at `/config/config.yaml` or adjust the environment variable to match your setup.

## Alert levels
- Checks can return `ok`, `warning`, or `error` severities
- Warnings trigger ⚠️ notifications; errors trigger 🚨 notifications
- Returning to `ok` emits a ✅ recovery message

### HTTP checker options
- `include_body_on_error` (bool, default `false`) – append the response body to failure notifications
- `response_excerpt_length` (int, default `500`) – max characters to include when the body is attached
- JSON responses are prettified automatically in alerts and the dashboard when included

### Azure App Registration checker options
- `tenant_id` (required) – directory tenant ID to query
- `client_id` / `client_secret` – service principal credentials; omit both to fall back to `DefaultAzureCredential`
- `include_prefixes` – optional whitelist of app name prefixes
- `exclude_prefixes` – optional blacklist of prefixes
- `exclude_apps` – explicit list of app display names to ignore
- Secrets expiring within 48 hours raise an error; within 30 days raise a warning
- The principal used must be granted `Application.Read.All` (and `Directory.Read.All` if needed) for Microsoft Graph

### Server options
- `host`, `port` – standard listening configuration
- `title` – string shown in the dashboard masthead and FastAPI metadata

## Extending Canary
- Add new checker types in `app/checks/`
- Register them in `app/checks/__init__.py`
- Provide any additional configuration keys in the YAML file

### Built-in checkers
- `http` – Verify HTTP endpoints (status codes and optional response content)
- `azure_app_registrations` – Monitor Entra app registration secrets for expiry

## Development Notes
- `python3 -m compileall app` sanity-checks syntax without hitting external services
- Use the `requirements.txt` for dependency management
- The scheduler and notification logic live in `app/scheduler.py`
