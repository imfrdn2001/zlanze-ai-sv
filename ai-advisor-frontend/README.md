# Zlanze AI Advisor Frontend

Standalone React frontend for the AI advisor. It does not modify or import code
from the existing Zlanze frontend.

## Features

- create, switch, and delete chat sessions;
- persistent browser history using `localStorage`;
- one backend `chat_id` per frontend session;
- multi-turn messages within the same session;
- suggested starter prompts;
- loading and API error states;
- responsive desktop and mobile layouts.

## Run locally

Start the database and AI backend first. Then:

```bash
cd ai-advisor-frontend
cp .env.example .env
npm install
npm run dev
```

Open `http://localhost:3000`.

`VITE_API_URL` controls the backend base URL. Local development uses `/api`;
Vite proxies that path to the Docker backend at `http://127.0.0.1:8001`.
This also allows a Windows browser to use the WSL frontend without separately
exposing the backend port.

## Build and test

```bash
npm test
npm run build
npm run preview
```

Conversation history is local to the current browser and device. Redis holds
the backend's compact AI context for 30 minutes; browser history remains until
the user deletes it or clears browser storage.
