---
title: Dashboard cold loads blocked on NHTSA recall lookups
date: 2026-09-02
category: runtime-errors
module: Dashboard data loading, recall service, and SQLAlchemy engine configuration
problem_type: performance
component: api, frontend
symptoms:
  - The dashboard took roughly a minute to show data, then behaved normally for the rest of the day
  - Only the first visit after a day away was slow; reloads minutes later were fast
  - The app shell, navigation, and static assets rendered immediately; only the vehicle cards spun
  - Nothing had been deployed and no error appeared in the browser or the API logs
root_cause: design_flaw
resolution_type: code_fix
severity: high
tags: [performance, nhtsa, external-api, cache, stale-while-revalidate, background-tasks, fastapi, connection-pool, sqlalchemy, promise-all, cold-load]
---

# Dashboard cold loads blocked on NHTSA recall lookups

## Problem

The dashboard took about 60 seconds to populate on the first visit of the day.
Once loaded, everything was fast, and it stayed fast for the rest of the day.
No deploy preceded it and nothing errored — the request simply sat there.

Each vehicle card waited on a `Promise.all` of five API calls, one of which was
`/api/vehicles/{id}/recall-status`. That endpoint kept a 24-hour cache, and on a
stale cache it called the NHTSA recalls API **inline, inside the request**. So
the first load of each day fanned out one live external call per vehicle, and
every card stayed in its loading state until its slowest call returned.

| User-visible failure | Root cause | Repair |
|---|---|---|
| Cards spin ~60s on the first load of the day | Stale 24h recall cache triggered a live NHTSA call awaited inside the request | Always serve cache; refresh via `BackgroundTasks` |
| One slow call froze the whole card | Recall status sat inside the card's blocking `Promise.all` | Fetch it separately and merge it in when it lands |
| Slowness scaled with vehicle count | Async handlers held pooled DB connections across the NHTSA await, against a default pool of 5 (+10 overflow) with a 30s checkout timeout | Release the session before the await; size the pool explicitly |

## Symptoms and diagnosis

The two facts that located this without any instrumentation:

- **The shell rendered instantly, the data did not.** That cleared the static
  frontend, nginx, and the edge, and pointed at API responses.
- **Slow only on the first visit after being away, fast all day after.** That is
  the signature of an expiring cache, not of cold containers (which `restart:
  unless-stopped` rules out) or of stale pooled connections (which
  `pool_pre_ping=True` already handled). A 24-hour TTL matches "first time I open
  it each day" exactly.

Reading the load path confirmed it:

- `frontend/src/pages/DashboardPage.tsx` — `loadVehicleData` awaited a
  `Promise.all` of reminders, expenses, fuel stats, costs, **and recall status**.
  The card's `loading` flag cleared only when all five resolved.
- `backend/app/routes/vehicles.py` — `vehicle_recall_status` treated a cache
  older than 24h as stale and `await get_recalls(...)` inline.
- `backend/app/services/recalls.py` — `timeout=8.0` on the httpx call. httpx
  applies that per read operation rather than as a wall-clock budget, so a slow
  NHTSA response can exceed 8s.
- `backend/app/database.py` — the engine used SQLAlchemy defaults (`pool_size=5`,
  `max_overflow=10`, `pool_timeout=30`). The dashboard issues `2 + 5N` requests
  at once, and each `async def` recall handler held its `get_db` session for the
  whole external call, so the remaining sync handlers queued for connections.
  This is what turned a per-vehicle 8s call into a compounded ~60s wait.

The diagnosis came from the symptom pattern plus the code path, not from a
timing measurement. The measurement that would have confirmed it directly:

```bash
curl -o /dev/null -s -w 'total=%{time_total}\n' \
  -H "Authorization: Bearer $TOKEN" \
  https://<domain>/api/vehicles/<id>/recall-status
```

run on a cold cache, which can be forced with
`UPDATE vehicles SET recalls_cache = NULL WHERE id = <id>;`.

## Fix

Commit `6811c96`, "perf(dashboard): stop blocking page load on NHTSA recall lookups".

1. **Stale-while-revalidate on the endpoint.** `vehicle_recall_status` now always
   answers from cache and, when stale, schedules
   `refresh_recall_cache(vehicle_id)` via FastAPI `BackgroundTasks`. The response
   is two DB queries.
2. **A background refresher with its own session.** `refresh_recall_cache` in
   `backend/app/services/recalls.py` opens its own `SessionLocal`, reads
   make/model/year, closes the session **before** the NHTSA await, fetches, then
   reopens to write the cache. A module-level `_refreshing` set keeps a burst of
   dashboard loads from stacking duplicate calls for one vehicle.
3. **Recall status off the frontend critical path.** The card renders on the four
   local-data calls; recall status is fetched alongside and merged into card
   state when it arrives.
4. **No pooled connection held across a network call.** `vehicle_recalls` (the
   full recall list route) captures make/model/year, calls `db.close()`, awaits
   NHTSA, then re-fetches the vehicle.
5. **Explicit pool sizing.** `pool_size=10`, `max_overflow=20`, `pool_timeout=10`,
   `pool_recycle=1800` for non-SQLite engines — twice the headroom, and a fast
   failure instead of a 30s stall when it runs out.

`backend/tests/test_recall_status.py` guards the behaviour with three tests. The
important one primes a stale cache with campaign `STALE-1` while the stubbed
NHTSA call returns `FRESH-1`, then asserts the **response** carries `STALE-1` and
the **database** ends up with `FRESH-1`. That fails if anyone reintroduces an
inline await, because the response would then carry the fresh value.

## Tradeoff accepted

A newly published recall now surfaces one page load later than before: the first
load renders the previous cache while the refresh happens behind it. A vehicle
with no cache at all shows no recall data until the background refresh completes.
This was accepted deliberately — recall data changes on a scale of weeks, and no
version of it justifies blocking the dashboard on a third-party API.

## Lessons

- **Never await a third-party API inside a request that renders a page.** Serve
  the last known value and refresh out of band. A cache that fetches inline on
  expiry does not remove the latency, it just makes it rare and therefore
  confusing.
- **A timeout is a ceiling per call, not a budget per page.** `timeout=8.0` looks
  survivable until it is multiplied by N vehicles and queued behind a connection
  pool.
- **Never hold a pooled DB connection across a network call.** An `async def`
  handler with a `get_db` dependency does exactly that by default, and it turns
  one slow external API into pool starvation for every unrelated request.
- **"Slow only the first time after a while" means a cache TTL.** Match the idle
  window to the TTL — here, a day away against a 24-hour cache — and the culprit
  usually falls out before any profiling.
- **One blocking element in a `Promise.all` sets the render time of the whole
  group.** Data that is decorative, or safely stale, belongs outside it.
