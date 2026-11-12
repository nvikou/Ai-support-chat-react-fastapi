# VateCon — AI Support Agent

> AI-powered customer support automation system.

---

## Getting Started

### 1. Launch the application

**Prerequisites:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) and an OpenAI API key.

```bash
cp .env.example .env
# Set OPENAI_API_KEY in .env, then:
docker compose up --build
```

First launch takes approximately 3–5 minutes (image download and dependency installation).

### 2. Sign in

Open **http://localhost:3000** in your browser. Unauthenticated sessions are redirected to the login page.

![Login page](docs/images/login.png)

**Administrator account** (created automatically on first startup):

| Field | Value |
|-------|-------|
| Email | `admin@vatecon.com` |
| Password | `Admin123!` |

**User account:** self-service registration at http://localhost:3000/register (minimum 8 characters).

### 3. Application URLs

| Interface | URL |
|-----------|-----|
| Login | http://localhost:3000/login |
| Register | http://localhost:3000/register |
| Chat | http://localhost:3000 |
| History | http://localhost:3000/history |
| Admin dashboard | http://localhost:3000/admin |
| User management | http://localhost:3000/admin/users |
| Knowledge Base | http://localhost:3000/knowledge |
| API documentation | http://localhost:8000/docs |

> **Security note:** keep `COOKIE_SECURE=false` for local HTTP. In production behind HTTPS, set `COOKIE_SECURE=true` in `.env`.

---

## Overview

VateCon AI Support Agent is a RAG support assistant: it answers in
real time, cites sources, exposes a composite confidence score, and
escalates low-trust or sensitive cases to a human.

We do **not** advertise an unverifiable “70–80% tickets automated”
rate. Offline evaluation on a synthetic labeled set
(`nimbusdesk-v1`, 180 questions) currently measures:

| Metric | Value |
|--------|------:|
| recall@5 | **0.625** |
| MRR | 0.547 |
| Escalation F1 | 0.559 |
| Confidence ECE | 0.275 |

Full tables, date, model tag, and limits:
[evaluation/RESULTS.md](evaluation/RESULTS.md).
Methodology: [evaluation/README.md](evaluation/README.md).

**Tech stack:**
- **Backend:** FastAPI + LangChain + OpenAI GPT-4o + FAISS (RAG) + PostgreSQL
- **Frontend:** React + TypeScript + Tailwind CSS + WebSocket
- **Infrastructure:** Docker Compose (4 orchestrated services)

---

## Features

### Authentication

- Open registration for users
- JWT access token (15 min) + httpOnly refresh cookie
- Each user sees **only their conversations**
- Admin sees **everything** and manages the Knowledge Base

### Chat interface (`/`)

![User interface — chat and history](docs/images/user.png)

- Real-time WebSocket connection (JWT required)
- Sidebar with recent conversations
- Typing indicator while the AI generates a response
- Display of **confidence score** on each response (0–100%)
- Cited sources (name of the document used to answer)
- Escalation banner visible when the conversation is transferred to a human

### Admin dashboard (`/admin`)

![Admin dashboard — stats and conversations](docs/images/admin_dashboard.png)

- Global statistics: number of conversations, AI resolution rate, escalations, today’s conversations
- Distribution chart (resolved by AI / escalated / closed)
- Conversation list with filters by status (active, escalated, resolved)
- Full message view of a conversation
- Manual close button for a conversation

### User management (`/admin/users`)

![User management](docs/images/admin_users.png)

- List of all registered accounts
- Conversation count per user
- Enable / disable accounts

### Knowledge Base (`/knowledge`)

![Knowledge Base — upload and FAQ](docs/images/admin_knowledge.png)

**Document upload**
Drop a PDF or TXT file. The system automatically splits it into chunks, generates embeddings via OpenAI, and indexes them in FAISS. The agent then uses this information to answer clients.

**FAQ Builder**
Directly add Question/Answer pairs without a file. Ideal for standard answers (pricing, refund policy, hours, etc.).

### Automatic escalation

The agent automatically escalates a conversation in two cases:
1. **Confidence score < 50%** — the answer is not reliable enough
2. **Sensitive keyword detected** — refund, fraud, talk to a human, etc.

---

```bash
# Prerequisites for test notebooks
pip install requests websocket-client colorama
```

---

## Sales pitch

| Problem | Solution |
|---------|----------|
| A support team answers the same questions 50x a day | Measured retrieval/escalation quality — see [RESULTS.md](evaluation/RESULTS.md) |
| Training a chatbot takes months | Just drop your docs — up and running in minutes |
| Incorrect answers hurt reputation | Confidence score + automatic escalation to a human |
| No visibility on support | Real-time dashboard with all conversations |

**Typical ROI for an SME:** 5 to 15 hours saved per week on customer support.

---

## Environment variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | — |
| `OPENAI_MODEL` | Model used | `gpt-4o` |
| `POSTGRES_USER` | PostgreSQL user | `vatecon` |
| `POSTGRES_PASSWORD` | PostgreSQL password | `vatecon_secret` |
| `POSTGRES_DB` | Database name | `vatecon_db` |
| `SECRET_KEY` | JWT secret key | — |
| `ADMIN_EMAIL` | Initial admin email | `admin@vatecon.com` |
| `ADMIN_PASSWORD` | Initial admin password | `Admin123!` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime | `15` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifetime | `7` |
| `COOKIE_SECURE` | HTTPS-only refresh cookie | `false` |
| `ALLOWED_ORIGINS` | Allowed CORS origins | `http://localhost:3000` |

---

## Architecture

Full map: [docs/architecture.md](docs/architecture.md). Decisions:
[docs/adr/](docs/adr/README.md).

### Happy path (chat turn)

```mermaid
sequenceDiagram
    participant U as Client (React)
    participant API as FastAPI
    participant R as Redis
    participant A as SupportAgent
    participant V as FAISS
    participant L as LLM
    participant DB as Postgres

    U->>API: POST /auth/ws-ticket (Bearer JWT)
    API->>R: store one-time ticket
    API-->>U: ticket
    U->>API: WebSocket /ws/chat/{session_id}?ticket=…
    API->>R: consume ticket (fail if replay)
    U->>API: user message
    API->>A: answer(session, text)
    A->>V: retrieve top-k chunks
    V-->>A: docs + distances
    A->>L: invoke (timeout / retry / fallback)
    L-->>A: completion
    A->>A: groundedness + composite confidence
    alt score low or sensitive keyword
        A->>DB: escalate conversation
        API-->>U: escalation event
    else trusted enough
        A->>DB: persist messages
        API-->>U: assistant + confidence + sources
    end
```

### Degraded path (LLM failure)

```mermaid
sequenceDiagram
    participant A as SupportAgent
    participant C as LLM client
    participant CB as Circuit breaker
    participant P as Primary model
    participant F as Fallback model
    participant DB as Postgres
    participant U as Client

    A->>C: invoke(prompt)
    C->>CB: guard()
    alt circuit open
        CB-->>C: reject
        C-->>A: degraded / unavailable
        A->>DB: escalate (human)
        A-->>U: escalation + safe message
    else circuit closed
        C->>P: attempt (timeout)
        alt success
            P-->>C: response
            C->>CB: record_success
            C-->>A: text
        else timeout / transient error
            C->>P: retry with jitter
            alt retry OK
                P-->>C: response
            else still failing
                C->>F: fallback model
                alt fallback OK
                    F-->>C: response
                    C->>CB: record_success
                    Note over C,A: degraded=true flag
                else fallback fails
                    C->>CB: record_failure (may open)
                    C-->>A: LLMError
                    A->>DB: escalate (human)
                    A-->>U: escalation event
                end
            end
        end
    end
```

### Architecture decisions

| ADR | Decision |
|-----|----------|
| [0001](docs/adr/0001-vector-store.md) | Keep FAISS; contain concurrency and name scale-out limits |
| [0002](docs/adr/0002-faiss-vs-managed.md) | Prefer FAISS until measured thresholds trip (then pgvector/Qdrant) |
| [0003](docs/adr/0003-websocket-vs-sse.md) | WebSocket for duplex chat (not SSE/polling) |
| [0004](docs/adr/0004-composite-confidence.md) | Composite confidence; reject LLM self-scoring |
| [0005](docs/adr/0005-markdown-header-chunking.md) | MarkdownHeaderTextSplitter + recursive fallback |
| [0006](docs/adr/0006-jwt-refresh-cookie.md) | Short JWT + httpOnly refresh cookie |

### Limitations & non-goals

VateCon is a portfolio-grade support RAG demo with production *practices*,
not a full multi-tenant SaaS. In particular it does **not**:

- Claim a verified “X% of tickets automated” — only offline metrics in
  [evaluation/RESULTS.md](evaluation/RESULTS.md)
- Run a managed vector DB (FAISS on a volume; see ADR 0001/0002)
- Safely scale **multiple ingest writers** without a durable job queue
- Provide per-tenant knowledge isolation or hybrid search filters
- Guarantee calibrated confidence on live traffic (offline ECE is
  moderate; bands are directional)
- Stream token-by-token LLM output (WebSocket carries turn-level events)
- Replace human agents for refunds, fraud, or legal decisions — those
  paths escalate by design
- Offer SOC2 / HIPAA / customer-managed keys out of the box

More operator detail: [docs/](docs/architecture.md),
[SECURITY.md](SECURITY.md), [CONTRIBUTING.md](CONTRIBUTING.md).

---
