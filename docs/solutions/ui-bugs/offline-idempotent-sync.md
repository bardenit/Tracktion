# Offline idempotent fuel sync

Offline fill-ups are stored in a versioned, user-specific localStorage queue. Each item receives one UUID operation ID when first submitted; the same ID is used for the online attempt and every later replay. The server binds that ID to the user, vehicle, canonical payload hash, and resulting fuel entry.

Logout, login, and account changes advance an authentication generation. Pending refreshes cannot restore stale tokens, and a sync stops before sending or rewriting queue state when its user generation changes. Validation conflicts remain visible for review; network and server failures remain pending.

The service worker never caches API responses and purges legacy Tracktion caches during activation and account transitions. Static application assets remain cacheable for offline launch.

