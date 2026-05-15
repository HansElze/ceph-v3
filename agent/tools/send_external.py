def send_external(recipient: str, subject: str, body: str) -> dict:
    """Send an email or external message.

    Use when the user asks to notify someone or send communication outside
    the agent — for example, emailing a report, alerting a contact, or
    forwarding a result to an external address.

    Args:
        recipient: Email address or identifier of the intended recipient.
        subject:   Subject line or brief description of the message.
        body:      Full message body to send.

    Returns:
        dict with keys:
            status:     "sent" on success, "blocked" if intercepted
            recipient:  Echo of the recipient argument
            message_id: Stub identifier for the sent message
    """
    # Stub implementation — no real send. Exists to demonstrate constitutional blocking.
    print(f"[send_external STUB] To: {recipient} | Subject: {subject}")
    return {"status": "sent", "recipient": recipient, "message_id": "stub-001"}
