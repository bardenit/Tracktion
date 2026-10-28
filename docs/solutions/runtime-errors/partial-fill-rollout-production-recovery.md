---
title: Partial-fill rollout production recovery
date: 2026-08-06
category: runtime-errors
module: Production startup, database migrations, and vehicle photo storage
problem_type: runtime_error
component: database
symptoms:
  - Backend startup exited and Cloudflare reported an invalid or incomplete origin response during login
  - Existing sessions could not load vehicles, while the dashboard initially presented the failure as an empty vehicle list
  - Startup then rejected known retired Smartcar columns in the production database
  - Vehicles loaded after recovery, but existing S3-backed photos did not render
root_cause: config_error
resolution_type: migration
severity: critical
tags: [production-rollout, jwt, alembic, schema-reconciliation, s3, vehicle-photos, docker, multiarch]
---

# Partial-fill rollout production recovery

## Problem

The partial-fill rollout exposed three independent compatibility failures in sequence. The API first exited because production startup required a manually supplied JWT signing secret. After that was repaired, schema reconciliation rejected six known Smartcar columns left by an older release. After startup and login recovered, the storage lifecycle migration routed existing S3 document records to a new local profile and left legacy vehicles without primary-photo references.

The combined impact was failed login, unavailable vehicle data for existing sessions, and missing vehicle photos. Checks recorded during recovery found that the vehicle rows, document metadata, and original S3 objects remained intact.

| User-visible failure | Root cause | Repair |
|---|---|---|
| Cloudflare origin error and failed login | Backend exited when `JWT_SECRET_KEY` was absent or unsuitable | Generate the secret once in persistent storage and reuse it |
| Backend still failed after the auth repair | Strict reconciliation treated retired Smartcar columns as unknown drift | Allowlist only the six known retired columns |
| Vehicles returned but photos were missing | Migration `0005` installed an active local storage profile and did not backfill primary photos | Migration `0009` restored configured S3 routing and primary-photo references |

## Symptoms and diagnosis

- The original rollout image exited during startup with `JWT_SECRET_KEY must be a non-default secret of at least 32 characters in production`, so the reverse proxy had no healthy origin for login or vehicle requests.
- The dashboard treated a rejected `listVehicles()` request like a legitimate empty collection and displayed “No vehicles yet.” This made an outage look like data loss.
- Once authentication startup was repaired, the backend reported six unknown `vehicles` columns: `smartcar_vehicle_id`, `smartcar_user_id`, `smartcar_access_token`, `smartcar_refresh_token`, `smartcar_token_expires_at`, and `smartcar_last_synced_at`. Smartcar had previously been removed, but these harmless historical columns remained in the unversioned production database.
- Recovery-session checks found that production document rows still named the expected S3 object keys and direct reads using the existing S3 configuration returned both objects. The active database storage profile, however, was local and had an empty configuration. Vehicle `primary_photo_id` values were also null.

## What did not work

- Supplying a new JWT secret manually would restore startup, but operators do not otherwise need this internal signing material. Generating a different secret on every restart would invalidate all existing sessions, so generation had to be persistent.
- Disabling schema validation would accept the Smartcar residue but also hide genuinely unknown drift. The safe fix was a narrow, table-specific historical allowlist.
- The first photo hypothesis was that container replacement had discarded locally stored files. The configured storage type, document keys, and successful direct object reads disproved that: this was a metadata-routing failure, not object loss.
- Copying or re-uploading the photos would have duplicated valid objects without correcting the migration defect.
- Passing builds and focused feature tests were insufficient rollout gates because they did not start the exact image against a production-shaped legacy database and persisted configuration.

## Resolution

### Persist generated signing material

As of this writing, branch commit `05a6d91` changed [`backend/app/config.py`](../../../backend/app/config.py) so an explicit non-placeholder `JWT_SECRET_KEY` still takes precedence. Otherwise, Tracktion generates a strong secret once at `DATA_DIR/.jwt_secret`, creates the file with private permissions, and reuses it on later starts. Production validation still rejects an empty key and warns if an explicitly supplied key is shorter than recommended.

The same commit changed [`frontend/src/pages/DashboardPage.tsx`](../../../frontend/src/pages/DashboardPage.tsx) to keep request failure separate from an empty vehicle list. Users now see “Unable to load vehicles” and a retry action when the API cannot be reached. Regression coverage in [`backend/tests/test_auth.py`](../../../backend/tests/test_auth.py) checks persistence, permissions, explicit configuration precedence, and replacement of the legacy placeholder.

The deployment must keep `DATA_DIR` on persistent storage. No operator needs to view or copy the generated secret during normal operation.

### Reconcile understood legacy schema safely

As of this writing, branch commit `8a6204a` added the six retired Smartcar fields to the table-specific `KNOWN_RETIRED_COLUMNS` set in [`backend/app/schema_bootstrap.py`](../../../backend/app/schema_bootstrap.py). Reconciliation subtracts only that set when calculating unknown columns, so unrelated drift continues to fail closed. The regression in [`backend/tests/test_schema_bootstrap.py`](../../../backend/tests/test_schema_bootstrap.py) proves the historical columns are accepted and preserved through upgrade.

### Restore configured S3 routing and photo pointers

As of this writing, branch commit `baede39` added forward-only migration [`backend/alembic/versions/0009_restore_configured_storage.py`](../../../backend/alembic/versions/0009_restore_configured_storage.py). When configuration selects a non-local backend but the active database profile is local, it creates and activates a profile from the configured backend, repoints affected documents, and deactivates the other profiles. It also fills each missing vehicle `primary_photo_id` from the associated `vehicle_photo` document with the lowest ID.

The migration changes database references only; it does not move, copy, delete, or rewrite object bytes. [`backend/tests/test_migrations.py`](../../../backend/tests/test_migrations.py) starts from the broken `0008` state and verifies the active S3-compatible profile, preserved configuration, corrected document association, and restored primary photo. [`backend/app/migrations.py`](../../../backend/app/migrations.py) identifies `0009_restore_configured_storage` as the required head.

## Verification recorded during recovery

- The session recorded that the full backend suite passed with 48 tests after the final migration; frontend tests, type checking, and production build passed after the dashboard change.
- Backend images were published for both `linux/amd64` and `linux/arm64`. The final `baede39`/`latest` manifest digest was `sha256:2d5d370c8df2aacf3365417bc46aec873f854736f7bbc10bb35a49633ce9959c`.
- The corrected backend was deployed to the Proxmox installation. The database reached revision `0009_restore_configured_storage`, exactly one S3 profile was active, both photo documents referenced it, and both legacy vehicle primary-photo values were restored.
- Login succeeded, vehicle data populated, and both original photos rendered through the application at their expected natural width. No image object was moved or recreated.

## Prevention

- Exercise migrations against production-shaped pre-upgrade fixtures containing retired columns, existing records, configured external storage, and nullable associations.
- When a database abstraction supersedes file or environment configuration, migrate the existing configuration rather than silently installing a default.
- Pair new association columns with deterministic data backfills and row-level assertions.
- Keep signing material on the persistent data mount and include a same-volume restart in container smoke tests.
- Preserve strict schema reconciliation, but document and test narrowly defined historical exceptions.
- Distinguish API errors from valid empty collections in frontend state and tests.
- Before promotion, start the exact image against representative legacy data, exercise login and core reads, retrieve existing objects through the application, and inspect the manifest for both target architectures.
- Roll out immutable commit tags in stages and retain the prior known-good image. A container rollback does not reverse a forward-only database migration.

## Related documentation

- [Migration failure handling](../database-issues/migration-failure-handling.md) covers backups, migration ownership, startup health, and rollback discipline.
- [Storage cutover compensation](../integration-issues/storage-cutover-compensation.md) covers safe copy, verification, atomic cutover, and cleanup for deliberate storage-backend changes. Its guarantees should also be applied when bootstrapping storage profiles from legacy configuration.
