---
name: Django project location
description: Where the Django project lives and why it's not an artifact
---

The Django project (Proyecto Córdoba) lives at `cordoba/` in the workspace root — NOT inside `artifacts/`.

**Why:** The `artifacts/` directory is for pnpm/Node.js apps registered through the artifacts skill. Django is not a supported artifact kind, so registering it would require a custom workaround. It's cleaner to run it from the workspace root with a workflow pointing to `cd cordoba && python manage.py runserver`.

**How to apply:** Always `cd cordoba` before running any manage.py commands. The DJANGO_SETTINGS_MODULE is set to `config.settings.development` in the shared env vars.
