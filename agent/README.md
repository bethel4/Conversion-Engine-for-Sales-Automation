# Conversion Engine Agent

For the full system overview (architecture + enrichment pipeline + briefs), see `README.md` in the repo root.

## SMS handler

This service now exposes an SMS flow for Africa's Talking:

- Outbound SMS: `POST /sms/send`
- Inbound SMS replies webhook: `POST /sms/webhook`

Use this webhook URL in Africa's Talking:

- `https://conversion-engine-for-sales-automation.onrender.com/sms/webhook`

Required environment variables:

- `AFRICASTALKING_USERNAME`
- `AFRICASTALKING_API_KEY`
- `AFRICASTALKING_SENDER_ID` optional

The SMS send route is intentionally gated for warm leads only. Requests must include
`prior_email_reply_received=true`; otherwise the API returns `403` and does not send SMS.
