# FinSight — Project Plan

> Status: **saved for later**. This is the initial roadmap agreed on before any code was
> written. We will work through it phase by phase, in teaching mode, starting from Phase 0.
> Nothing here is final — phases will be adjusted as we learn things along the way.

## Goal

Build a production-oriented full-stack financial portfolio intelligence platform called
**FinSight**.

The purpose is primarily educational: use it to deeply learn and practice Python, Django,
React, PostgreSQL, asynchronous processing, integrations, cloud infrastructure,
observability, and production engineering — while also producing something good enough to
publish on GitHub as a serious portfolio project.

The project must be built incrementally and didactically (CodeCrafters-style), not generated
in one shot. The goal is understanding *why* every component exists, what problem it solves,
what alternatives exist, and what trade-offs are involved — not just working software.

## Teaching / development mode

For every phase, the mentor (Claude) should:

1. Explain the objective.
2. Explain the relevant concepts briefly.
3. Explain why we are introducing the technology or architectural pattern.
4. Give a small implementation task.
5. Wait for the implementation.
6. Review the implementation.
7. Point out mistakes, improvements, and trade-offs.
8. Ask questions to verify understanding.
9. Only then move to the next task.

**Do not**: build the entire project at once, generate large amounts of unexplained code,
hide important details behind abstractions, auto-solve every problem, or introduce
technologies before explaining why they're needed.

Prefer: small tasks, incremental commits, tests before/alongside implementation, debugging
exercises, architecture discussions, deliberate mistakes to diagnose, and comparisons with
Java/Spring Boot (the developer's background: Java/Spring Boot, Node.js, Clojure, Go, SQL,
Kafka, AWS, distributed systems — so skip basic programming explanations and focus on
Python idioms, Django architecture, modern React patterns, full-stack trade-offs, and
production concerns).

## Product

FinSight is a simplified financial portfolio intelligence platform for financial
professionals to manage clients, advisors, investment accounts, portfolios, and positions;
upload and asynchronously process financial documents; extract structured financial
information; analyze portfolio risk; evaluate compliance rules; search financial
information; and review analysis results through a web interface. The domain stays generic,
independent of any real company/product.

## Domain model (introduced progressively, not all at once)

`Advisor`, `Client`, `Account`, `Portfolio`, `Position`, `Document`, `RiskAnalysis`,
`ComplianceRule`, `ComplianceViolation` — plus more as the architecture requires.

## Core user workflow (target end state)

```
Advisor → Client → Account → Portfolio → Positions → Document Upload
  → Asynchronous Processing → Data Extraction → Portfolio Analysis
  → Risk Analysis → Compliance Analysis → Advisor Review
```

The React app provides the UI for this workflow.

## Technology stack

- **Backend**: Python 3.13+, Django, Django REST Framework, PostgreSQL, Pytest
- **Frontend**: React, modern ES6+, HTML5/CSS3, an appropriate state-management solution
  (Redux or similar when justified)
- **Async processing**: Celery, Redis (initial broker); later investigate SQS, Kafka, and
  task-queue vs event-streaming trade-offs
- **Search / data**: PostgreSQL, Redis, Elasticsearch
- **Infrastructure**: Docker, Docker Compose, AWS (RDS, S3, EC2, Lambda, IAM, networking,
  secrets/configuration)
- **Observability**: OpenTelemetry, Prometheus, Grafana, Loki, Tempo; possibly Sentry
- **IaC**: Terraform

## Architectural principle

Build **feature-by-feature**, not technology-by-technology, whenever practical. A
meaningful feature goes through:

```
Requirement → Domain model → Database → Backend API → Frontend UI
  → Tests → Deployment → Observability → Production verification
```

The goal is to practice owning features end-to-end, not learning isolated technologies.

## Phase roadmap

| Phase | Title |
|---|---|
| 0 | Project & Domain Setup |
| 1 | Production Python Foundations |
| 2 | Django Fundamentals |
| 3 | First End-to-End Feature — Client Management |
| 4 | React Deep Dive |
| 5 | Portfolio & Account Management |
| 6 | Django ORM & PostgreSQL Deep Dive |
| 7 | Portfolio Analytics |
| 8 | Risk Engine |
| 9 | Compliance Engine |
| 10 | Document Management (synchronous) |
| 11 | Asynchronous Processing with Celery |
| 12 | Broker Architecture (Celery/Redis/SQS/Kafka trade-offs) |
| 13 | AI-Assisted Document Extraction |
| 14 | AI-Assisted Development Practices |
| 15 | Elasticsearch |
| 16 | External Integrations |
| 17 | Observability |
| 18 | Reliability & SLOs |
| 19 | Cross-Stack Debugging |
| 20 | Security |
| 21 | Multi-Tenancy |
| 22 | Docker |
| 23 | AWS |
| 24 | Terraform |
| 25 | Production Verification |
| 26 | Architecture Review |
| 27 | Senior Backend / Full-Stack Interview Preparation |

Full phase-by-phase detail (objectives, concepts, and tasks) is below.

---

### Phase 0 — Project & Domain Setup

Objective: understand the product before writing significant code.

Tasks: define initial product scope, first user persona, first feature; create the
repository; establish project documentation; define development conventions; set up Git.

Create: README, architecture notes, development setup, initial backlog. Do not create the
complete domain model yet.

### Phase 1 — Production Python Foundations

Objective: become comfortable writing maintainable Python before relying heavily on Django.

Study/practice: functions, modules, packages, type hints, dataclasses, exceptions,
comprehensions, generators, iterators, context managers, dependency management, virtual
environments, testing with pytest, Pythonic code, code organization.

Build small standalone portfolio calculations (total portfolio value, allocation
percentages, concentration, top holdings) with tests. Compare relevant concepts with Java
when useful.

### Phase 2 — Django Fundamentals

Objective: understand Django's architecture, not just follow tutorials.

Learn: project vs app, settings, URL routing, views, models, migrations, Django ORM,
serializers, DRF, validation, HTTP lifecycle. Create the first backend app, starting with
the Client domain.

### Phase 3 — First End-to-End Feature: Client Management

Architecture: `React → REST API → Django → PostgreSQL`

Implement: create/list/retrieve/update/delete client.

Frontend: client list, client form, client details, loading/error/empty states.

Learn: React components, props, state, hooks, API calls, forms, frontend/backend
contracts, HTTP errors. Feature must work end-to-end before moving on.

### Phase 4 — React Deep Dive

Objective: become comfortable with modern React development.

Study: component composition, hooks, controlled forms, derived state, effects, API
integration, loading/error states, reusable components, frontend business logic, routing,
state management, Redux or equivalent. Also: HTML semantics, responsive CSS, accessibility,
rendering performance. No unnecessary frontend libraries — every dependency needs a reason.

### Phase 5 — Portfolio & Account Management

Introduce: Advisor, Account, Portfolio, Position. Build end-to-end.

Frontend: `Advisor → Clients → Accounts → Portfolio → Positions`
Backend: `REST API → Django → PostgreSQL`

Learn: relationships, foreign keys, nested data, API design, validation, pagination,
filtering, sorting.

### Phase 6 — Django ORM & PostgreSQL Deep Dive

Objective: understand what happens beneath Django.

Study: QuerySets, lazy evaluation, `select_related`, `prefetch_related`, `annotate`,
`aggregate`, F expressions, Q expressions, transactions, indexes, constraints, isolation,
migrations, query plans.

Exercise: create an N+1 query, detect it, fix it, measure the difference.

Also: schema design, normalization/denormalization, indexes, composite indexes, safe schema
migrations, data integrity.

### Phase 7 — Portfolio Analytics

Implement: total portfolio value, asset allocation, top holdings, concentration, sector
allocation, geographic allocation.

Discuss where business logic should live (not embedded in views/components). Expose via API
and build the React dashboard.

### Phase 8 — Risk Engine

Deterministic risk engine. Example rules: max concentration per asset, max crypto exposure,
min cash allocation, max exposure to a sector.

Generate `RiskAnalysis` with: rule, observed value, threshold, result, timestamp,
explanation. Build advisor review UI.

### Phase 9 — Compliance Engine

Introduce `ComplianceRule`, `ComplianceViolation`. Deterministic compliance checks.

UI shows: compliant/violated rules, severity, observed value, threshold, explanation,
status.

Discuss: auditability, reproducibility, deterministic business rules, data integrity.

### Phase 10 — Document Management

Introduce `Document`. Lifecycle: `UPLOADED → PROCESSING → PROCESSED` or
`PROCESSING → FAILED`.

Implement: upload, list, details, processing status, error state. Process **synchronously**
first — understand the problem before introducing Celery.

### Phase 11 — Asynchronous Processing with Celery

Identify the problem with synchronous processing, then introduce
`Django → Celery → Redis → Celery Worker`.

Learn: tasks, workers, brokers, task lifecycle, retries, task states, concurrency,
idempotency, timeouts, scheduling.

Convert document processing to async. Frontend shows UPLOADED/PROCESSING/PROCESSED/FAILED.
Discuss polling vs alternatives for status updates.

### Phase 12 — Broker Architecture

Understand Celery (task execution framework) vs broker (message transport: Redis/SQS/
RabbitMQ/Kafka). Start with Celery + Redis, then investigate Celery + SQS.

Discuss: operational complexity, reliability, scalability, semantics, monitoring, AWS
integration, task processing vs event streaming. Explain trade-offs before switching
anything.

### Phase 13 — AI-Assisted Document Extraction

Simulated AI provider pipeline:
`Document → Extraction task → AI provider → Structured JSON → Validation → Database`

The provider should sometimes produce invalid JSON, missing fields, invalid symbols,
incorrect totals, timeouts, rate-limit errors. The deterministic validation layer must
protect the database from invalid AI output — intentional.

### Phase 14 — AI-Assisted Development

Practice using Claude Code as part of the workflow: generating small pieces of code,
reviewing generated code, asking for alternatives, writing tests for AI-generated code,
detecting hallucinated APIs, identifying security problems, rejecting unnecessary
abstractions. Never blindly accept generated code.

Flow for important changes:
`AI proposal → review → tests → architecture review → implementation`

Document useful AI-assisted development practices in the repo.

### Phase 15 — Elasticsearch

Introduce only after PostgreSQL search becomes insufficient for a meaningful use case
(e.g., searching portfolios, securities, or documents).

Architecture: `React → Django API → Elasticsearch`

Study: indexing, mappings, analyzers, full-text search, relevance, pagination,
synchronization. Discuss PostgreSQL as source of truth vs Elasticsearch as search index, and
synchronization strategies / what happens when they disagree.

### Phase 16 — External Integrations

Simulate integration with external financial providers:
`External Provider → Integration Service → FinSight`

Introduce: timeout, rate limit, duplicate data, partial failure, malformed response,
provider outage, inconsistent data. Implement retries, timeouts, idempotency, validation,
error handling, monitoring. Discuss synchronization and data integrity.

### Phase 17 — Observability

Introduce OpenTelemetry, Prometheus, Grafana, Loki, Tempo. Instrument Django, Celery,
external integrations.

Capture metrics (request latency/count/error rate, task duration/failures, queue depth,
external API latency), logs (structured, correlation IDs, errors), traces (HTTP request, DB
calls, Celery task, external API call).

Learn to correlate: `request → trace → logs → background task`.

### Phase 18 — Reliability & SLOs

Define realistic SLOs (e.g., "99% of document-processing jobs complete within 30
seconds"). Track latency, availability, errors, throughput, queue depth. Create dashboards
and alerts. Introduce deliberate failures and investigate them.

### Phase 19 — Cross-Stack Debugging

Realistic production incidents, e.g.: slow React page, sudden API latency increase, Django
N+1 queries, unbounded Celery queue growth, slow AI provider, Redis unavailability, stale
Elasticsearch, exhausted DB connection pool, S3 upload failure, authentication failures.

For each: `Frontend → Backend → Database → Infrastructure → Observability`. Find the root
cause, don't just patch symptoms. Document: symptoms, investigation, root cause, fix,
prevention, monitoring improvement.

### Phase 20 — Security

Study/implement: authentication, authorization, RBAC, tenant isolation, secrets management,
secure configuration, input validation, SQL injection prevention, secure file uploads,
audit logs. Protect sensitive financial information.

Discuss: least privilege, IAM, encryption, access control, auditability.

### Phase 21 — Multi-Tenancy

Introduce `Firm → Advisors → Clients → Accounts → Portfolios`. Ensure one firm cannot
access another firm's data.

Discuss approaches: shared database/shared schema, tenant ID, separate schema, separate
database. Implement a reasonable simplified approach.

### Phase 22 — Docker

Containerize Django, React, PostgreSQL, Redis, Celery worker, supporting services. Create a
Docker Compose dev environment. Understand containers, images, networks, volumes,
environment variables, health checks, startup dependencies.

### Phase 23 — AWS

Deploy a simplified production environment. Study RDS, S3, EC2, Lambda, IAM, networking,
security groups, secrets/configuration, load balancing. For each service, ask: why do we
need it, what problem does it solve, what are the alternatives, what does it cost, how does
it affect reliability. Don't blindly reproduce every AWS service.

### Phase 24 — Terraform

Introduce IaC. Manage selected infrastructure with Terraform. Learn: providers, resources,
variables, outputs, state, modules, plan/apply, environment configuration. Don't
over-engineer.

### Phase 25 — Production Verification

After deployment, verify the complete system: frontend, API, database, background workers,
document processing, integrations, search, observability, authentication. Verify failures
are observable and important business workflows actually work in production.

### Phase 26 — Architecture Review

Stop coding temporarily. Review the complete architecture: API boundaries, database design,
caching, async processing, Celery, Redis, SQS, Kafka, Elasticsearch, consistency,
idempotency, retries, rate limiting, security, observability, SLOs, scaling, cost,
deployment, failure modes.

For every major architectural decision, document: Decision, Reason, Alternatives,
Trade-offs.

### Phase 27 — Senior Backend / Full-Stack Interview Preparation

Use FinSight as an interview case study. Be able to explain, among others: why
Django/PostgreSQL/Redis/Celery; why not Kafka/SQS and when they'd be preferable; why
Elasticsearch and how to sync it with PostgreSQL; how to make Celery tasks idempotent and
handle retries; how to handle AI failures; how the system is monitored; what the SLOs are;
how to scale the API and workers; what happens if PostgreSQL becomes the bottleneck; how
financial data is protected; how to debug across React/Django/Redis/PostgreSQL; where
business logic should live; what belongs in frontend vs backend; how this would deploy on
AWS; what would change at 100x traffic.

---

## Definition of done

The project is considered complete when the developer can:

- build a feature from requirement to production
- write production-quality Python
- work fluently with Django
- design REST APIs
- work comfortably with React
- understand frontend state management
- design PostgreSQL schemas
- optimize Django ORM queries
- implement asynchronous workflows
- explain Celery and its broker
- understand Redis, SQS and Kafka trade-offs
- work with Elasticsearch
- build resilient external integrations
- instrument a system with observability
- define meaningful SLOs
- debug cross-stack production problems
- deploy using Docker and AWS
- explain security decisions
- review backend and frontend code
- use AI coding tools without blindly trusting them
- explain the architecture clearly in a technical interview

## Final principle

This project is not about creating the largest possible application. It is about creating a
progressively more sophisticated system where every new layer exists because a real
engineering problem was encountered.

Start simple. Understand the problem. Implement the simplest solution. Measure it. Find its
limitations. Introduce the next technology only when it solves a demonstrated problem.

Always ask: *What problem are we solving? Why this solution? What are the alternatives?
What are the trade-offs? How would this behave in production?*
