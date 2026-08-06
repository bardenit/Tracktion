# Storage cutover and compensation

Storage changes create an inactive candidate profile and a durable per-document ledger. Each object is copied and verified by byte length and SHA-256 before a locked cutover changes document references. A stale migration or credential-version mismatch cannot cut over.

On failure, the source profile remains active and source objects remain authoritative. Resume the same migration after correcting connectivity or credentials. Cancel only before completion. Old source objects are retained for the rollback window; cleanup records are durable and retryable, and deletion rechecks that no live document still references the object.

Monitor failed migration objects, pending/failed cleanup rows, active-profile count, and documents whose profile is missing. Never delete the source store until every reference resolves through the active profile and sampled downloads match their stored digest.

