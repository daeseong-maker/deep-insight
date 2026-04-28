---
title: Ops Dashboard
status: active
last_updated: 2026-03-01
---

# Ops Dashboard

Optional operational layer for the Web UI. Adds DynamoDB-backed job tracking, SNS email notifications, and a Cognito-authenticated admin dashboard. The Web UI works normally without it.

## Where the code lives

- `deep-insight-web/ops/` — admin router, auth, job tracker

## References

- [admin-authentication.md](./admin-authentication.md) — Cognito JWT, cookies, route protection
- [language-switching.md](./language-switching.md) — Korean/English i18n for admin pages
- [plan/](./plan/) — business requirements, research, technical approach, implementation plan
