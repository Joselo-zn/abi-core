# Authentication (Chainlit UI)

```{note}
**Alpha.** Built for the bundled Chainlit UI (`abi-core ui chainlit` /
`abi_core.ui.chainlit_app`). Env vars and behavior may change between
releases.
```

By default the bundled Chainlit UI runs **anonymous** — no login, no
persisted conversation history, a fresh context on every browser session.
Setting `OAUTH_GOOGLE_CLIENT_ID` turns on Google login, backed by Postgres,
which gets you three things at once: real login, conversations that survive a
page reload or a return visit days later, and an invite-only registration
system so the UI isn't open to anyone with a Google account.

## What gets added

- **Google OAuth login** — via Chainlit's own `@cl.oauth_callback` mechanism.
- **A Postgres data layer** — persists users, threads, and steps. Reloading
  the page (or coming back tomorrow, on any device) restores the
  conversation instead of starting over.
- **Session continuity across logins** — the same bearer token mechanism
  from [Sessions & Multi-turn](../single-agent/07-sessions-multi-turn.md) is
  bridged into the persisted thread, so a returning logged-in user keeps
  their `context_id` (pending plans, clarifications, conversation memory)
  instead of starting a new anonymous session every time.
- **Invite-only registration** — nobody can register without a valid
  invite; the first person to ever register becomes admin automatically.

## Setup

### 1. Google OAuth credentials

Create an OAuth Client ID (Web application) in
[Google Cloud Console → Credentials](https://console.cloud.google.com/apis/credentials).

Add an **Authorized redirect URI** — it must match exactly:

```
<CHAINLIT_URL>/auth/oauth/google/callback
```

For local dev, that's `http://localhost:8500/auth/oauth/google/callback`
(adjust the port to whatever you map the UI to). Add your production URL too
once you have it — Google allows multiple redirect URIs on the same client.

"Authorized JavaScript origins" is **not** needed — Chainlit's OAuth flow is a
server-side redirect (classic Authorization Code flow), not a client-side
JS-initiated one, so Google never validates an origin for it.

### 2. Postgres

A plain Postgres instance — add one to `compose.yaml` if you don't already
have one:

```yaml
services:
  my-app-postgres:
    image: postgres:16
    environment:
      - POSTGRES_USER=abi
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=my_app
    volumes:
      - postgres_data:/var/lib/postgresql/data
```

The schema (users, threads, steps, feedbacks, elements — Chainlit's own
tables — plus `invites` and `waiting_list`) is created automatically on
first use. No migration step.

### 3. Generate the auth secret

Signs session JWTs — required as soon as any auth is configured:

```bash
docker run --rm --entrypoint sh <your-chatui-image> -c "chainlit create-secret"
```

### 4. Wire it up

Put secrets in a local `.env` (gitignored) that `docker compose` loads
automatically — never commit real credentials to `compose.yaml`:

```bash
# .env
POSTGRES_PASSWORD=...
OAUTH_GOOGLE_CLIENT_ID=...
OAUTH_GOOGLE_CLIENT_SECRET=...
CHAINLIT_AUTH_SECRET=...
CHAINLIT_URL=http://localhost:8500
ADMIN_NOTIFICATION_EMAIL=you@example.com
SMTP_HOST=...          # optional — see below
```

```yaml
# compose.yaml
services:
  chatui:
    environment:
      - DATABASE_URL=postgresql+asyncpg://abi:${POSTGRES_PASSWORD}@my-app-postgres:5432/my_app
      - OAUTH_GOOGLE_CLIENT_ID=${OAUTH_GOOGLE_CLIENT_ID}
      - OAUTH_GOOGLE_CLIENT_SECRET=${OAUTH_GOOGLE_CLIENT_SECRET}
      - CHAINLIT_AUTH_SECRET=${CHAINLIT_AUTH_SECRET}
      - CHAINLIT_URL=${CHAINLIT_URL}
      - ARTIFACT_ENDPOINT=http://my-app-minio:9000
      - ARTIFACT_ACCESS_KEY=minioadmin
      - ARTIFACT_SECRET_KEY=minioadmin
      - ADMIN_NOTIFICATION_EMAIL=${ADMIN_NOTIFICATION_EMAIL}
```

See [Environment Variables → Chainlit UI Authentication](../reference/environment-variables.md#chainlit-ui-authentication-oauth--invites)
for the full list, including the optional SMTP block.

## Invite-only registration

Nobody can self-register with just any Google account. The flow:

1. **Bootstrap**: the very first person to ever log in becomes admin
   automatically — no invite needed for that one registration.
2. The admin generates invite links from `/admin/invites` (in the running
   UI) — each link is a single-use token, good for registering with any
   email.
3. Once registered, every user gets **one** invite of their own to hand out
   (`/invites/mine`) — access grows by referral from there, the admin doesn't
   have to invite everyone directly.
4. Someone who tries to log in without an available invite lands on
   `/waiting-list` instead of a generic error — they leave their email, and
   (if SMTP is configured) the admin gets notified.

```{note}
An invite link is generic, not tied to a specific email — whoever completes
Google login through it registers with whatever account they used. There's
no way to restrict a link to one particular person's email; if that matters,
don't share the link beyond the one person it's for.
```

## Without any of this

Leave `OAUTH_GOOGLE_CLIENT_ID` unset and the UI behaves exactly as before —
anonymous sessions, no persistence, nothing in this page applies. Turning
auth on and off is a config-only change; no code to revert.
