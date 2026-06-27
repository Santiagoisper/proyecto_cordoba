---
name: Login/logout templates are standalone HTML
description: allauth login.html and logout.html must NOT extend base.html
---

`templates/account/login.html` and `templates/account/logout.html` are standalone HTML files — they do NOT `{% extends "base.html" %}`.

**Why:** `base.html` has `{% block content %}` inside a `{% if user.is_authenticated %}` branch. If login.html extends base.html, Django sees `{% block content %}` defined in the parent AND the child, triggering `TemplateSyntaxError: 'block' tag with name 'content' appears more than once` (or the if/else structure causes issues).

**How to apply:** Any allauth template override (login, logout, signup, etc.) should be a standalone HTML file with its own `<html>` structure, Tailwind CDN, and Lucide CDN inline.
