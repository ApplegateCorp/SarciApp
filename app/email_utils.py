import resend
from app.config import RESEND_API_KEY, EMAIL_FROM, BASE_URL


def send_ticket_email(to_email: str, name: str, token: str, qr_base64: str):
    """Send the festival ticket with QR code to the attendee."""
    resend.api_key = RESEND_API_KEY
    ticket_url = f"{BASE_URL}/ticket"

    html = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: auto; padding: 24px;">
      <h1 style="color: #1a1a2e;">🎉 Your festival ticket</h1>
      <p>Bonjour <strong>{name}</strong>,</p>
      <p>Your ticket for the festival is confirmed. Show the QR code below at the entrance.</p>

      <div style="text-align: center; margin: 32px 0;">
        <img src="data:image/png;base64,{qr_base64}" alt="QR Code" width="250" />
      </div>

      <p style="text-align: center;">
        <a href="{ticket_url}" style="
          background: #e94560;
          color: white;
          padding: 12px 24px;
          border-radius: 8px;
          text-decoration: none;
          font-weight: bold;
        ">View my ticket online</a>
      </p>

      <hr style="margin: 32px 0; border: none; border-top: 1px solid #eee;" />
      <p style="color: #888; font-size: 13px;">
        You can also log in at {ticket_url} to access your ticket and recharge your bar account.
      </p>
    </div>
    """

    resend.Emails.send({
        "from": EMAIL_FROM,
        "to": to_email,
        "subject": "🎉 Your festival ticket",
        "html": html,
    })
