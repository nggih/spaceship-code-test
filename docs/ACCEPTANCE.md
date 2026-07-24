# Acceptance Checklist

This checklist consolidates the requirements from `Coding_assignment.md` and `logistics-spec.md`. The specifications are consistent; the detailed assignment supplies bonus and README details omitted by the concise specification.

- [x] Five required logistics KPIs
- [x] At least two operational charts
- [x] Shared dataset and filters
- [x] Multi-turn natural-language conversation interface
- [x] Bounded prior-turn context for follow-up questions
- [x] Validated AI orchestration rather than AI-generated answers
- [x] No deterministic natural-language parser, text-to-SQL, or AI code execution
- [x] Production prompt contract for metrics, dates, routing, ambiguity, and examples
- [x] Dynamic, allowlisted chart selection
- [x] Filters, metric, dimensions, plan, and underlying rows shown
- [x] Per-chart query-plan and metric explainability
- [x] Diagnostic delay-association analysis
- [x] Read-only analytics
- [x] Overall, category, and guarded SKU forecasts
- [x] Forecast values, chart, recommendation, warnings, and methodology
- [x] Persistent browser conversation, ambiguity UI, result caching, retries, and empty states
- [x] shadcn/ui component structure, Tailwind CSS, and ECharts
- [x] Public-host configuration for Cloudflare
- [x] Docker Compose local environment
- [x] Secret-safe configuration
- [x] First-message Turnstile with signed session reuse
- [x] Body/history limits, exact CORS, and two-layer AI throttling
- [x] Backend tests (25 passing)
- [x] Frontend lint, unit tests, production build, and Playwright (8 passing)
- [x] Docker Compose smoke test on frontend port 3000
- [x] Architecture, assumptions, limitations, and future improvements documented
- [x] Public repository: https://github.com/nggih/spaceship-code-test
- [x] Live Pages: https://logistics-intelligence-dashboard.pages.dev
- [x] Live Worker: https://logistics-intelligence-api.nggih.workers.dev
- [x] Production Turnstile and OpenRouter Worker secrets configured
- [x] Dedicated OpenRouter key reports a $5 lifetime cap
