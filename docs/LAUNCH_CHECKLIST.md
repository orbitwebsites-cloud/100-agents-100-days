# Going live — from repo to first paying customer

Everything below is a one-time setup. Budget ~1 hour.

## 1. Stripe (test mode first)
1. Create a Stripe account → Developers → API keys → copy the **secret key** into `STRIPE_SECRET_KEY`.
2. Create the products and prices (idempotent — safe to re-run):
   ```bash
   python -m hundred.admin stripe-setup
   ```
3. Developers → Webhooks → **Add endpoint** → `https://<your-domain>/stripe/webhook`, events:
   - `checkout.session.completed`
   - `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`,
     `customer.subscription.paused`, `customer.subscription.resumed`
   - `invoice.paid`, `invoice.payment_failed`

   Copy the signing secret into `STRIPE_WEBHOOK_SECRET`.
4. Settings → Billing → **Customer portal**: enable "update payment method", "cancel subscription",
   and "switch plans" (add the All-Access price as an upgrade option).
5. Settings → Billing → **Subscriptions and emails → Manage failed payments**: turn on Smart Retries
   and Stripe's own card-update emails. Our server cuts access on the first failed payment and
   restores it the moment any retry (or a new card) succeeds.
6. Optional: create promotion codes (Products → Coupons) for influencers/launch ("PH50" = 50% off
   first 3 months). Checkout already accepts them.

Test the whole loop with card `4242 4242 4242 4242`, then a decline with `4000 0000 0000 0341`
(attaches fine, fails on the first charge) → watch the key go dark, update the card in `/account`,
watch it come back. Use the Stripe CLI to replay events locally:
`stripe listen --forward-to localhost:8000/stripe/webhook`.

## 2. Email
Email goes through **Brevo**. In Brevo: SMTP & API → API keys → create a key, and store it as the
`BREVO_API_KEY` secret on your host (never commit it or paste it anywhere else). `EMAIL_FROM` must be a
verified Brevo sender; `alex@orbitboyzz.me` already is, so `EMAIL_FROM="Hundred <alex@orbitboyzz.me>"`
works today. Without a key, emails are logged instead of sent (fine for testing, not for launch: the
license key and sign-in codes are emailed).
- Deliverability: in Brevo → Senders, Domains & Dedicated IPs → Domains, authenticate
  `orbitboyzz.me` (Brevo code, DKIM and DMARC records). If the domain's DNS is on Cloudflare, add those
  records in Cloudflare → DNS, with the proxy **off** (grey cloud) for any CNAMEs.
- The Brevo free plan sends 300 emails a day. That covers early launch; move to a paid plan (from
  ~$9/mo) before daily signups plus sign-ins approach it, because a missed sign-in code is a lost customer.
- `RESEND_API_KEY` still works as an alternative and is used only when `BREVO_API_KEY` is blank.

## 2b. Sign-in from AI apps (OAuth)
Customers add just `https://<your-domain>/mcp`; Claude, ChatGPT, Cursor, VS Code and Claude Code
then open your `/connect` page, the customer enters their email, gets a 6-digit code, and is connected.
- `PUBLIC_URL` must be your real **https** domain: it is the OAuth issuer, and apps reject a mismatch.
- Email (step 2) must be live, since the sign-in code is emailed.
- Keys still work everywhere (`?key=`, `/k/<key>/mcp`, `Authorization: Bearer <key>`) for apps
  that can't sign in. Directory listings that need an anonymous endpoint use `/mcp?free=1`.
- Test it: add the URL as a custom connector in Claude, sign in with the email on a test
  subscription, then ask "write a cold email to a VP of operations". It should just work.

## 3. Deploy (Fly.io example; any Docker host with a persistent disk works)
```bash
fly launch --no-deploy            # uses fly.toml
fly volumes create hundred_data --size 1
fly secrets set STRIPE_SECRET_KEY=sk_live_... STRIPE_WEBHOOK_SECRET=whsec_... \
  BREVO_API_KEY=xkeysib-... EMAIL_FROM="Hundred <alex@orbitboyzz.me>" PUBLIC_URL=https://yourdomain.com
fly deploy
```
Point your domain at it, then update `PUBLIC_URL` and the Stripe webhook URL.

## 4. Safety net
Run the reconciler daily (Fly machines cron, GitHub Action, or any scheduler). It re-pulls every
subscription from Stripe and fixes anything a missed webhook left stale:
```bash
python -m hundred.admin reconcile
```
Back up `/data/hundred.db` daily (e.g. `sqlite3 /data/hundred.db ".backup /data/backup.db"` + copy off-box).

## 5. Before announcing
- [ ] `python -m pytest -q` is green
- [ ] Buy your own All-Access in live mode with a real card, connect it to Claude and ChatGPT, refund yourself
- [ ] Issue comp keys for launch partners: `python -m hundred.admin issue-key --email x@y.com --plan all --note "launch partner"`
- [ ] Submit to MCP directories (see `marketing/DIRECTORY_SUBMISSIONS.md`)
