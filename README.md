# Ethic Companion

**AI as our Companion in Decision-Making**

Ethic Companion is an AI assistant built on trust, not engagement. It helps you focus on what matters by filtering noise and respecting your boundaries—always.

## Purpose

In an era of information overload and attention manipulation, Ethic Companion is different:

- **NOT** optimized for "time in-app"
- **NOT** designed to maximize engagement
- **NOT** using dark patterns or FOMO
- **IS** optimized for your well-being
- **IS** respecting your explicit boundaries
- **IS** transparent about every decision

## Ethical Safeguard Layer

Every action that affects you passes through our **Ethical Safeguard Layer (ESL)**:

1. **You set boundaries** (e.g., "No work notifications after 7 PM")
2. **The AI proposes an action** (e.g., "Send meeting summary")
3. **ESL checks your boundaries** (Is it after 7 PM? Yes → VETOED)
4. **Decision is logged** (You can see every decision we make)

**The ESL is not optional. It is mandatory and cannot be bypassed.**

## Architecture

```
Frontend (Next.js) ↔️ Backend (FastAPI) ↔️ Supabase
                           ⬇️
                  ETHICAL SAFEGUARD LAYER
                      (Mandatory Gateway)
```

## Project Structure

```
/
├── backend/          # FastAPI backend with ESL core
├── frontend/         # Next.js 14 frontend (coming soon)
└── README.md         # This file
```

## Getting Started

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Configure your .env file
python main.py
```

See `backend/README.md` for detailed setup.

### Frontend Setup

Coming soon! (Todo #12)

## Development Roadmap

We're building this step-by-step, with the ESL as our foundation:

1. **Backend Project Structure** (Current)
2. **ESL Data Models** (Next)
3. ESL Engine Implementation
4. ESL Rule System
5. ESL Audit & Logging
6. Supabase Integration
7. Context Manager
8. ... and more!

See the full roadmap in our todo list.

## MVP Features (v1.0)

- User-defined values & boundaries
- Google Calendar integration (read-only)
- Relevance detection for upcoming events
- Context summarization (Groq + Tavily)
- Text-to-Speech summaries (Google Cloud TTS)
- ESL transparency dashboard

## Tech Stack

**Backend:**
- FastAPI (Python)
- Supabase (Postgres + pgvector)
- Groq API (Llama 3 for speed)
- Google Cloud TTS
- Tavily Search

**Frontend:**
- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS
- Vercel deployment

**Infrastructure:**
- Google Cloud Run (Backend)
- Vercel (Frontend)

## Core Principles

1. **User Well-being is Primary Metric**
2. **User Control is Crucial**
3. **Commitment to Non-Manipulation**
4. **Continuous Research and Alignment**

## Founder

**Cátia Machado**  
November 4, 2025

---

*"Trust over Engagement. Always."*

## Documentation

- [Backend README](./backend/README.md) - Detailed backend architecture and ESL design
- [Technical Design Document](./DESIGN.md) - Coming soon
- [Engineering Playbook](./docs/process/ENGINEERING_PLAYBOOK.md) - Required workflow (design review, TDD, staged rollout)
- [Design Doc Template](./docs/templates/design-doc.md)
- [Implementation Plan Template](./docs/templates/implementation-plan.md)
- [Test Plan Template](./docs/templates/test-plan.md)

## Contributing

This project is in active development. Contributions welcome, but must align with our ethical principles.

## License

TBD
