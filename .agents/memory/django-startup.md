---
name: Django startup and PORT
description: How the Django workflow is configured and the PORT variable requirement
---

The Replit workflow command is: `cd cordoba && python manage.py runserver 0.0.0.0:${PORT:-8000}`

**Why:** Replit's workflow system doesn't always inject PORT automatically. Without the `:-8000` fallback, `$PORT` evaluates to empty string and Django throws `"0.0.0.0:" is not a valid port number`. The PORT=8000 env var is also set in shared environment.

**How to apply:** Always use `${PORT:-8000}` in the runserver command. The workflow `waitForPort` is set to 8000 to match.
