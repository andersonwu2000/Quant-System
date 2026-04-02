# Security Review 2026-04-02

## Scope

Static security review of the current backend/API surface, focused on:

- Authentication and authorization
- Admin bootstrap and secret management
- WebSocket access control
- Sensitive information exposure
- Trading-critical safety endpoints

This review was performed from source inspection only. No live penetration test or dependency CVE scan was run in this pass.

## Verdict

**Severe vulnerabilities do exist.**

The most serious issues are:

1. Unauthenticated operational endpoints expose live portfolio, positions, cash, trade summaries, and pipeline metadata.
2. Prometheus `/metrics` is exposed without auth and includes sensitive trading gauges such as current NAV and intraday drawdown.
3. Production deployments can still auto-create a default `admin` account with the well-known password `Admin1234` if `QUANT_ADMIN_PASSWORD` is omitted.

These are not theoretical quality concerns. They are concrete confidentiality and control failures.

## Findings

### 1. Critical: Unauthenticated `/ops/*` endpoints leak sensitive trading and portfolio data

**Severity:** Critical

**Affected code:**

- [src/api/routes/ops.py](/D:/Finance/src/api/routes/ops.py#L22)
- [src/api/routes/ops.py](/D:/Finance/src/api/routes/ops.py#L106)
- [src/api/routes/ops.py](/D:/Finance/src/api/routes/ops.py#L137)
- [src/api/app.py](/D:/Finance/src/api/app.py#L185)

**What happens**

The `ops` router is mounted into `/api/v1`, but its endpoints do not require `verify_api_key` or any role dependency.

As implemented, an unauthenticated caller can retrieve:

- current NAV and cash
- full position list with quantities, prices, average cost, pnl, and weights
- recent pipeline run metadata
- trade summary and reconciliation summary
- strategy name and rebalance frequency

**Why this is severe**

This is direct leakage of highly sensitive trading information. In a real deployment this gives an external party visibility into:

- current portfolio composition
- position sizing
- performance drift
- operational state

That is enough to reverse-engineer behavior, infer strategy activity, or front-run manual operational processes.

**Recommended fix**

- Require authentication on the entire `ops` router.
- Require at least `risk_manager` or `admin` for detailed operational data.
- Consider splitting into:
  - safe public health endpoint
  - authenticated operational endpoint

---

### 2. Critical: Unauthenticated `/metrics` exposes sensitive trading telemetry

**Severity:** Critical

**Affected code:**

- [src/api/app.py](/D:/Finance/src/api/app.py#L164)
- [src/api/app.py](/D:/Finance/src/api/app.py#L165)
- [src/metrics.py](/D:/Finance/src/metrics.py#L28)
- [src/metrics.py](/D:/Finance/src/metrics.py#L33)
- [src/risk/realtime.py](/D:/Finance/src/risk/realtime.py#L104)

**What happens**

Prometheus metrics are exposed at `/metrics` without any authentication gate. The exported metrics include:

- `nav_current`
- `intraday_drawdown_pct`
- kill switch counters
- risk alert counters
- reconciliation mismatch counts

**Why this is severe**

This endpoint leaks live account health and risk posture to any network party that can reach the API. `nav_current` alone is sensitive account information. Combined with drawdown and kill-switch metrics, it gives outsiders near-real-time operational visibility into distress conditions.

**Recommended fix**

- Do not expose `/metrics` publicly.
- Restrict it to an internal network, reverse proxy allowlist, or authenticated metrics path.
- If public exposure is unavoidable, remove portfolio-sensitive gauges from the exported set.

---

### 3. Critical: Production can auto-create `admin` with default password `Admin1234`

**Severity:** Critical

**Affected code:**

- [src/core/config.py](/D:/Finance/src/core/config.py#L83)
- [src/core/config.py](/D:/Finance/src/core/config.py#L85)
- [src/core/config.py](/D:/Finance/src/core/config.py#L145)
- [src/api/app.py](/D:/Finance/src/api/app.py#L52)
- [src/api/app.py](/D:/Finance/src/api/app.py#L104)

**What happens**

On startup, `_seed_admin()` automatically creates an `admin` account if one does not already exist. The password is sourced from `config.admin_password`, whose default remains `Admin1234`.

Non-dev validation currently rejects default `api_key` and `jwt_secret`, but it does **not** reject the default admin password.

That means a production deployment can be started with:

- strong API key
- strong JWT secret
- but still auto-create `admin / Admin1234`

if `QUANT_ADMIN_PASSWORD` is simply forgotten.

**Why this is severe**

This is a classic deployment foot-gun that becomes an actual administrative takeover path. It only requires:

1. username discovery, which is trivial because the seeded username is fixed as `admin`
2. password omission during deployment

This is exactly the kind of mistake that happens in real rollouts.

**Recommended fix**

- In non-dev, reject `admin_password == "Admin1234"` at config validation time.
- Prefer failing startup over seeding any default admin in staging/prod.
- Optionally require explicit bootstrap credentials for first run.
- Add a mandatory `force_password_change` flag on first login if bootstrap seeding remains.

---

### 4. High: WebSocket channels ignore authorization scope after token validation

**Severity:** High

**Affected code:**

- [src/api/app.py](/D:/Finance/src/api/app.py#L188)
- [src/api/app.py](/D:/Finance/src/api/app.py#L200)
- [src/api/app.py](/D:/Finance/src/api/app.py#L209)
- [src/api/routes/auto_alpha.py](/D:/Finance/src/api/routes/auto_alpha.py#L579)
- [src/api/routes/auto_alpha.py](/D:/Finance/src/api/routes/auto_alpha.py#L595)
- [src/api/routes/auto_alpha.py](/D:/Finance/src/api/routes/auto_alpha.py#L604)

**What happens**

The WebSocket endpoints validate that a JWT is present and valid in non-dev environments, but they do not enforce role- or channel-level authorization.

Any valid authenticated token can subscribe to:

- `portfolio`
- `alerts`
- `orders`
- `market`
- `auto-alpha`

There is no check that, for example, a `viewer` should be allowed to receive order or portfolio streams.

**Why this is serious**

This is a privilege-separation failure. Even if the HTTP API uses role checks correctly, the WebSocket layer currently collapses all authenticated roles into one access class.

That creates a lateral information exposure path for lower-privilege accounts or leaked low-privilege API keys.

**Recommended fix**

- Add per-channel authorization checks based on JWT role.
- Define a channel policy explicitly, for example:
  - `portfolio`, `orders`: trader+
  - `alerts`: risk_manager+
  - `auto-alpha`: researcher+ or admin
  - `market`: viewer+ if intended

---

### 5. High: Production compose still allows fallback database password `dev_only_password`

**Severity:** High

**Affected code:**

- [docker-compose.yml](/D:/Finance/docker-compose.yml#L7)
- [docker-compose.yml](/D:/Finance/docker-compose.yml#L8)
- [docker-compose.yml](/D:/Finance/docker-compose.yml#L41)

**What happens**

The compose file sets `QUANT_ENV: prod`, but still provides a fallback DB password:

- `postgresql://postgres:${DB_PASSWORD:-dev_only_password}@db:5432/quant`
- `POSTGRES_PASSWORD: ${DB_PASSWORD:-dev_only_password}`

So a production-tagged deployment can silently come up with a known default database password.

**Why this is serious**

Even if the DB is not internet-exposed, this is still unsafe:

- it weakens internal trust boundaries
- it enables trivial compromise from any foothold inside the deployment network
- it creates a configuration mismatch where "prod" does not actually enforce secret presence

**Recommended fix**

- Replace fallback expansion with required expansion:
  - `${DB_PASSWORD:?Set DB_PASSWORD}`
- Do not allow any default password in the production compose path.

## Additional observations

These were not the top three critical issues, but they are worth fixing:

### A. Rate limiter key function is broken

**Affected code:**

- [src/api/app.py](/D:/Finance/src/api/app.py#L35)
- [src/api/app.py](/D:/Finance/src/api/app.py#L41)

`_rate_limit_key()` imports `decode_token` from `src.api.auth`, but that function does not exist. The exception is swallowed and the limiter falls back to IP-based limiting.

This is not a severe vulnerability by itself, but it means the intended per-user throttling is not actually in effect.

### B. Security tests are too permissive to catch real auth regressions

**Affected code:**

- [tests/security/test_api_auth.py](/D:/Finance/tests/security/test_api_auth.py#L44)
- [tests/security/test_api_auth.py](/D:/Finance/tests/security/test_api_auth.py#L55)

The auth tests accept `(200, 401, 403)` for invalid or missing credentials in dev-mode scenarios. That makes them weak at catching accidental auth relaxation.

### C. Health/docs exposure should be reviewed explicitly

The app exposes `/docs` and `/redoc` in all environments via FastAPI defaults. That is not automatically a vulnerability, but it should be an explicit decision for prod, not an accidental default.

## Recommended remediation order

### Immediate

1. Protect or remove `/api/v1/ops/*`
2. Protect or remove `/metrics`
3. Reject default `admin_password` outside dev
4. Remove DB password fallback from production compose

### Next

5. Add role-based WebSocket authorization
6. Fix rate limiting key function
7. Tighten security tests so auth failures are deterministic in non-dev

## Final assessment

The system does **not** appear to contain an obvious unauthenticated remote code execution path from this review pass.

However, it **does** contain severe confidentiality and control weaknesses:

- direct unauthenticated operational data exposure
- sensitive metrics exposure
- bootstrap admin credential risk
- missing privilege separation in WebSocket subscriptions

Those are enough to block any claim of production-hardening until fixed.
