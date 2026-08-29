# Testing strategy

FinSight is built to ship without a manual QA gate in front of every release.
That only works if the automated suite is trustworthy, fast, and layered so each
kind of test does the job it is actually good at. This document is the reasoning;
the tests themselves live next to the code they cover.

## The layers

| Layer | Lives in | Answers | Cost |
|---|---|---|---|
| **Unit — example based** | `api/portfolio/tests/test_analytics.py` | "Do the hand-computed numbers come out right?" | ~ms, no I/O |
| **Unit — property based** | `api/portfolio/tests/test_analytics_properties.py` | "Do the domain invariants hold for *every* input?" | ~seconds |
| **Integration — API** | `api/clients/tests/test_clients_api.py` | "Does the endpoint honor its contract, including error paths?" | needs a DB |
| **Contract — schema** | _(SHOULD scope)_ | "Do the frontend types still match the backend schema?" | CI only |

The pyramid is deliberate: most of the confidence comes from the two cheap unit
layers, which is why the domain logic is a **framework-free module** (`portfolio/analytics.py`
imports nothing from Django). Pull that logic into views or serializers and it can
only be tested through HTTP and a database — slower, and with the interesting
branches buried under framework code.

## Property-based testing

`test_analytics_properties.py` uses [Hypothesis](https://hypothesis.readthedocs.io/).
Rather than asserting specific outputs, it states invariants and lets Hypothesis
search for a counterexample:

- `total_value` equals the sum of the individual market values, and is never negative
- every allocation weight is in `(0, 1]`, and the weights of a portfolio with value sum to 1
- the Herfindahl index and the largest-position weight are always fractions
- a single-symbol portfolio is fully concentrated (weight 1, HHI 1)
- `top_holdings(n)` is a descending prefix of the holdings, at most `n` long
- adding a worthless lot (zero price or quantity) changes nothing

Writing these invariants is what surfaced the original bug where `allocations()`
returned a `0.0` entry for held-but-worthless symbols — a case no example test
had thought to cover. That is the point: property tests do some of the
exploratory work a QA engineer would otherwise do by hand.

## What runs in CI

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml), on every push and PR:

1. **`ruff check`** — lint, repo-wide. Pre-existing files that predate the linter
   are grandfathered with narrow per-file ignores (see `pyproject.toml`), so the
   rule set is real for all new code without a big reformat commit.
2. **`ruff format --check`** — on `portfolio/` for now, expanding outward.
3. **`mypy --strict`** — scoped to `portfolio/analytics.py`. The Django layer
   needs `django-stubs` before it type-checks cleanly; that is the next step.
4. **`pytest`** — the whole suite, against a real `postgres:16` service
   container (not SQLite — the app pins the `django_prometheus` PostgreSQL
   backend, and test parity with production is worth the few seconds).
5. **Coverage floor** — `--cov-fail-under=95` on `portfolio/`. The floor is
   scoped to new domain code on purpose; a single repo-wide number just trains
   people to write assertion-free tests to move it.

## Deliberately not here yet

- **Contract tests** between the React client and the DRF schema (`drf-spectacular`
  + `openapi-typescript`, failing CI on schema drift).
- **Mutation testing** (`mutmut`) on the domain core, to check the tests actually
  fail when the code is broken — coverage says a line ran, not that a test would
  notice it changing.
- **`factory_boy`** fixtures once a second model-backed slice exists.
- Frontend unit tests (Vitest) and a smoke end-to-end.

These are the SHOULD / COULD scope, tracked so the strategy is visible before the
code catches up.
