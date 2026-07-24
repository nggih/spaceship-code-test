# Cloudflare Access Deployment

The application uses Cloudflare Access for browser login and Cloudflare D1 for
user-owned conversation history. Reviewer credentials must be delivered
privately with the submission and must never be committed to this repository.

## Request flow

```text
Browser
  → Cloudflare Access login for the Pages hostname
  → Pages application
  → same-origin /api/* Pages Function proxy
  → Python Worker validates Cf-Access-Jwt-Assertion
  → D1 query scoped by the immutable Access subject claim
```

The Worker validates the Access JWT signature, issuer, audience, expiry, and
subject. An email header by itself is never trusted. D1 queries always include
the authenticated subject, preventing one reviewer from reading or mutating
another reviewer's conversations.

## One-time Cloudflare configuration

1. Open **Zero Trust → Access controls → Applications**.
2. Create a **Self-hosted** application for
   `logistics-intelligence-dashboard.pages.dev`.
3. Choose a browser identity provider and create an **Allow** policy containing
   only the reviewer account(s). A dedicated reviewer account is preferred over
   a shared personal account.
4. Set an appropriate Access session duration, such as 24 hours.
5. Copy the application **AUD tag** and the team domain in the form
   `https://<team>.cloudflareaccess.com`.
6. Configure these values on the `logistics-intelligence-api` Worker:

   ```bash
   cd backend
   uv run pywrangler secret put ACCESS_TEAM_DOMAIN
   uv run pywrangler secret put ACCESS_AUD
   ```

7. Apply the D1 migration and deploy the Worker:

   ```bash
   npx wrangler d1 migrations apply logistics-intelligence-history --remote
   uv run pywrangler deploy
   ```

8. Build and deploy Pages from `frontend/` without `VITE_API_URL`. Production API
   requests must remain same-origin so the Pages Function can forward the Access
   assertion:

   ```bash
   cd frontend
   VITE_API_URL= npm run build
   npx wrangler pages deploy dist \
     --project-name logistics-intelligence-dashboard
   ```

9. In a private browser window, verify that the Pages URL redirects to Access,
   that the provided reviewer identity can log in, and that an unapproved
   identity is rejected.

## Reviewer handoff

Provide these items outside the public repository:

- Application URL
- Dedicated reviewer username/email
- Password or identity-provider instructions
- Expiry date for the reviewer access

Revoke the reviewer identity or remove the Access policy after the evaluation
window.
