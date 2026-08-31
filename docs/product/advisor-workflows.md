# FinSight — Advisor Workflows

The product lens for FinSight. Where [`docs/PLAN.md`](../PLAN.md) is a learning
curriculum (a sequence of phases, each introducing a technology), this document is about
**what the software is for**: the day-to-day work of a financial advisor, and the
workflows FinSight exists to support.

Keep this in mind while building. Every feature should trace back to a question an advisor
is actually trying to answer.

---

## Why this doc exists

It is tempting to describe FinSight as "a CRUD app for portfolios". That framing produces a
collection of technical demos — a clients table, a positions table, some endpoints — with
no spine.

The better framing: FinSight is an **advisor's working surface**. An advisor opens it to
answer one question —

> *"What do I need to know about my clients, their portfolios, and anything that needs my
> attention today?"*

— and everything in the product is in service of that. The domain is deliberately generic
and not tied to any real company or product; this doc describes the shape of the problem,
drawn from how advisor-facing wealth-management platforms generally work.

**How the three planning surfaces relate:**

| Surface | Question it answers | Status |
|---|---|---|
| [`docs/PLAN.md`](../PLAN.md) | *In what order do I learn the stack?* | frozen curriculum |
| **this doc** | *What is the product, and what does an advisor do with it?* | living product model |
| GitHub issues (`diego3/finsight`) | *What exactly is the next unit of work?* | per-task specs |

---

## Persona: the financial advisor

The advisor manages money for a set of clients (individuals, families, small institutions)
on behalf of a wealth-management firm. Their day is spent moving between disconnected tools:
a CRM for client contact data, custodial platforms (Schwab, Fidelity, Pershing) for what
the client actually holds, spreadsheets for analysis, a document store for statements and
paperwork, and email for everything else.

They are **not** thinking about Django, Celery, or PostgreSQL. On a Monday morning they want
to know: which clients are off track, which need a review, what paperwork is missing, and
what they should do about it. FinSight's job is to connect those scattered pieces —
profile, risk, policy, portfolio, compliance — into one place so the advisor can see the
whole picture and act on it.

Secondary users appear later: a **compliance / supervisory** user who reviews the advisor's
book for issues, and eventually **firm** administrators (multi-tenancy).

---

## The advisor's mental model

```
                          Advisor
                             │
                 ┌───────────┼───────────┐
                 │           │           │
              Clients    Portfolios    Tasks
                 │           │           │
              Profile      Risk      Exceptions
                 │           │           │
                 └───────────┼───────────┘
                             │
                         Documents
                             │
                             ▼
                       AI / Extraction
                             │
                             ▼
                        Compliance
                             │
                             ▼
                        Audit Trail
```

## The core loop

Almost every advisor workflow is a walk around this loop:

```
Understand the client   →   Understand the portfolio   →   Compare against
   (profile, risk,             (allocation, holdings,        objectives & policy
    objectives)                 concentration)                (IPS, rules)
                                                                   │
                                                                   ▼
   Take & document      ←    Surface what needs      ←────────  Identify gaps
   the action                attention (exceptions)             & violations
```

The domain objects line up with the loop:

```
Client ─▶ RiskProfile ─▶ IPS ─▶ Portfolio ─▶ Analysis ─▶ Rule ─▶ Violation ─▶ Exception ─▶ Audit Trail
```

All terms are defined in [`CONTEXT.md`](../../CONTEXT.md).

---

## Feature areas

Thirteen areas, grouped by where they sit in the core loop. Each notes the domain objects
it touches and the roughly corresponding phase(s) in [`docs/PLAN.md`](../PLAN.md). UI
sketches are illustrative, not final.

### Understand the client & portfolio

#### 1. Client dashboard

The advisor selects a client and sees profile, risk, policy, portfolio, and compliance
state **connected on one screen** rather than spread across tools.

```
John Smith
────────────────────────────────────
Risk Profile        Moderate
Risk Score          62
IPS                 Current
Last Review         12 days ago

Portfolio           $2.4M
Target Allocation   60 / 40
Current Allocation  67 / 33

⚠ 2 Compliance Issues
⚠ 1 Concentration Alert

Accounts
  • Schwab IRA
  • Fidelity Taxable
  • Pershing 401(k)
```

- **Domain:** Client, RiskProfile, IPS, Account, Portfolio, Violation
- **Frontend:** a `/client/:id` route — client info, risk profile, accounts, portfolio
  summary, alerts, recent activity
- **PLAN phases:** 3 (client), 5 (accounts/portfolio), 7 (portfolio summary)

#### 2. Portfolio analysis

*"How is this client's portfolio actually positioned?"*

```
Portfolio: John Smith            Value: $2,400,000

Asset Allocation                 Top Holdings
────────────────────             ────────────────────
Equities        67%              AAPL          22%
Fixed Income    28%              MSFT           9%
Cash             5%              VOO            8%
                                 ...

Risk
────────────────────
Overall Risk        Moderate
Concentration       HIGH
Equity Exposure     HIGH
Cash                OK
Portfolio Drift     WARNING
```

- **Domain:** Portfolio, Position/Holding, Allocation, Concentration, Drift
- **In code today:** `api/portfolio/analytics.py` already computes `total_value`,
  `allocations`, `top_holdings`, `herfindahl_index`, `largest_position_weight` — pure, no
  persistence yet
- **PLAN phases:** 7 (analytics), 8 (risk assessment)

#### 3. Search

*"I need to quickly find clients, documents, securities, and compliance records across a
large dataset."*

```
[ John Smith                                    🔍 ]

John Smith
  ├── Client profile
  ├── Accounts
  ├── Portfolios
  ├── Documents
  ├── IPS
  └── Compliance history
```

This is where Elasticsearch earns its place — driven by a real product need, not a résumé
line.

- **Domain:** cross-cutting — Client, Document, Position, Violation
- **PLAN phase:** 15

### Establish the mandate

#### 4. Risk-profile questionnaire

Establishing a new or existing client's risk profile.

```
Risk Profile

How would you react to a 20% portfolio decline?
  ○ Sell everything
  ○ Reduce exposure
  ● Stay invested
  ○ Increase investment

Investment horizon:      [ 10+ years ]
Liquidity needs:         [ Low ]
Investment experience:   [ Experienced ]
```

The questionnaire is **not** the whole suitability assessment. It captures willingness
(**tolerance**) and ability (**capacity**) to take risk; advisor commentary and
client-specific circumstances still matter and belong alongside it.

```
RiskProfile
  ├── tolerance
  ├── capacity
  ├── horizon
  ├── liquidity
  └── objectives
```

- **Domain:** RiskProfile (its own entity; today it's just an enum on `Client`)
- **PLAN phases:** extends 3 / 5 (no dedicated phase yet)

#### 5. Investment Policy Statement (IPS)

The document that answers *"what are we actually allowed and expected to do with this
client's portfolio?"* — and then becomes the reference for all monitoring.

```
Investment Policy Statement          Client: John Smith

Objective:         Long-term growth
Risk:              Moderate

Target Allocation                 Allowed Range
Equities       60%                Equities      50–70%
Fixed Income   40%                Fixed Income  30–50%

Restrictions:
  • No tobacco companies
  • Maximum 10% crypto
  • Maximum 15% single security
```

The system generates the IPS from the client's risk profile and portfolio policy, then
uses those same parameters to detect drift, concentration, and restriction breaches. This
gives the compliance/risk engine a **single source of truth**.

- **Domain:** IPS, RiskProfile, Portfolio, Allocation, Compliance Rule
- **PLAN phases:** new — sits between 5 and 9; prerequisite for meaningful compliance

### Monitor & work exceptions

#### 6. Portfolio drift alert

IPS says equities target 60%, allowed 50–70%. The portfolio drifts to 74%.

```
⚠ Portfolio Drift          John Smith

Target:        60%
Current:       74%
Allowed max:   70%

Status: OUT OF POLICY

[ Review ]  [ Dismiss ]  [ Rebalance ]
```

- **Domain:** Portfolio → Analysis → IPS → Violation → advisor action
- **PLAN phases:** 8 / 9 (depends on IPS existing)

#### 7. Concentration alert

```
⚠ Concentration Risk

AAPL represents 28.4% of the portfolio.
Policy maximum:  20%
Current value:   $681,600

[ Review Position ]  [ Document Exception ]
```

The system should not just shout "Violation!". A large legacy position, tax consequences of
selling, or a legitimate exception are all possible — the product **facilitates the
advisor's judgment and its documentation**.

- **Domain:** Concentration, Compliance Rule, Violation, Exception
- **In code today:** `largest_position_weight` / `herfindahl_index` in
  `api/portfolio/analytics.py`
- **PLAN phases:** 7 (measurement) + 8 (rule)

#### 8. Task / exception inbox

The main screen. Instead of making the advisor navigate to find problems, surface them:

```
Good morning, Sarah

Things requiring your attention
────────────────────────────────────
🔴 2 Critical
   • John Smith — Concentration violation
   • Jane Doe — Missing KYC information

🟡 4 Warnings
   • Bob Johnson — Portfolio drift
   • Alice Brown — Risk profile expired
   • ...

🟢 12 Recently completed
```

The product becomes **workflow-oriented**: the advisor works through exceptions, not just
"views data".

- **Domain:** Task / Exception Inbox, aggregating Violation + Document + RiskProfile state
- **PLAN phases:** 9+ (net-new UI concept over the risk/compliance output)

### Documents

#### 9. Document upload & extraction

```
John_Smith_Schwab_Statement.pdf

Uploading…  →  Processing…  →  Extracting…  →  Validation…  →  Ready for Review
```

Extracts: account, positions, share counts, cost basis, account type, lots, acquisition
dates — from custodial statements (Schwab, Fidelity, Pershing). **Low-confidence
extractions are surfaced for human review**, not silently accepted.

- **Domain:** Document (UPLOADED → PROCESSING → PROCESSED | FAILED), Extraction, Position,
  Lot
- **PLAN phases:** 10 (synchronous), 11 (async via Celery), 13 (AI extraction + validation)

#### 10. "Good Order" review

When an advisor uploads new account paperwork, required information is checked **before the
workflow proceeds**:

```
Document Review
────────────────────────
✓ Client information
✓ Account information
✓ Investment objective
✓ Risk profile
⚠ Missing beneficiary designation
⚠ Missing signature

Status: NEEDS REVIEW      [ Fix Issues ]
```

- **Domain:** Good Order, Document, workflow state
- **PLAN phases:** 10+ (document validation); a step inside onboarding

### Compliance & oversight

#### 11. Compliance review

A compliance/supervisory user reviews the book:

```
Compliance Dashboard          Open Issues: 17

By Type
────────────────────
Suitability       5
Concentration     4
Risk mismatch     3
Documentation     3
Trading           2
```

Drilling into one issue shows the rule, the observed value, the evidence, when it was
detected, and its status — with actions to assign, document an exception, or resolve. The
important part: the system keeps a **record of what happened** — a system of record for
supervisory actions (reviews, approvals, exceptions, sign-offs), retained and indexed for
auditability.

- **Domain:** Compliance Rule, Violation, Exception, Audit Trail
- **PLAN phases:** 9 (engine), 20 (audit logs), 21 (multi-tenant supervision)

#### 12. Personal trading / pre-clearance *(later)*

```
Pre-Clearance Request
Security: AAPL     Transaction: BUY     Quantity: 100

⚠ RESTRICTED SECURITY
AAPL appears on the firm's restricted list.
Request requires CCO review.

[ Submit for Review ]
```

Pre-clearance against a restricted list, plus reconciliation of approvals against actual
brokerage transactions. A more advanced module — a later FinSight phase, not the first
version.

- **Domain:** Pre-Clearance, Restricted List, Audit Trail
- **PLAN phases:** post-20 (compliance module extension)

### End-to-end

#### 13. Client onboarding

The flagship. See [The two flagship workflows](#the-two-flagship-workflows) below.

---

## The two flagship workflows

FinSight should be organised around two end-to-end workflows. Everything else is a
component of one of them.

### A. Client onboarding

```
New Client
   ↓
Client Information
   ↓
Risk Profile
   ↓
Upload Existing Statements
   ↓
AI Extraction
   ↓
Portfolio Created
   ↓
Risk Analysis
   ↓
IPS Generated
   ↓
Compliance Check
   ↓
Account Opening   (Good Order validation + supervisory review)
   ↓
Ready
```

This one workflow exercises nearly the entire stack:

```
React  →  Django API  →  PostgreSQL  →  S3  →  Celery  →  Redis
      →  AI extraction  →  Portfolio analysis  →  Compliance  →  Notifications / workflow
```

That is exactly the kind of end-to-end feature the target role is about: data model →
Django API → React UI → integrations → database → production behavior.

### B. Portfolio review

The Monday-morning loop for an **existing** client:

```
Open client  →  Review portfolio positioning  →  Compare vs IPS
      →  See drift / concentration / suitability flags
      →  Decide: rebalance, document an exception, or dismiss
      →  Action is recorded in the audit trail
```

Shorter, run far more often, and the reason the advisor logs in most days.

---

## MVP sequence

A thin vertical slice through **both** flagship workflows — the smallest thing an advisor
could conceptually use:

1. Create client
2. Capture risk profile
3. Create account
4. Upload statement
5. Extract positions *(manual or stubbed first; AI later)*
6. View portfolio
7. Calculate risk *(concentration, drift)*
8. Detect violations
9. Review exception

At step 9 the loop closes: the advisor has understood the client, seen the portfolio,
compared it to a policy, found a problem, and documented a decision.

## Progressive enhancement ladder

Once the MVP loop works, deepen it one demonstrated problem at a time:

```
→ IPS                    (turn hard-coded thresholds into a real mandate)
→ document validation    (Good Order gate)
→ async processing       (statements don't block the request — Celery/Redis)
→ AI extraction          (real extraction with a validation layer)
→ search                 (Elasticsearch, once PostgreSQL search is insufficient)
→ integrations           (pull holdings from custodians directly)
→ compliance workflows   (assignment, sign-off, supervisory review, audit trail)
→ observability          (metrics, logs, traces across the whole path)
```

---

## Mapping to `docs/PLAN.md`

`docs/PLAN.md` stays the learning curriculum — the order in which technologies are
introduced. This doc is the product lens. They are complementary: the MVP sequence below
is a **product** ordering; PLAN.md is a **learning** ordering, and the two interleave.

| MVP step / feature | PLAN phase(s) | Notes |
|---|---|---|
| Create client | 3 | in code today |
| Capture risk profile | 3 / 5 | RiskProfile becomes its own entity |
| Create account | 5 | introduces Account, Portfolio, Position |
| Upload statement | 10 | synchronous first |
| Extract positions | 10 → 13 | stub → AI + validation |
| View portfolio | 5 + 7 | analytics already partly in `portfolio/analytics.py` |
| Calculate risk (concentration, drift) | 7 + 8 | drift needs the IPS |
| Detect violations | 8 / 9 | Risk Engine + Compliance Engine |
| Review exception | 9 | Violation → Exception + audit record |
| IPS | — | net-new; slot between phases 5 and 9 |
| Task / exception inbox | 9+ | net-new UI over risk/compliance output |
| Good Order review | 10+ | document-completeness gate |
| Search | 15 | Elasticsearch |
| Integrations (custodians) | 16 | |
| Personal trading / pre-clearance | post-20 | later module |
| Observability across the workflow | 17 | |

---

## Keeping this current

- This doc and [`CONTEXT.md`](../../CONTEXT.md) evolve together. When a workflow here uses a
  domain term, that term must be defined in `CONTEXT.md`.
- Use the `mattpocock-skills:domain-modeling` skill to evolve `CONTEXT.md` as terms get
  sharpened.
- Architecture decisions that come out of building these workflows go in `docs/adr/` (not
  created yet).
- The reference product is never named in this repo — keep descriptions generic.
