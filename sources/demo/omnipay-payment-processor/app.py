"""Payment processor service."""

import os
from flask import Flask, request, jsonify
import stripe
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

stripe.api_key = os.getenv("STRIPE_API_KEY")
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "service": "payment-processor"})


@app.route("/api/v1/payments/create-intent", methods=["POST"])
def create_payment_intent():
    """Create a Stripe payment intent."""
    data = request.get_json() or {}
    amount = data.get("amount", 0)
    currency = data.get("currency", "usd")

    try:
        intent = stripe.PaymentIntent.create(
            amount=int(amount * 100),  # Convert to cents
            currency=currency,
            automatic_payment_methods={"enabled": True},
        )
        return jsonify({
            "client_secret": intent.client_secret,
            "payment_intent_id": intent.id,
        })
    except stripe.error.StripeError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/v1/payments/confirm", methods=["POST"])
def confirm_payment():
    """Confirm a payment intent."""
    data = request.get_json() or {}
    payment_intent_id = data.get("payment_intent_id")

    try:
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        return jsonify({
            "status": intent.status,
            "amount": intent.amount,
        })
    except stripe.error.StripeError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/v1/payments/webhook", methods=["POST"])
def webhook():
    """Handle Stripe webhooks."""
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.getenv("STRIPE_WEBHOOK_SECRET")
        )
    except stripe.error.SignatureVerificationError:
        return "Signature verification failed", 400

    # Handle the event
    if event["type"] == "payment_intent.succeeded":
        print(f"Payment succeeded: {event['data']['object']['id']}")
    elif event["type"] == "payment_intent.payment_failed":
        print(f"Payment failed: {event['data']['object']['id']}")

    return jsonify({"received": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
