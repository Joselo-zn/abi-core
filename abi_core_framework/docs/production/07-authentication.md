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
tables — plus `invites`, `waiting_list` and `data_keys`) is created on first
use: at start-up the UI creates only the tables and columns that are missing.
No migration step. If the UI connects with a role that can't create them —
see [a least-privilege role](#encrypted-data-and-a-least-privilege-database) —
the error lists what's missing, for the database owner to create.

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

## Encrypted data and a least-privilege database

Once conversations are stored, a copy of the database is a copy of everything your users wrote. The UI encrypts their content before it reaches Postgres, so a leaked dump or an over-curious query shows ciphertext.

**What's encrypted** (AES-256-GCM): messages, conversation titles, feedback comments, attachment names and user metadata. Attachments are encrypted in the bucket too; the UI serves them decrypted, only to their owner, from `/abi-ui/files/...` — anyone else gets a 404.

**Keys.** Each user has their own data key, stored in the `data_keys` table wrapped by a key-encryption key (KEK) you provide:

| Variable | Use |
|---|---|
| `ABI_UI_KMS_KEY` | A Cloud KMS key as the KEK: `projects/<project>/locations/<region>/keyRings/<ring>/cryptoKeys/<key>`. Install `abi-core-ai[ui,gcp]`; the UI's service account needs `roles/cloudkms.cryptoKeyEncrypterDecrypter` on that key |
| `ABI_UI_LOCAL_KEK` | A local KEK, for development: 32 random bytes, base64 |
| `ABI_UI_IDENTITY_KEY` | A secret for the HMAC of users' emails |

```bash
python -c "import base64, os; print(base64.b64encode(os.urandom(32)).decode())"   # a local KEK
```

With neither KEK set, the UI stores everything in clear and logs a warning at start-up — fine on your laptop, never with real users. Rows written before you turned encryption on stay readable.

**Destroying a user's data key makes all their data unreadable** — every message, title and file — without touching a row. That's how you honor a deletion request when backups still hold the rows.

**No emails in clear.** With `ABI_UI_IDENTITY_KEY` set, users are looked up by an HMAC of their email, so the address itself isn't stored; existing users are migrated on their next login. Keep the secret stable: changing it makes every user a stranger.

**A least-privilege role.** Deleting a conversation or removing a 👍/👎 hides the row instead of deleting it. So the UI's database role needs no `CREATE` and no `DELETE`:

```sql
GRANT USAGE ON SCHEMA public TO chatui;
GRANT SELECT, INSERT, UPDATE ON users, threads, steps, feedbacks, elements,
      invites, waiting_list, data_keys TO chatui;
```

Create the tables once with the owner — or let the UI create them on a first start with an owner role — and run the UI with the restricted one from then on.

**Search** over conversations keeps working: it filters in the application, on the decrypted text.

## Without any of this

Leave `OAUTH_GOOGLE_CLIENT_ID` unset and the UI behaves exactly as before —
anonymous sessions, no persistence, nothing in this page applies. Turning
auth on and off is a config-only change; no code to revert.

## Next step

👉 [Code Execution Sandbox](08-sandbox.md)
