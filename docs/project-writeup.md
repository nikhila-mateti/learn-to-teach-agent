# Learn to Teach Agent — Project Write-up

## What I built

Learn to Teach Agent is an AI-assisted publishing workflow for turning technical learning notes into material that can be reviewed and taught. A user selects a topic, adds notes or saved source material, and requests a tutorial. The application produces a structured package containing an article, a teaching example, a five-question quiz, source references, claim warnings, and a publication-readiness report. The author can then edit, approve, and publish the result to a public blog hosted by the same application.

The project is implemented as a FastAPI application with server-rendered Jinja templates, a JSON API, SQLAlchemy, PostgreSQL, and a LangChain agent. It includes session-protected author pages, note uploads, deterministic content validation, an explicit content lifecycle, reader-facing articles and quizzes, Docker Compose for local operation, CI, and educational Kubernetes manifests.

The problem I wanted to address was not simply “generate an article with an LLM.” People learning a technical sequence often collect fragmented notes but struggle to turn them into durable teaching artifacts. A generic prompt can produce fluent prose, but it can also invent personal experience, measurements, sources, or commands. Those failure modes matter more when the output is published under a person’s name. I therefore designed the system around a reviewable pipeline instead of a chat box.

## My approach

The agent begins with tools rather than relying only on the user’s final prompt. Those tools load the saved learning path, relevant notes, approved knowledge packs, and a writing profile. Tool results are treated as untrusted context: the system prompt remains authoritative, and retrieved notes cannot override its instructions.

The application supports two explicit generation modes. In `notes_grounded` mode, sufficiently detailed notes may support first-person observations supplied by the author. In `curriculum_aware` mode, missing or weak notes cause the system to use a neutral teaching voice and prohibit invented personal stories. This distinction makes provenance visible instead of allowing the model to blur authored experience and generated explanation.

The model must return a typed `ContentPackage`, not arbitrary prose. Pydantic schemas define the article, teaching example, quiz, sources, warnings, and readiness fields. After generation, a deterministic validation service independently checks the package. Among other rules, it validates quiz structure, rejects placeholder or unapproved sources, detects unsupported first-person claims and fabricated metrics, flags overclaims, and checks for required teaching sections. Model-authored warnings are discarded and rebuilt from validator results so the model cannot mark its own work safe.

Generation never publishes automatically. Every item enters `needs_review`, and state transitions allow it to move through `approved` to `published`. Blocking validation issues prevent approval. The author can edit the content, which triggers validation again, and only published records are visible through public routes. This separation between generation, validation, and authorization is the central architectural decision in the project.

PostgreSQL stores notes, content packages, validation results, generation metadata, and lifecycle state. Keeping the public blog in the same application makes the workflow demonstrable end to end: source notes become a structured draft, the draft is reviewed, and the approved artifact becomes a reader-facing tutorial and quiz.

## Engineering choices and tradeoffs

I chose server-rendered FastAPI pages because they kept the project focused on workflow and reliability rather than introducing a separate frontend deployment. The UI is intentionally straightforward, but it exposes the information needed for review: generation mode, model, prompt version, sources, warnings, readiness, and lifecycle actions.

Deterministic validation is intentionally narrower than a second open-ended model review. Rules are testable, repeatable, inexpensive, and easy to explain, but they cannot establish factual truth. The system therefore treats validation as a guardrail rather than a guarantee and keeps a human in the publishing loop.

The repository includes unit and integration coverage with mocked model calls so normal CI does not require paid credentials. Tests cover authentication, agent tools, generation modes, validation behavior, content APIs, note uploads, publishing, public visibility, and health checks. Docker Compose provides the application and PostgreSQL with health checks and persistent storage, while the smoke script verifies container state and HTTP readiness.

## What I would do differently today

First, I would build evals alongside prompt development rather than after the workflow was functional. The repository contains an initial content case set, but I would turn it into a scored regression suite covering grounding, unsupported personal claims, source quality, pedagogical structure, and quiz correctness. I would run a stable subset in CI and a broader model comparison suite on demand.

Second, I would design observability and cost controls into the generation boundary. Each run should record latency, token usage, estimated cost, provider/model, tool-call sequence, validation outcomes, and retry count. Traces should use structured redaction so private notes and credentials are not copied into logs.

Third, I would move generation out of the web request cycle. A durable background queue would make retries, cancellation, progress reporting, provider rate limits, and longer jobs easier to manage. Idempotency keys would prevent duplicate drafts when users retry.

Finally, I would replace the MVP operational pieces before treating the system as multi-user production software: Alembic migrations instead of startup `create_all`, managed PostgreSQL with backups and pooling, object storage for uploads, a managed identity provider, CSRF protection, HTTPS-only cookies, and explicit author/reviewer/publisher roles. These are deliberate next steps rather than capabilities the current repository claims to have.

The result is a compact but complete demonstration of how I approach LLM application engineering: constrain the model with grounded tools and typed contracts, verify important properties outside the model, preserve provenance and lifecycle state, test without paid dependencies, and keep consequential actions under human control.
