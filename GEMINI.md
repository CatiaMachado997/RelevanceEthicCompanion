# GEMINI.md

## Project Overview

This is a full-stack web application called "Ethic Companion". The project's core philosophy is "Trust over Engagement". It's an AI assistant designed to help users make decisions while respecting their boundaries. The central feature is the **Ethical Safeguard Layer (ESL)**, a mandatory gateway for all user-facing actions, which filters out manipulative or intrusive AI behaviors.

The application is composed of:

*   **Frontend:** A Next.js 14 (App Router) application written in TypeScript. It uses Tailwind CSS for styling and Vercel for deployment.
*   **Backend:** A FastAPI (Python) application that serves as the API. It integrates with Supabase for the database (Postgres + pgvector), Groq API for LLM (Llama 3), and Tavily for search. The backend is designed to be deployed on Google Cloud Run.

## Building and Running

### Backend

To run the backend server:

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Add your credentials to the .env file
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000` and the interactive documentation at `http://localhost:8000/docs`.

### Frontend

To run the frontend development server:

```bash
cd frontend
npm install
cp .env.local.example .env.local
# Add your credentials to the .env.local file
npm run dev
```

The frontend will be available at `http://localhost:3000`.

### Testing

To run the backend tests:

```bash
cd backend
pytest
```

## Development Conventions

*   **Ethical Safeguard Layer (ESL):** All user-facing actions *must* pass through the ESL for evaluation. This is a core, non-negotiable principle of the project. The ESL is implemented in the `backend/esl` directory.
*   **Orchestrator:** The `Orchestrator` service in `backend/services/orchestrator.py` is the "brain" that coordinates the ESL, context, and LLM services. All actions should be initiated through the orchestrator.
*   **API Client:** The frontend uses a typed API client (`frontend/lib/api.ts`) to communicate with the backend.
*   **Configuration:** Both frontend and backend are configured using environment variables. Example files (`.env.example` and `.env.local.example`) are provided.
*   **Dependencies:** Backend dependencies are managed with `pip` and `requirements.txt`. Frontend dependencies are managed with `npm` and `package.json`.
