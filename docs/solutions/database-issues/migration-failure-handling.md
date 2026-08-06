# Migration failure handling

Tracktion upgrades the database with Alembic before starting the API. A failed upgrade prevents readiness; do not bypass the revision check or start an older application against a newer schema.

Before deployment, back up the database and persistent `data/` directory, stop older application instances, and run one migration-capable instance. Verify `/health` reports ready and `alembic_version.version_num` equals the `HEAD_REVISION` in `app/migrations.py` before scaling the API.

If migration fails, keep the application stopped, preserve the database and logs, and restore the pre-deploy backup with the prior compatible image. Re-running is safe only after the failed revision is confirmed restartable. Forward-only revisions require restore-based rollback.

