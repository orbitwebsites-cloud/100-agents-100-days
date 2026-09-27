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
Create a Resend account, verify your domain, set `RESEND_API_KEY` and `EMAIL_FROM`. Without it
emails are logged instead of sent (fine for testing, not for launch — the key is emailed).

## 3. Deploy (Fly.io example; any Docker host with a persistent disk works)
```bash
fly launch --no-deploy            # uses fly.toml
fly volumes create hundred_data --size 1
fly secrets set STRIPE_SECRET_KEY=sk_live_... STRIPE_WEBHOOK_SECRET=whsec_... \
  RESEND_API_KEY=re_... EMAIL_FROM="Hundred <agents@yourdomain.com>" PUBLIC_URL=https://yourdomain.com
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
