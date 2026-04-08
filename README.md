# WhatsApp Fynd

> A WhatsApp DM bot that connects accommodation seekers with listers using AI-powered semantic matching. Berlin-first, multi-city ready.

WhatsApp Fynd is an AI-powered "super-connector" for the housing market, inspired by Boardy AI. It allows listers to describe their apartments and seekers to describe their needs in plain text. The bot extracts structured data, matches users via hybrid search, and facilitates introductions through a double opt-in process.

## 🚀 Features

* **Hybrid Matching**: Combines PostgreSQL hard filters (e.g., maximum rent, minimum rooms, city) to eliminate mismatches with pgvector semantic search to rank listings by "vibe" and description.
* **AI Data Extraction**: Utilizes Gemini 3.1 Flash-Lite to extract structured Pydantic data from free-text messages.
* **Double Opt-In**: Protects privacy by requiring both the lister and the seeker to accept a match before sharing contact information.
* **Persistent Memory**: Remembers user preferences and conversation state across sessions using LangGraph PostgresSaver (short-term) and PostgresStore (long-term).
* **WhatsApp Native**: Built directly on the Meta Cloud API (no third-party wrappers) using interactive buttons and list messages for a clean UX.

## 🛠 Tech Stack

* **Language**: Python 3.12+
* **Framework**: FastAPI (Async webhook handling)
* **Orchestration**: LangGraph (StateGraph)
* **LLM**: Gemini 3.1 Flash-Lite (via `langchain-google-genai`)
* **Embeddings**: Gemini Embedding 2 (768-dim via MRL)
* **Database**: Supabase (PostgreSQL + pgvector)
* **Infrastructure**: Docker + Railway/Fly.io

## 📁 Project Structure

```text
src/
├── main.py                    # FastAPI app, webhook endpoints
├── config.py                  # Environment variables
├── graph/                     # LangGraph state graph
│   ├── state.py               # FyndState TypedDict
│   ├── graph.py               # StateGraph builder
│   └── nodes/                 # Individual workflow nodes (onboard, extract, search, etc.)
├── models/                    # Pydantic schemas (listing, search, intent, webhook)
├── services/                  # Clients for WhatsApp, Gemini, and Supabase
└── db/migrations/             # SQL schemas for users, listings, matches
