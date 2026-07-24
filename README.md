# Logistics Intelligence

An AI-powered logistics analytics dashboard built for the coding assignment in [`docs/`](docs/). It combines a traditional operational dashboard, validated natural-language analysis, and transparent demand forecasting over one immutable CSV dataset.

## What is included

- Five required KPIs with shared filters
- Order-volume, delivery-status, and carrier-delay charts
- Expandable underlying order data
- Natural-language analytics through OpenRouter
- Structured query plans and explainability
- Overall and category demand forecasts
- Inventory guidance with explicit methodology
- Docker Compose local environment
- Cloudflare Pages and Python Worker deployment configuration

The two supplied specifications are consistent. [`Coding_assignment.md`](docs/Coding_assignment.md) is the detailed checklist; [`logistics-spec.md`](docs/logistics-spec.md) is the concise specification faithfully converted from its DOCX source.

## Quick start with Docker Compose

Requirements: Docker with Compose support.

```bash
cp .env.example .env
docker compose up --build
```

Open:

- Dashboard: <http://localhost:3000>
- API documentation: <http://localhost:8000/docs>
- API health: <http://localhost:8000/api/health>

Override the default ports with `FRONTEND_PORT` and `BACKEND_PORT` in `.env` when needed.

Dashboard analytics and forecasting work without external credentials. Add `OPENROUTER_API_KEY` to `.env` to enable natural-language interpretation. Turnstile is bypassed only when `ENVIRONMENT` is not `production` and no Turnstile secret is configured.

## Local development with uv

Backend:

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
uv run pytest
```

Frontend:

```bash
cd frontend
npm install
VITE_DEV_API_PROXY=http://localhost:8000 npm run dev
npm test
npm run build
```

## Environment variables

| Variable | Exposure | Purpose |
|---|---|---|
| `OPENROUTER_API_KEY` | Secret, backend only | Dedicated OpenRouter inference key |
| `OPENROUTER_MODEL` | Backend | Defaults to `google/gemma-4-26b-a4b-it:free` |
| `TURNSTILE_SECRET_KEY` | Secret, backend only | Server-side challenge verification |
| `VITE_TURNSTILE_SITE_KEY` | Public | Browser Turnstile widget |
| `VITE_API_URL` | Public | Production Worker base URL; blank uses same origin/proxy |
| `ALLOWED_ORIGINS` | Backend | Comma-separated exact frontend origins |
| `PUBLIC_APP_URL` | Backend | OpenRouter attribution URL |
| `ENVIRONMENT` | Backend | Use `production` to require Turnstile configuration |
| `DATA_PATH` | Backend | Optional CSV path override |

Never put `OPENROUTER_API_KEY` or `TURNSTILE_SECRET_KEY` in a `VITE_` variable.

## Architecture

```text
React dashboard
   ├── dashboard filters ───────────────→ validated analytics query
   ├── forecast controls ───────────────→ forecast tool
   └── natural-language question
          ↓
       Turnstile + rate limit
          ↓
       OpenRouter structured interpretation
          ↓
       Pydantic AnalysisPlan validation
          ↓
       analytics tool OR forecast tool
          ↓
       computed answer + chart contract + table + explanation
```

The AI is an interpreter, not the source of truth. Every natural-language question is interpreted through OpenRouter. The model sees the schema, available filter values, and dataset date range—not the dataset rows—and must return a strict `AnalysisPlan`. The backend rejects unknown fields and computes the result with deterministic code. Raw AI-generated SQL and arbitrary ECharts options are never accepted.

The frontend maps five approved semantic chart types to locally owned ECharts builders. That keeps model output away from executable presentation configuration.

### API

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Service, dataset, and AI readiness |
| `GET /api/metadata` | Date range, filter options, supported fields |
| `POST /api/dashboard` | Filtered KPIs, dashboard charts, and order rows |
| `POST /api/analytics` | One validated analytical computation |
| `POST /api/forecast` | Overall or category forecast |
| `POST /api/ask` | Protected natural-language interpretation and computation |

All data endpoints are read-only.

## Data definitions

- Total orders: distinct `order_id`
- Delivered orders: `status = delivered`
- Delayed orders: `status = delayed`
- On-time rate: delivered ÷ (delivered + delayed)
- Average delivery time: calendar days from order to delivery for delivered/delayed rows
- Demand: sum of `quantity`
- Late: `status = delayed`
- Relative “today”: maximum dataset order date, 2025-12-30

The late/on-time definitions are proxies because the dataset does not include a promised delivery date.

## Forecasting

The forecast aggregates monthly quantity, fills absent months with zero, and fits an ordinary least-squares linear trend using pure Python. Forecast values are clamped to zero and rounded upward. The inventory recommendation adds 15% safety stock to the next-month forecast.

Overall and category forecasts are supported. SKU forecasting is intentionally unsupported: 313 of 355 SKUs occur only once, so a SKU trend would imply precision the dataset cannot provide.

## OpenRouter budget and security

Use a dedicated OpenRouter inference key:

1. Add only the amount you are prepared to spend.
2. Set the key to a **$5 lifetime limit** with no reset.
3. Disable automatic top-up.
4. Keep the model pinned to `google/gemma-4-26b-a4b-it:free`.
5. Store the key only as a Worker secret.

The public AI endpoint additionally requires Turnstile in production, permits five attempts per IP per ten-minute Worker-isolate window, limits questions to 500 characters, caps model output, applies an upstream timeout, and does not log secrets or full model responses.

## Cloudflare deployment

### Backend Worker

Python Workers are currently beta. The implementation avoids pandas and native scientific packages to remain compatible with Pyodide and Worker limits.

```bash
cd backend
uv sync
uv run pywrangler secret put OPENROUTER_API_KEY
uv run pywrangler secret put TURNSTILE_SECRET_KEY
uv run pywrangler deploy
```

Set non-secret production variables such as `ALLOWED_ORIGINS` and `PUBLIC_APP_URL` in the Worker configuration before deployment.

### Frontend Pages

Create a Cloudflare Pages project connected to the repository:

- Root directory: `frontend`
- Build command: `npm ci && npm run build`
- Output directory: `dist`
- Variables: `VITE_API_URL` and `VITE_TURNSTILE_SITE_KEY`

The deployed Pages origin must exactly match the backend `ALLOWED_ORIGINS`.

## Testing

Backend tests cover dataset invariants, KPIs, filter combinations, time grouping, delay ranking, forecasts, schema rejection, mocked AI responses, and throttling.

Frontend tests cover API request mapping; TypeScript compilation and the production Vite build validate component contracts and bundling.

```bash
cd backend && uv run pytest
cd frontend && npm test && npm run build
```

## Assumptions and simplifications

- The CSV is immutable and small enough to load once per process/isolate.
- A database would add operational cost without improving this read-only 400-row exercise.
- Relative dates use the latest dataset date so assignment examples remain meaningful.
- The in-memory per-IP limiter is best-effort per Worker isolate; Turnstile and the OpenRouter key limit provide the durable abuse boundaries.
- The pinned free model may be slow, rate-limited, or temporarily unavailable. The UI reports this rather than fabricating results.

## Limitations

- No promised delivery date, so true SLA lateness cannot be calculated.
- Only one year of data is available for forecasting.
- Free OpenRouter models may change between requests.
- No authentication or persistent query history.
- Cloudflare Python Workers remain a beta runtime.

## Future improvements

- Add promised delivery/SLA fields and carrier service levels.
- Back analytics with D1 or an analytical store for larger datasets.
- Add Durable Objects for globally consistent throttling and query history.
- Evaluate forecasting methods with rolling backtests and confidence intervals.
- Add cached deterministic interpretations for common questions.
- Add browser-level Playwright coverage and deployment smoke checks.
