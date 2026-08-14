---
title: Cloudflare trailing-slash stripping breaks collection routes
date: 2026-08-14
category: runtime-errors
module: API routing, reverse proxy configuration, and edge normalization
problem_type: runtime_error
component: api
symptoms:
  - The dashboard showed "Unable to load vehicles" while login and settings pages worked normally
  - Every request to /api/vehicles returned 307 Temporary Redirect and the redirect was never satisfied
  - The backend was healthy, the database was current, and no request reached the list handler
  - Nothing had been deployed or changed for eight days before the failure appeared
root_cause: external_change
resolution_type: code_fix
severity: critical
tags: [cloudflare, url-normalization, trailing-slash, fastapi, starlette, uvicorn, proxy-headers, redirect-loop, diagnosis-technique]
---

# Cloudflare trailing-slash stripping breaks collection routes

## Problem

Tracktion became unable to list vehicles. Authentication, settings, and every
single-resource route continued to work. No code had been deployed for eight
days, and no configuration had been changed on the Cloudflare side.

Cloudflare began removing trailing slashes from incoming URLs before forwarding
them to the origin. Every FastAPI collection route is registered at `"/"` under
a prefix, so `/api/vehicles/` is the canonical path and `/api/vehicles` is not a
route. Starlette answered the stripped path with a 307 redirect to the slashed
path, the edge stripped that slash too, and the browser looped until it gave up.
Because the failure happened at the network layer, the client saw no status code
at all.

| User-visible failure | Root cause | Repair |
|---|---|---|
| "Unable to load vehicles" on a healthy backend | Edge stripped the trailing slash; the slash redirect could never be satisfied | Serve the stripped path directly instead of redirecting |
| Redirect pointed at `http://` on an HTTPS page | uvicorn ignored `X-Forwarded-Proto` because the sender was not a trusted proxy IP | Trust forwarded headers and pass the scheme through nginx |

## Symptoms and diagnosis

- The dashboard rendered the failure card added in `05a6d91`. Before that commit
  the same failure would have rendered as "No vehicles yet", so this outage
  would have looked like an empty garage rather than an error.
- `docker ps` showed both containers healthy. Backend logs showed `200 OK` for
  `/api/auth/me`, `/api/auth/refresh`, and every `/api/settings/*` route, and
  `307 Temporary Redirect` for every `/api/vehicles` request.
- `GET /api/vehicles/` sent directly to the API container returned `403`, proving
  the route existed and that only the auth check rejected it.
- `GET /api/vehicles` sent directly to the API container returned
  `location: http://localhost:8000/api/vehicles/` — an absolute URL whose scheme
  came from what uvicorn believed about the connection.
- The decisive measurement used **unique query-string markers** so each request
  could be traced to the exact hop it arrived through:

  ```bash
  curl -s -o /dev/null -w 'edge:%{http_code}\n'  "https://<domain>/api/vehicles/?probe=edge1"
  curl -s -o /dev/null -w 'local:%{http_code}\n' "http://localhost:3000/api/vehicles/?probe=local1"
  docker logs --tail 100 vehicle-tracker-api | grep -E 'probe=(edge1|local1)'
  ```

  `local1` reached the origin as `/api/vehicles/?probe=local1` and returned 403.
  `edge1` reached the origin as `/api/vehicles?probe=edge1` — slash removed — and
  returned 307. Same nginx, same backend, same second. Only the path through
  Cloudflare lost the slash.
- A follow-up probe against a route that does not exist, `/api/zzz/?probe=slash3`,
  arrived as `/api/zzz`. The stripping is universal, not specific to one path.

## What did not work

- **Assuming the origin was down.** The reported symptom, "could not reach the
  server", matched the previous outage in
  [partial-fill rollout production recovery](partial-fill-rollout-production-recovery.md),
  where the backend had genuinely exited at startup. Here the backend was healthy
  the entire time. Identical user-visible text, unrelated cause.
- **Assuming lost secrets or a file-permission problem.** A lost JWT secret
  produces 401s that the axios interceptor converts into a logout and a login
  screen, not a transport failure. The container runs as root, so a 0600 secret
  file cannot fail to be written. Both were ruled out by reading the code paths
  rather than by testing.
- **Blaming Cloudflare URL Normalization.** The settings page disproved it:
  "Normalize URLs to origin" was **off**, so the normalized form was never sent
  upstream, and the "Cloudflare" normalization type only merges successive
  forward slashes and converts backslashes. Neither touches a trailing slash.
  The stripping comes from edge behavior that is not exposed as a zone setting.
- **Reading `docker logs --tail 2` immediately after a curl.** A browser tab was
  retrying the failed request in a loop, so the most recent log lines were
  browser traffic, not the probe. This produced a confident but unsupported
  conclusion. Marker query strings fixed the ambiguity.
- **Searching git history with an over-literal pickaxe.** `git log -S'@router.get("/")'`
  returned nothing because the real decorators carry `response_model=` arguments.
  The routers also live in `backend/app/routes/`, not `backend/app/routers/`.
  Both mistakes briefly suggested the routing had never been what it is.
- **Fixing only the proxy headers.** Correcting the redirect scheme was necessary
  but insufficient. It converted a first-hop mixed-content block into a visible
  redirect loop, which was progress in diagnosis but not a repair.

## Resolution

### Trust forwarded headers at the origin

As of this writing, branch commit `2942153` added `--proxy-headers
--forwarded-allow-ips=*` to the uvicorn command in
[`backend/Dockerfile`](../../../backend/Dockerfile). uvicorn honors
`--proxy-headers` by default, but `forwarded_allow_ips` defaults to `127.0.0.1`
and requests arrive from the frontend nginx container, so Cloudflare's
`X-Forwarded-Proto: https` was discarded and redirects were built as `http://`.
The same commit added `proxy_set_header X-Forwarded-Proto $forwarded_proto;` to
[`frontend/nginx.conf`](../../../frontend/nginx.conf), where a `map` prefers the
scheme reported upstream and falls back to the connection scheme so direct LAN
access still works.

The API port is published on the host, so `*` means any host on the LAN can
present forged `X-Forwarded-*` headers. This was an accepted trade-off for a
personal deployment. uvicorn 0.24 does not support CIDR ranges in
`forwarded_allow_ips`, so scoping to the Docker subnet was not available.

### Stop depending on the slash redirect

As of this writing, branch commit `adcf64e` added `StrippedSlashMiddleware` to
[`backend/app/main.py`](../../../backend/app/main.py). It reads the live route
table and, for an incoming path with no trailing slash, rewrites `scope["path"]`
before routing when — and only when — the slashed variant is a registered route.
Starlette never emits the 307, so there is no redirect for an intermediary to
mangle, and unknown paths still fall through to a normal 404.

Regression coverage in
[`backend/tests/test_stripped_slash.py`](../../../backend/tests/test_stripped_slash.py)
checks that the stripped path returns real data, that the slashed path still
works for direct access, that an unknown path still 404s rather than being
rewritten, and that nested resource paths such as `/api/vehicles/999` are
untouched.

## Verification recorded during recovery

- The full backend suite passed with 52 tests, including the four new cases.
- Backend images were published for `linux/amd64` and `linux/arm64`. The final
  `adcf64e`/`latest` manifest digest was
  `sha256:3b77e04d270f22b81a972ecf6e7c5b25a8adb41aef4cede547f7a8c6c670fba2`.
- After deployment, `GET /api/vehicles/?probe=fixed2` through Cloudflare returned
  `403` instead of `307`. The origin log still shows the path arriving without
  its slash, confirming the edge behavior is unchanged and that the application
  now serves that form directly.
- Vehicle data loaded in the application. No database, storage, or secret
  material was modified during this incident.

## Prevention

- Do not let a framework's automatic slash redirect sit on the critical path of
  an application served through a CDN or reverse proxy. An intermediary that
  rewrites paths turns the redirect into an unsatisfiable loop. Register
  collection routes so both forms resolve without a redirect.
- When an application is behind a proxy, configure the origin to trust forwarded
  headers from that proxy. An absolute redirect built from an untrusted scheme
  is wrong in a way that only manifests over HTTPS.
- Diagnose multi-hop request paths with a unique marker per request, such as a
  query string, and grep the origin log for it. Never infer causation from the
  tail of a log while a browser is retrying in the background.
- Distrust "nothing changed" as a reason to look only at your own code, and
  distrust your own diff as the only thing that can change. Third-party edge
  behavior changes without a deploy and without a setting to point at.
- A passing test suite cannot detect an edge-behavior change. Smoke-test the
  deployed application through its real public hostname after deployment, not
  just against the container.
- When two incidents share a user-visible message, confirm the mechanism before
  reusing the previous diagnosis. This outage and the Aug 6 rollout failure both
  rendered as an inability to load vehicles and had nothing else in common.
- Frontend error states that distinguish a failed request from an empty
  collection are what made this visible at all. Preserve that distinction.

## Related documentation

- [Partial-fill rollout production recovery](partial-fill-rollout-production-recovery.md)
  covers the earlier outage with the same user-visible symptom, caused by a
  backend that exited at startup.
