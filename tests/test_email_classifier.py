from erp.events.email_classifier import EmailIntent, classify_inbound_email


def test_plain_language_order_request_is_classified_as_customer_order():
    result = classify_inbound_email(
        sender="customer@example.com",
        subject="Order",
        body_text="I would like to order 10 units of Assy Bracket Wings.",
    )

    assert result.intent == EmailIntent.CUSTOMER_ORDER
    assert result.event_type == "erp.crm.inbound_customer_order"

