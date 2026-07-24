# Logistics Intelligence

An AI-powered logistics analytics dashboard built for the coding assignment in [`docs/`](docs/). It combines a traditional operational dashboard, validated natural-language analysis, and transparent demand forecasting over one immutable CSV dataset.

## What is included

- Five required KPIs with shared filters
- Order-volume, delivery-status, and carrier-delay charts
- Expandable underlying order data
- Natural-language analytics through OpenRouter
- Delay-driver diagnostics with explicit correlation/causation warnings
- Structured query plans and explainability
- Overall, category, and guarded low-confidence SKU forecasts
- Automatic backtesting across four approved forecasting methods, with manual override
- Inventory guidance with explicit methodology
- Persistent conversational AI thread, result caching, ambiguity handling, and retry states
- Docker Compose local environment
- Deployed Cloudflare Pages frontend and Python Worker API

The two supplied specifications are consistent. [`Coding_assignment.md`](docs/Coding_assignment.md) is the detailed checklist; [`logistics-spec.md`](docs/logistics-spec.md) is the concise specification faithfully converted from its DOCX source.

## Live deployment

- Application: <https://logistics-intelligence-dashboard.pages.dev>
- API health: <https://logistics-intelligence-api.nggih.workers.dev/api/health>
- Public repository: <https://github.com/nggih/spaceship-code-test>

The production Worker uses exact-origin CORS, a managed Turnstile widget, Worker secrets, and a Cloudflare Rate Limiting binding.

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
For example, if another local service owns port 8000:

```bash
BACKEND_PORT=18000 FRONTEND_PORT=3000 docker compose up --build
```

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
npm run lint
npm run build
npm run test:e2e
```

## Environment variables

| Variable | Exposure | Purpose |
|---|---|---|
| `OPENROUTER_API_KEY` | Secret, backend only | Dedicated OpenRouter inference key |
| `OPENROUTER_MODEL` | Backend | Defaults to `openrouter/free` |
| `TURNSTILE_SECRET_KEY` | Secret, backend only | Server-side challenge verification |
| `AI_SESSION_SECRET` | Secret, backend only | Signs one-hour, IP-bound AI session tokens |
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
   └── conversational question + bounded prior turns
          ↓
       first message: Turnstile → signed AI session
       follow-ups: validated AI session → rate limit
          ↓
       OpenRouter native function-tool selection
          ↓
       Pydantic tool-argument validation
          ↓
       analytics OR diagnostic OR forecast tool
          ↓
       computed answer + chart contract + table + explanation
```

The AI is a tool selector, not the source of truth. Every natural-language question is interpreted through OpenRouter—there is no deterministic natural-language parser. The model receives four native function tools: `query_logistics_analytics`, `analyze_delay_drivers`, `forecast_demand`, and `request_clarification`. It must request exactly one tool; the application then validates the arguments and executes the mapped local Python function.

Each tool has an inlined, closed JSON Schema generated from its Pydantic input model. OpenRouter receives `tool_choice: required`, strict function definitions, and `require_parameters: true`; Pydantic remains the final validation boundary before execution. `openrouter/free` is attempted first and automatically filters for tool-capable models; invalid or unavailable output falls back to a known tool-capable free model. The actual routed model and selected tool are returned in result metadata. Unknown tools, extra fields, invalid values, multiple calls, and semantically inconsistent arguments are rejected.

This uses OpenRouter's native function-calling protocol directly rather than adding LangChain or Strands. With four bounded, single-step tools, a general agent framework would add deployment weight and indirection without improving capability. The model suggests a function call; it never executes Python itself, and computed results are not sent through a second generative pass that could alter the numbers.

There is no text-to-SQL and no model-generated code execution. Tool calls dispatch only to allowlisted pure-Python functions. Cloudflare Sandboxes are therefore unnecessary for the current application.

The frontend maps five approved semantic chart types to locally owned ECharts builders. That keeps model output away from executable presentation configuration.

### API

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Service, dataset, and AI readiness |
| `GET /api/metadata` | Date range, filter options, supported fields |
| `POST /api/dashboard` | Filtered KPIs, dashboard charts, and order rows |
| `POST /api/analytics` | One validated analytical computation |
| `POST /api/diagnostics` | Delay-rate association analysis |
| `POST /api/forecast` | Overall, category, or SKU forecast |
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

The forecast aggregates monthly quantity and fills absent months with zero. Automatic mode compares a 3-month moving average, ordinary least-squares linear trend, simple exponential smoothing, and a last-observation baseline using expanding-window one-step mean absolute error (MAE). The lowest-MAE candidate is selected, while the UI also permits an explicit method override.

Forecast values are clamped to zero and rounded upward. The chart uses one shared boundary point between historical and forecast series, and the inventory recommendation adds 15% safety stock to the next-month forecast. The result displays every candidate score, the selected method, validation-period count, supporting-order count, and methodology limitations.

Overall, category, and SKU forecasts are supported. Sparse SKU forecasts are clearly marked low-confidence, include their supporting-order count, and use 30% safety stock because 313 of 355 SKUs occur only once. They are planning signals, not claims of statistical precision.

## OpenRouter budget and security

Use a dedicated OpenRouter inference key:

1. Add only the amount you are prepared to spend.
2. Set the key to a **$5 lifetime limit** with no reset.
3. Disable automatic top-up.
4. Use `openrouter/free`; validation may fall back only to another free model.
5. Store the key only as a Worker secret.

The deployed key reports a $5 lifetime cap. The first AI message in a browser session requires server-verified Turnstile. The Worker then returns a one-hour HMAC-signed token bound to the client IP; follow-up messages reuse it without another challenge. A new tab, expiration, IP change, or invalid signature requires Turnstile again. This is abuse verification, not user authentication.

Every message still passes Cloudflare's distributed 5-request/60-second burst limiter plus a 5-request/10-minute warm-isolate window. Questions and conversation turns are limited to 500 characters, history is capped at eight alternating turns, bodies over 16 KiB are rejected, model output is capped, upstream calls time out, and secrets/full upstream responses are never logged.

## Cloudflare deployment

### Backend Worker

Python Workers are currently beta. The implementation avoids pandas and native scientific packages to remain compatible with Pyodide and Worker limits.

```bash
cd backend
uv sync
uv run pywrangler secret put OPENROUTER_API_KEY
uv run pywrangler secret put TURNSTILE_SECRET_KEY
uv run pywrangler secret put AI_SESSION_SECRET
uv run pywrangler deploy
```

Set non-secret production variables such as `ALLOWED_ORIGINS` and `PUBLIC_APP_URL` in the Worker configuration before deployment.

### Frontend Pages

The deployed Pages project is `logistics-intelligence-dashboard`. For another account, create a Pages project with:

- Root directory: `frontend`
- Build command: `npm ci && npm run build`
- Output directory: `dist`
- Variables: `VITE_API_URL` and `VITE_TURNSTILE_SITE_KEY`

The deployed Pages origin must exactly match the backend `ALLOWED_ORIGINS`.

## Testing

Backend tests cover dataset invariants, KPIs, filter combinations, time grouping, delay ranking, diagnostics, every forecast scope and method, automatic MAE selection, boundary-month continuity, horizon validation, intent-specific plan rejection, cache behavior, AI ambiguity and failover, and both limiter paths.

Frontend unit tests cover API mapping, session rotation, validation errors, empty states, and forecast-method evidence. Playwright runs the real React/FastAPI stack on desktop and mobile Chromium, exercising filters, diagnostics, automatic and manual SKU forecasts, multi-turn context, clarification UI, and conversation reset.

```bash
cd backend && uv run pytest
cd frontend && npm run lint && npm test && npm run build && npm run test:e2e
```

## Assumptions and simplifications

- The CSV is immutable and small enough to load once per process/isolate.
- A database would add operational cost without improving this read-only 400-row exercise.
- Relative dates use the latest dataset date so assignment examples remain meaningful.
- The 10-minute limiter is per warm Worker isolate; the Cloudflare binding adds a distributed burst boundary.
- Free models may be slow, rate-limited, invalid, or temporarily unavailable. Invalid plans are retried/fail over; the UI reports final unavailability rather than fabricating results.

## Limitations

- No promised delivery date, so true SLA lateness cannot be calculated.
- Only one year of data is available for forecasting.
- Free OpenRouter models may change between requests.
- Conversation history is browser-local; there is no cross-device history or user authentication.
- Cloudflare Python Workers remain a beta runtime.

## Future improvements

- Add promised delivery/SLA fields and carrier service levels.
- Back analytics with D1 or an analytical store for larger datasets.
- Add Durable Objects for an exact globally consistent 10-minute window and shared query history.
- Add longer demand history, prediction intervals, and seasonal methods once at least two annual cycles are available.
- Add server-side semantic-plan caching after privacy and invalidation review.

## AI usage disclosure

I used ChatGPT and Codex as collaborative tools throughout the task. I actively directed the process, discussed the approach in depth, evaluated alternatives, reviewed the generated output, and made the final implementation and design decisions. The submitted work reflects my own understanding and judgment, with AI used to accelerate development and support problem-solving.
