# VateCon — AI Support Agent

> AI-powered customer support automation system — built for the VateCon hackathon.

---

## Overview

VateCon AI Support Agent is a complete solution that enables a company to automate 70–80% of its customer support tickets using AI. The agent responds in real time, cites its sources, indicates its confidence score, and automatically escalates complex cases to a human.

**Tech stack:**
- **Backend:** FastAPI + LangChain + OpenAI GPT-4o + ChromaDB (RAG) + PostgreSQL
- **Frontend:** React + TypeScript + Tailwind CSS + WebSocket
- **Infrastructure:** Docker Compose (4 orchestrated services)

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Client (React)                    │
│   /           → Real-time chat interface            │
│   /admin      → Admin dashboard + analytics         │
│   /knowledge  → Document upload + FAQ builder       │
└────────────────────────┬────────────────────────────┘
                         │ HTTP + WebSocket (Nginx proxy)
┌────────────────────────▼────────────────────────────┐
│                 Backend (FastAPI)                   │
│                                                     │
│  WebSocket /ws/chat/{session_id}                    │
│       ↓                                             │
│  SupportAgent (LangChain)                           │
│       ↓                                             │
│  ChromaDB (vectorstore RAG)  ←  docs / FAQ          │
│       ↓                                             │
│  GPT-4o → response + confidence score               │
│       ↓                                             │
│  PostgreSQL (conversation history)                  │
└─────────────────────────────────────────────────────┘
```

---

## Quick Start

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- An OpenAI API key

### 1. Configure the environment

```bash
cp .env.example .env
```

Open `.env` and enter your OpenAI key:

```env
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
```

### 2. Start the project

```bash
docker compose up --build
```

First launch: about 3–5 minutes (downloads images and installs dependencies).

### 3. Access the application

| Interface         | URL                          |
|-------------------|------------------------------|
| Chat client       | http://localhost:3000        |
| Admin dashboard   | http://localhost:3000/admin  |
| Knowledge Base    | http://localhost:3000/knowledge |
| API Docs          | http://localhost:8000/docs   |

---

## Features

### Chat interface (`/`)

- Real-time WebSocket connection
- Typing indicator while the AI generates a response
- Display of **confidence score** on each response (0–100%)
- Cited sources (name of the document used to answer)
- Escalation banner visible when the conversation is transferred to a human

### Admin dashboard (`/admin`)

- Global statistics: number of conversations, AI resolution rate, escalations, today’s conversations
- Distribution chart (resolved by AI / escalated / closed)
- Conversation list with filters by status (active, escalated, resolved)
- Full message view of a conversation
- Manual close button for a conversation

### Knowledge Base (`/knowledge`)

**Document upload**
Drop a PDF or TXT file. The system automatically splits it into chunks, generates embeddings via OpenAI, and indexes them in ChromaDB. The agent then uses this information to answer clients.

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

## Environment variables

| Variable            | Description                  | Default                  |
|---------------------|-----------------------------|--------------------------|
| `OPENAI_API_KEY`    | OpenAI API key              | —                        |
| `OPENAI_MODEL`      | Model used                  | `gpt-4o`                 |
| `POSTGRES_USER`     | PostgreSQL user             | `vatecon`                |
| `POSTGRES_PASSWORD` | PostgreSQL password         | `vatecon_secret`         |
| `POSTGRES_DB`       | Database name               | `vatecon_db`             |
| `SECRET_KEY`        | Application secret key      | —                        |
| `ALLOWED_ORIGINS`   | Allowed CORS origins        | `http://localhost:3000`  |

---

## Sales pitch

| Problem | Solution |
|---------|----------|
| A support team answers the same questions 50x a day | The AI agent answers 70–80% of tickets automatically |
| Training a chatbot takes months | Just drop your docs — up and running in minutes |
| Incorrect answers hurt reputation | Confidence score + automatic escalation to a human |
| No visibility on support | Real-time dashboard with all conversations |

**Typical ROI for an SME:** 5 to 15 hours saved per week on customer support.
