import pytest
from decimal import Decimal
from stripe_service.stripe_payment import create_stripe_session

from config import get_settings


@pytest.mark.integration
def test_create_stripe_session():
    settings = get_settings()
    message = "ok"
    total_amount=Decimal(5)
    order_id = 1
    stripe_session = create_stripe_session(
        total_amount=total_amount,
        titles="DieHard",
        message=message,
        order_id=order_id,
    )
    assert stripe_session is not None
    assert stripe_session.url is not None
    assert stripe_session.id is not None
    assert stripe_session.url.startswith("https://checkout.stripe.com/")
    assert stripe_session.id.startswith("cs_test")
    assert stripe_session.object == "checkout.session"
    assert stripe_session.mode == "payment"
    assert stripe_session.success_url == settings.PAYMENT_SUCCESS_URL + f"{order_id}/"
    assert stripe_session.cancel_url == settings.PAYMENT_CANCEL_URL + f"{order_id}/"
    assert stripe_session.custom_text.submit["message"] == message
    assert stripe_session.amount_total == total_amount * 100