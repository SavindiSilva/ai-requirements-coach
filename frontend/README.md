# AI Requirements Coach — Frontend

React + TypeScript + Vite + Tailwind CSS, consuming the FastAPI backend in `../app`.

## Setup

```bash
npm install
cp .env.example .env   # adjust VITE_API_BASE_URL if the backend isn't on :8000
npm run dev
```

Runs on `http://localhost:3000` by default — this matches the backend's
`FRONTEND_URL` setting (`app/core/config.py`), which CORS is locked to.

## Scripts

- `npm run dev` — start the dev server
- `npm run build` — typecheck (`tsc -b`) and production build
- `npm run lint` — oxlint
