# FinSight — Domain Context

Single-context project. This file is the domain glossary: the vocabulary FinSight uses, so
that code, issues, tests, and docs all name the same concept the same way. The product model
these terms serve is in [`docs/product/advisor-workflows.md`](docs/product/advisor-workflows.md);
architecture decisions go in `docs/adr/` (not created yet).

The domain is deliberately **generic** — a portfolio-intelligence platform for financial
advisors, not modelled on any named company or product. Do not name a reference product
anywhere in this repo.

**Status tags below:** `[in code]` exists today · `[partial]` exists in a reduced form ·
`[planned]` named but not built.

---

## Glossary

### People & tenancy

**Advisor** `[planned]`
The primary user. A financial professional who manages money for a set of clients on behalf
of a firm. Everything in the product serves the advisor's daily work.
*Avoid:* "user", "agent" (ambiguous — "agent" means an AI/automation elsewhere).

**Client** `[in code: `api/clients/models.py`]`
A person, family, or small institution the advisor manages money for. The first domain
entity. Has contact details and a risk profile.
*Avoid:* "customer", "account holder".

**Firm** `[planned]`
The wealth-management company that employs advisors. Becomes real at the multi-tenancy stage
(`Firm → Advisors → Clients → Accounts → Portfolios`); one firm must never see another's
data.
*Avoid:* "tenant" in user-facing text (fine as an implementation term), "organization".

**Compliance user** `[planned]`
A supervisory role that reviews an advisor's book of business for issues and signs off on
exceptions. Distinct from the advisor.

### Risk & mandate

**Risk Profile** `[partial: an enum on `Client` — conservative / moderate / aggressive]`
A structured view of how much investment risk is appropriate for a client. Planned as its
own entity with distinct parts:
- **Tolerance** — the client's *willingness* to accept losses (behavioural).
- **Capacity** — the client's *ability* to absorb losses without derailing their goals
  (financial). Tolerance and capacity are not the same and can disagree.
- **Horizon** — how long until the money is needed.
- **Liquidity needs** — how much must stay readily accessible.
- **Objectives** — what the money is for (growth, income, preservation).

The questionnaire that seeds a risk profile is **not** the whole suitability assessment;
advisor commentary and client circumstances sit alongside it.

**Risk Score** `[planned]`
A single number (e.g. 0–100) summarising the risk profile, for quick comparison and display.

**Investment Policy Statement (IPS)** `[planned]`
The agreed mandate for a client's portfolio: objective, target allocation, allowed ranges
per asset class, and restrictions (e.g. "max 15% single security", "no tobacco"). Generated
from the risk profile plus portfolio policy, and then used as the **reference for all
monitoring** — drift, concentration, and restriction checks are all "compared against the
IPS".
*Avoid:* bare "policy" (ambiguous). Say "IPS" or "the client's mandate".

### Accounts & holdings

**Account** `[planned]`
A custodial account holding some of a client's assets (e.g. "Schwab IRA", "Fidelity
Taxable"). Belongs to a client; a client can have several.

**Custodian** `[planned]`
The external institution that actually holds client assets and issues statements (Schwab,
Fidelity, Pershing). A data source, not part of FinSight.

**Portfolio** `[planned]`
The set of investable assets under management for a client (or aggregated across their
accounts). What analytics and risk checks run against.

**Position** `[planned]`
A persisted holding of a particular security within a portfolio: how many units, at what
price, in what account.

**Holding** `[in code: `api/portfolio/analytics.py`]`
The framework-free value object the pure analytics operate on: `symbol`, `quantity`,
`price`. A `Position` is the persisted, ORM-backed equivalent; analytics never see the ORM —
the API layer loads positions and passes plain `Holding` values in.

**Lot** `[planned]`
A single tax lot within a position: a batch of units acquired on one date at one cost basis.
Needed for cost-basis and tax-aware analysis.

**Market Value** `[in code: `Holding.market_value`]`
`quantity × price` for a holding; summed for a portfolio.

### Analysis

**Allocation** `[in code: `allocations()`]`
How portfolio value is split — across asset classes, symbols, sectors, or geography.
- **Target Allocation** — what the IPS says it should be.
- **Current Allocation** — what it actually is right now.

**Drift** `[planned]`
The gap between current and target allocation, once it exceeds the IPS allowed range. A
portfolio within range has drifted but is *in policy*; beyond the range it is *out of
policy* and raises a drift alert.

**Concentration** `[in code: `largest_position_weight()`, `herfindahl_index()`]`
Outsized exposure to a single position (or sector). Measured by the largest position's
weight and by the Herfindahl-Hirschman index (sum of squared weights). Checked against a
policy maximum (e.g. 20% in one security).

### Compliance

**Compliance Rule** `[planned]`
A checkable constraint on a portfolio: max concentration per asset, min cash allocation, max
crypto exposure, max sector exposure, IPS restriction, risk-mismatch, etc. A rule evaluation
records: observed value, threshold, result, timestamp, explanation.
*Avoid:* "check" as a noun for the rule itself (fine for the act of evaluating).

**Violation** `[planned]`
A recorded instance of a rule failing for a specific portfolio at a specific time. Has a
status (open / resolved) and links to its evidence. Distinct from `RiskAnalysis` in
`docs/PLAN.md`, which is the same idea for risk-engine output.

**Exception** `[planned]`
An advisor-documented, deliberately accepted deviation from policy — e.g. a concentrated
legacy position kept because selling triggers a large tax bill. The product's job is to
**support the advisor's judgment and capture its rationale**, not to just flag the
violation and stop.
*Avoid:* using "exception" to mean a software error in domain text.

**Good Order** `[planned]`
A validation gate: before an account-opening (or similar) workflow proceeds, all required
information and signatures must be present. Missing items are surfaced ("needs review"), not
silently passed through.

**Pre-Clearance** `[planned, later]`
Approval an employee must obtain before making a personal trade, checked against a
restricted list and later reconciled against their actual brokerage activity.

**Restricted List** `[planned, later]`
Securities that employees may not freely trade, maintained by the firm's compliance office.

**Audit Trail / System of Record** `[planned]`
The retained, indexed record of supervisory actions — reviews, approvals, exceptions,
sign-offs — kept for auditability. Once written, entries are not edited.

### Documents

**Document** `[planned]`
An uploaded file: a custodial statement, account paperwork, a disclosure. Lifecycle:
`UPLOADED → PROCESSING → PROCESSED` or `PROCESSING → FAILED`.

**Extraction** `[planned]`
Pulling structured data out of a document — account, positions, share counts, cost basis,
lots, acquisition dates. Low-confidence extractions are surfaced for human review rather
than accepted automatically. Starts synchronous, becomes a Celery task, later uses an AI
provider behind a deterministic validation layer.

### Workflow surfaces

**Task / Exception Inbox** `[planned]`
The advisor's work queue: everything requiring attention (violations, missing information,
expired risk profiles, drift), ranked by severity. The product is *worked through*, not just
*viewed*.

**Client Dashboard** `[planned]`
The single screen that connects one client's profile, risk, IPS, portfolio, and compliance
state.

**Portfolio Review** — see [`docs/product/advisor-workflows.md`](docs/product/advisor-workflows.md).
The recurring core loop for an existing client.

**Client Onboarding** — see [`docs/product/advisor-workflows.md`](docs/product/advisor-workflows.md).
The end-to-end workflow that takes a new client from first contact to a funded, analysed,
compliant portfolio.

### External data sources

**CRM** `[planned]` — system of record for client contact and relationship data; a data source.
**Market-Data Provider** `[planned]` — external source of prices, security metadata, classifications.

---

## For agents

Consumer rules for this file (and `docs/adr/` once it exists) are in
[`docs/agents/domain.md`](docs/agents/domain.md). In short: read this before exploring;
use these terms in issue titles, hypotheses, and test names; if a concept you need isn't
here, either you're inventing language the project doesn't use, or there's a real gap to
record with `mattpocock-skills:domain-modeling`.
