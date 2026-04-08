
# WhatsApp Fynd 🏠

> WhatsApp DM bot that connects accommodation seekers with listers using AI-powered semantic matching. Berlin-first, multi-city ready.

## Project Overview

**WhatsApp Fynd** is a WhatsApp bot where:
- **Listers** describe their apartment
- **Seekers** describe what they need
- **AI** extracts structured data, embeds descriptions, and matches them using hybrid search (hard filters + semantic ranking)
- **Double opt-in** ensures both parties agree before contact info is shared

Inspired by [Boardy AI](https://www.boardy.ai/) and adapted for the housing market.

## Status

🚧 **Design phase** — design docs complete, implementation in progress on `feature/phase1-foundation`

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Language** | Python 3.12+ | Ecosystem (LangChain, LangGraph), async support |
| **Web Framework** | FastAPI | Async webhook handling |
| **AI Orchestration** | LangGraph | State graph, conversation memory, checkpointing |
| **LLM** | Gemini 3.1 Flash-Lite | Cost-effective ($0.25/1M tokens), fast (381 tok/s) |
| **Embeddings** | Gemini Embedding 2 (768-dim) | Via MRL truncation, fast HNSW indexing |
| **Database** | Supabase (Postgres + pgvector) | Type-safe, vector search built-in |
| **Memory** | LangGraph PostgresSaver + PostgresStore | Short-term (conversation) + long-term (semantic search) |
| **WhatsApp API** | Meta Cloud API | Direct integration, no third-party wrapper |
| **Deployment** | Docker + Railway/Fly.io | Containerized, easy scaling |

## Architecture
WhatsApp Cloud API → FastAPI webhook → LangGraph StateGraph → Gemini + Supabase


### LangGraph Nodes

| Node | Purpose |
|------|---------|
| `identify_user` | DB lookup + load long-term memory from PostgresStore |
| `classify_intent` | Gemini structured output → route to correct handler |
| `onboard_user` | Interactive buttons (lister/seeker/both) |
| `extract_listing` | Gemini extraction → Pydantic validation → completeness check → embed → save |
| `follow_up` | Ask for missing required fields (rent, rooms, etc.) |
| `search_and_match` | Extract preferences → embed → pgvector hybrid query |
| `handle_opt_in` | Double opt-in accept/reject flow |
| `respond` | Format + send WhatsApp API message |

Key Design Decisions
Hybrid matching — Structured filters eliminate bad matches, embeddings rank by "vibe"
DM-only bot — No group integration, cleaner UX, compliant with Meta 2026 AI policy
Double opt-in — Both parties accept before contact info is shared (Boardy-inspired)
LangGraph over Mastra — Mature for WhatsApp, rock-solid PostgreSQL checkpointing
Gemini 3.1 Flash-Lite — Cheapest, fast, 94-97% structured output compliance
768-dim embeddings — Fast HNSW indexing, good quality

Project Structure
whatsapp-fynd/
├── src/
│   ├── main.py                 # FastAPI app, webhook endpoints
│   ├── config.py               # Environment variables
│   ├── graph/
│   │   ├── state.py            # FyndState TypedDict
│   │   ├── graph.py            # StateGraph builder
│   │   ├── nodes/              # One file per graph node
│   │   └── prompts.py          # Gemini prompts
│   ├── models/                 # Pydantic schemas
│   ├── services/               # whatsapp.py, gemini.py, supabase.py, embeddings.py
│   └── db/migrations/          # SQL migrations
├── tests/                      # Test files
├── docs/                       # Design docs (in plans/)
├── .env.example                # Example environment variables
├── .gitignore                  # Git ignore rules
├── pyproject.toml              # Project metadata & dependencies
├── run.py                      # Local dev server entry point
└── CLAUDE.md                   # AI context for development

Built with ❤️ for housing seekers everywhere
