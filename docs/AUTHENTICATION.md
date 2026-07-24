# Authentication and Reviewer Credentials

The default login is a single-reviewer credential flow designed for a deployed
coding-assignment application. `USERNAME`, `PASSWORD`, and
`AUTH_SESSION_SECRET` exist only in the backend environment.

## Security model

```text
Login form
  → same-origin POST /api/auth/login
  → constant-time credential comparison
  → per-IP login throttling
  → signed 8-hour HttpOnly + Secure + SameSite=Lax cookie
  → protected API and user-owned D1 conversation history
```

The browser never stores the password or the signing secret. The session cookie
contains only the username, a derived account identifier, and timestamps. Its
HMAC signature prevents modification. Logout deletes the cookie; changing the
password or `AUTH_SESSION_SECRET` invalidates existing sessions.

The existing Cloudflare Access validator remains available as an optional
enterprise identity layer. When a valid Access assertion is present, it takes
precedence over credential login.

## Password policy

The configured reviewer password must:

- Contain 12–128 characters
- Include at least one uppercase letter
- Include at least one lowercase letter
- Include at least one number
- Include at least one non-whitespace symbol
- Contain no whitespace

The backend validates this policy against the configured secret and refuses
login with a configuration error when it is not satisfied. It does not reveal
which rule failed during login. Incorrect credentials always receive the same
generic response.

## Local Docker

Add the following only to the ignored `.env` file:

```dotenv
USERNAME=reviewer
PASSWORD=<a-long-random-password>
AUTH_SESSION_SECRET=<an-independent-random-secret>
```

For convenience, local development can derive the signing key from `PASSWORD`
when `AUTH_SESSION_SECRET` is absent. Production deliberately does not permit
that fallback.

Start the application:

```bash
BACKEND_PORT=18000 FRONTEND_PORT=3000 docker compose up -d --build
```

## Cloudflare Worker secrets

Never create `VITE_USERNAME`, `VITE_PASSWORD`, or any equivalent frontend
variable. Upload the three values as encrypted Worker secrets:

```bash
cd backend
uv run pywrangler secret put USERNAME
uv run pywrangler secret put PASSWORD
openssl rand -hex 32 | uv run pywrangler secret put AUTH_SESSION_SECRET
uv run pywrangler deploy
```

The Pages build must keep `VITE_API_URL` blank so authentication and API calls
use the same-origin Pages Function proxy:

```bash
cd frontend
VITE_API_URL= npm run build
npx wrangler pages deploy dist \
  --project-name logistics-intelligence-dashboard
```

Provide the reviewer username and password privately with the submission. Do
not place them in the README, Git history, screenshots, or issue tracker.
