# Multi-tenancy architecture options

Status: **proposed — open for discussion, no decision made yet.**
Relates to: `docs/PLAN.md` Phase 21 (Multi-Tenancy), pulled forward because it
changes the shape of every table and every query we write from here on.

## Context

FinSight is sold to **firms** (registered investment advisory firms), not to
individual advisors. A firm signs up, and its advisors log in and work with
*their firm's* clients, accounts, portfolios, and documents only. So the
tenant is the **Firm**, and the domain hierarchy becomes:

```
Firm
 └─ Advisor
     └─ Client
         └─ Account
             └─ Portfolio
                 └─ Position
```

The hard requirement: **Firm A must never be able to see Firm B's data.**
This is financial data — client holdings, positions, documents — so a
cross-tenant data leak isn't a cosmetic bug, it's the kind of incident that
ends a B2B contract (and, in a real regulated product, triggers a breach
disclosure). Whatever we pick has to make that leak *structurally hard*, not
just "the code remembers to filter by firm every time."

We don't have a `Firm` model yet — only `Client` exists today. This document
is about deciding the tenancy **strategy** before we retrofit it, because
changing strategy later means a data migration across every tenant-scoped
table, not just adding a column.

## What we're optimizing for

In rough priority order for where the product is right now:

1. **Isolation strength** — how hard is it, structurally, for a bug or a
   compromised query to return another tenant's rows?
2. **Blast radius** — if isolation *does* fail (bug, bad migration, ops
   mistake), how much damage does one incident do?
3. **Operational cost per tenant** — migrations, backups, connection pools,
   monitoring — does this scale to hundreds of firms without hundreds of
   people running it?
4. **Time to market / implementation cost** — we're a small team (of one,
   learning) building an MVP to sell to firms, not a bank.
5. **Cross-tenant operations** — do we ever need to query across firms?
   (Product analytics, admin dashboards, billing usage, "how many firms are
   on the platform" — yes, we will need some of this.)
6. **Fit with Django + PostgreSQL**, since that's the stack we've already
   committed to.

These pull in different directions — that's the whole trade-off, and it's why
there are four real options instead of one obviously-correct answer.

## Option 1 — Shared schema, shared tables, `firm_id` column ("pool")

Every tenant-scoped table gets a `firm_id` foreign key. All firms live in the
same tables, in the same PostgreSQL schema, in the same database. Every query
is scoped by `firm_id`.

```sql
CREATE TABLE client (
  id UUID PRIMARY KEY,
  firm_id UUID NOT NULL REFERENCES firm(id),
  name TEXT NOT NULL,
  ...
);
CREATE INDEX ON client (firm_id);
```

Isolation is enforced in application code (a base QuerySet/manager that
always filters by `request.firm`, or Django REST Framework's
`get_queryset()` overridden per view) — optionally backstopped by
**PostgreSQL Row-Level Security (RLS)**, where the database itself refuses to
return rows unless a session variable matching the tenant is set:

```sql
ALTER TABLE client ENABLE ROW LEVEL SECURITY;
CREATE POLICY firm_isolation ON client
  USING (firm_id = current_setting('app.current_firm_id')::uuid);
```

With RLS, even a forgotten `.filter(firm=...)` on some view fails closed
instead of leaking — this is the difference between "isolation is a
convention" and "isolation is a database constraint."

**Pros**
- Cheapest to build and run. One schema, one migration, one connection pool.
- Easiest to add features that span tenants (platform admin, usage billing,
  aggregate analytics) — it's just a `GROUP BY firm_id`.
- Scales to a large number of tenants without a linear increase in
  operational objects (no per-tenant schema/DB to create, migrate, back up).
- Well-trodden path in Django (this is what most Django SaaS apps do).

**Cons**
- Weakest *structural* isolation of the four options — it's one bug away
  from a cross-tenant leak if RLS isn't used or a query bypasses it.
- Noisy-neighbor risk: one firm's expensive query or huge data volume shares
  the same database resources as everyone else.
- Can't offer a firm "your data lives in its own database" as a selling
  point (some enterprise financial clients ask for this contractually).
- All firms restore together in a disaster-recovery scenario — you can't
  restore just one firm's data to an earlier point in time without care.

## Option 2 — Schema-per-tenant ("bridge")

One PostgreSQL **database**, but each firm gets its own **schema**
(namespace) with an identical set of tables — `firm_acme.client`,
`firm_beta.client`, etc. The application switches `search_path` per request
based on which firm is logged in.

Django ecosystem tooling exists for this (e.g. `django-tenants`), which
routes each request to the right schema via middleware and runs migrations
once per schema.

**Pros**
- Stronger isolation than Option 1 — a query literally cannot see another
  schema's table without explicitly cross-schema querying, which the app
  never does. No risk of "forgot the `.filter(firm=...)`".
- Still one database to operate (one instance, one backup target, one
  connection pool at the Postgres level) — cheaper ops than Option 3.
- Per-tenant customization is easier if it's ever needed (a firm-specific
  column or table) without touching other tenants' schemas.

**Cons**
- Migrations run *N times* (once per schema) — with 500 firms, a schema
  change becomes a loop over 500 schemas instead of one `ALTER TABLE`. Needs
  its own tooling and gets slow.
- Connection pooling gets awkward: PgBouncer's transaction-pooling mode
  (the efficient one) doesn't play well with per-connection `search_path`
  switching, and Django's own connection reuse needs care here too.
- Cross-tenant queries (platform admin, analytics) require querying N
  schemas and merging in the application — no free `GROUP BY` across
  tenants.
- Postgres has practical/operational limits well before "thousands of
  schemas" (catalog bloat, `pg_dump` time, autovacuum overhead) — fine for
  dozens to low hundreds of firms, painful much beyond that.
- More Django "magic" (schema-switching middleware) — more to understand
  and debug when something goes wrong, which cuts against the project's
  learning goals somewhat.

## Option 3 — Database-per-tenant ("silo")

Each firm gets a fully separate PostgreSQL database — potentially even a
separate RDS instance for large/regulated firms. The application picks a
connection string per tenant (a small "tenant → DB" directory lives in a
shared control-plane database).

**Pros**
- Strongest isolation of the four — physically separate storage, separate
  backup/restore, separate resource limits. A bug can't cross this boundary
  even in principle.
- Best answer to an enterprise/compliance ask like "our data must not
  share infrastructure with other customers."
- Natural blast-radius containment: one tenant's runaway query, bad
  migration, or even full database loss doesn't touch anyone else.
- Per-tenant backup/restore, and even per-tenant point-in-time recovery,
  falls out for free.

**Cons**
- Most expensive to operate by far: migrations, monitoring, connection
  pooling, and backups all multiply by tenant count. 500 firms is (up to)
  500 databases to keep migrated and healthy.
- Connection management is the sharp edge: Django holds a connection pool
  per database — with many tenants you need PgBouncer (or similar) in front,
  and a control-plane lookup on every request to route to the right DB.
- Cross-tenant features (platform analytics, admin views, billing) require
  fanning a query out to every database and aggregating in application code
  — genuinely hard to do well.
- Slowest to provision a new tenant (create DB, run all migrations) unless
  automated carefully.
- Massive overkill for an MVP with a handful of design-partner firms.

## Option 4 — Hybrid / tiered: pool by default, silo on demand

Most SaaS platforms selling to a mix of small and enterprise customers land
here rather than on a single strategy for every tenant. Concretely for
FinSight:

- **Default tier**: every firm starts in the Option 1 shared-schema model
  (with RLS) — cheap, fast to onboard, fine for the vast majority of firms.
- **Enterprise tier**: a firm that needs it (compliance requirement, data
  volume, contractual isolation demand) gets **migrated to its own schema or
  database** (Option 2 or 3) — the same application code, just pointed at
  isolated storage for that one tenant.

This requires the application layer to already be tenant-*aware*
everywhere (every query scoped by firm, `firm_id` on every tenant table)
regardless of which physical storage tier a given firm sits in — so the
"pool vs. silo" decision becomes a **deployment/ops decision made per
tenant**, not a rewrite.

**Pros**
- Matches cost to the customer who's actually paying for isolation — most
  firms don't need or want to pay for silo-grade infrastructure.
- Avoids the Option 3 problem of paying full per-tenant operational cost for
  every customer from day one.
- Gives us a genuine "enterprise" tier to sell later without a rewrite.

**Cons**
- Most complex to build and reason about: two isolation mechanisms live in
  the codebase at once, and both have to be tested.
- Only pays off once we actually have enough tenants (and a real enterprise
  ask) to justify it — premature right now.
- Easy to under-invest in the "default" tier's isolation because "the
  important customers get siloed anyway" — a trap worth naming explicitly.

## Comparison

| | Isolation strength | Blast radius | Ops cost | Build cost | Cross-tenant queries | Postgres/Django fit |
|---|---|---|---|---|---|---|
| **1. Shared schema + `firm_id`** | Weakest (app-enforced; strong *with* RLS) | High if it fails | Lowest | Lowest | Trivial | Best |
| **2. Schema-per-tenant** | Strong | Medium | Medium–high, worsens with tenant count | Medium | Hard | Awkward beyond ~100s of tenants |
| **3. Database-per-tenant** | Strongest | Lowest | Highest | High | Hardest | Needs a control plane |
| **4. Hybrid (pool + silo on demand)** | Tunable per tenant | Tunable per tenant | Starts low, grows deliberately | Highest (two mechanisms) | Trivial for pooled, hard for siloed | Good, once built |

## Where this leaves us

This is genuinely a "what stage is the business at" decision more than a
"what's technically best" one — Option 3's isolation is objectively the
strongest, but it's also the most expensive answer to a question nobody
(no design-partner firm) has asked yet.

A reasonable default to start the discussion from: **Option 1 with Postgres
RLS turned on from the first migration that adds `Firm`**, keeping Option 4
in view as the deliberate next step once we have a real enterprise
prospect asking for isolation. That gets us:

- The cheapest, fastest path to a working multi-tenant MVP.
- Isolation that's enforced by the database, not just "we remembered to
  filter" — which closes most of the gap with Options 2/3 for a fraction of
  the operational cost.
- No architectural dead end: `firm_id`-scoped tables and RLS policies are
  exactly the foundation Option 4 needs later — we're not throwing this
  away if we outgrow it.

That's a starting recommendation, not a decision — the actual call (and in
particular, how much weight to put on "a firm might contractually demand
physical isolation" for the kind of firms we're targeting) is yours to make.

## Open questions to settle before implementing

1. How many firms are we realistically designing for in year one — tens,
   hundreds? This alone rules some options in or out.
2. Do we know of a specific compliance/contractual driver (e.g. a firm's own
   regulator or client-agreement language) that would demand physical
   isolation, or is that a hypothetical for now?
3. Is a "your firm's admin can export/see everything, but never another
   firm's" requirement enough, or is there also a *platform admin* role that
   legitimately needs cross-tenant visibility (support, billing)? That
   shapes how RLS policies and the admin surface get designed either way.
4. Do we anticipate firms wanting **on-premise / VPC-isolated** deployments
   at all (a step beyond even Option 3), or is this strictly a
   multi-tenant SaaS product?

## Next steps

Once a direction is picked here, Phase 21 in `docs/PLAN.md` covers the
implementation itself (introducing `Firm`, retrofitting `firm_id` onto
existing models, and — if we go the RLS route — the Django-specific pattern
for setting `app.current_firm_id` per request). That work stays out of this
PR on purpose: this PR is the decision, not the migration.
