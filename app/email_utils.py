import io
import base64
import tempfile
import resend
from fpdf import FPDF
from app.config import RESEND_API_KEY, EMAIL_FROM, BASE_URL


def _generate_ticket_pdf(name: str, email: str, qr_base64: str) -> bytes:
    """Generate a PDF ticket with QR code."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=False)

    # ── Background color (light green) ──
    pdf.set_fill_color(238, 242, 232)
    pdf.rect(0, 0, 210, 297, "F")

    # ── Header bar (charcoal) ──
    pdf.set_fill_color(44, 44, 44)
    pdf.rect(0, 0, 210, 50, "F")

    # ── Title ──
    pdf.set_y(10)
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 12, "REPEAT THE MONKEY #3", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(200, 200, 200)
    pdf.cell(0, 7, "3 - 4 - 5 Juillet 2026", align="C", new_x="LMARGIN", new_y="NEXT")

    # ── Ticket info section ──
    pdf.set_y(62)
    pdf.set_text_color(44, 44, 44)

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 12, "Billet d'entree", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(8)

    # Dashed line
    pdf.set_draw_color(209, 217, 200)
    pdf.set_line_width(0.5)
    pdf.dashed_line(30, pdf.get_y(), 180, pdf.get_y(), 4, 3)
    pdf.ln(8)

    # Attendee info
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(107, 107, 107)
    pdf.cell(0, 7, "NOM", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(44, 44, 44)
    pdf.cell(0, 10, name, align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(4)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(107, 107, 107)
    pdf.cell(0, 7, "EMAIL", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(44, 44, 44)
    pdf.cell(0, 8, email, align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(10)

    # Dashed line
    pdf.dashed_line(30, pdf.get_y(), 180, pdf.get_y(), 4, 3)
    pdf.ln(10)

    # ── QR Code ──
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(107, 107, 107)
    pdf.cell(0, 6, "PRESENTEZ CE QR CODE A L'ENTREE", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    # Decode QR base64 to temp file
    qr_bytes = base64.b64decode(qr_base64)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(qr_bytes)
        tmp_path = tmp.name

    # Center QR code (60mm wide)
    qr_x = (210 - 60) / 2
    pdf.image(tmp_path, x=qr_x, y=pdf.get_y(), w=60)
    pdf.set_y(pdf.get_y() + 65)

    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(107, 107, 107)
    pdf.cell(0, 5, "Ce billet est personnel et non-transferable.", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(12)

    # ── Info box ──
    pdf.set_fill_color(255, 255, 255)
    pdf.set_draw_color(209, 217, 200)
    box_y = pdf.get_y()
    pdf.rect(25, box_y, 160, 32, "DF")
    pdf.set_xy(30, box_y + 4)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(44, 44, 44)
    pdf.cell(150, 5, "Compte bar prepaye", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(30)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(107, 107, 107)
    pdf.multi_cell(150, 4,
        "Rechargez votre compte bar en ligne avant ou pendant le festival.\n"
        f"Connectez-vous sur {BASE_URL}/wallet pour recharger."
    )

    # ── Footer bar ──
    pdf.set_fill_color(44, 44, 44)
    pdf.rect(0, 275, 210, 22, "F")
    pdf.set_y(279)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(200, 200, 200)
    pdf.cell(0, 5, f"REPEAT THE MONKEY #3  |  {BASE_URL}", align="C")

    # Clean up temp file
    import os
    try:
        os.unlink(tmp_path)
    except OSError:
        pass

    return pdf.output()


def send_reset_email(to_email: str, name: str, reset_link: str):
    """Send a password reset email."""
    if not RESEND_API_KEY or RESEND_API_KEY == "re_REPLACE_ME":
        return

    resend.api_key = RESEND_API_KEY

    html = f"""
    <div style="font-family: 'Roboto', -apple-system, sans-serif; max-width: 600px; margin: auto; padding: 24px;">
      <div style="background: #2C2C2C; padding: 24px; border-radius: 12px 12px 0 0; text-align: center;">
        <h1 style="color: #fff; margin: 0; font-size: 22px; letter-spacing: 0.04em; text-transform: uppercase;">Repeat the Monkey #3</h1>
        <p style="color: rgba(255,255,255,0.5); margin: 4px 0 0; font-size: 12px;">3 - 4 - 5 Juillet 2026</p>
      </div>
      <div style="background: #ffffff; padding: 28px; border: 1px solid #D1D9C8; border-top: none; border-radius: 0 0 12px 12px;">
        <h2 style="color: #2C2C2C; margin: 0 0 8px; font-size: 18px;">Reinitialiser votre mot de passe</h2>
        <p style="color: #6B6B6B;">Bonjour <strong style="color:#2C2C2C;">{name}</strong>,</p>
        <p style="color: #6B6B6B;">
          Cliquez sur le bouton ci-dessous pour definir un nouveau mot de passe.
          Ce lien est valable <strong>15 minutes</strong>.
        </p>

        <div style="text-align: center; margin: 28px 0;">
          <a href="{reset_link}" style="
            background: #3D6B4F; color: white; padding: 14px 28px;
            border-radius: 50px; text-decoration: none; font-weight: 500;
            font-size: 14px; display: inline-block;
          ">Reinitialiser mon mot de passe</a>
        </div>

        <p style="color: #999; font-size: 12px;">
          Si vous n'avez pas demande cette reinitialisation, ignorez cet email.
        </p>
      </div>
      <p style="color: #999; font-size: 11px; text-align: center; margin-top: 16px;">
        Repeat the Monkey #3 &mdash; {BASE_URL}
      </p>
    </div>
    """

    resend.Emails.send({
        "from": EMAIL_FROM,
        "to": to_email,
        "subject": "Reinitialisation de votre mot de passe",
        "html": html,
    })


def send_ticket_email(to_email: str, name: str, token: str, qr_base64: str):
    """Send the festival ticket with QR code as PDF attachment."""
    if not RESEND_API_KEY or RESEND_API_KEY == "re_REPLACE_ME":
        return  # Skip if not configured

    resend.api_key = RESEND_API_KEY
    ticket_url = f"{BASE_URL}/ticket"

    # Generate PDF
    pdf_bytes = _generate_ticket_pdf(name, to_email, qr_base64)
    pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")

    html = f"""
    <div style="font-family: 'Roboto', -apple-system, sans-serif; max-width: 600px; margin: auto; padding: 24px;">
      <div style="background: #2C2C2C; padding: 24px; border-radius: 12px 12px 0 0; text-align: center;">
        <h1 style="color: #fff; margin: 0; font-size: 22px; letter-spacing: 0.04em; text-transform: uppercase;">Repeat the Monkey #3</h1>
        <p style="color: rgba(255,255,255,0.5); margin: 4px 0 0; font-size: 12px;">3 - 4 - 5 Juillet 2026</p>
      </div>
      <div style="background: #ffffff; padding: 28px; border: 1px solid #D1D9C8; border-top: none; border-radius: 0 0 12px 12px;">
        <h2 style="color: #2C2C2C; margin: 0 0 8px; font-size: 18px;">Ton billet est confirme</h2>
        <p style="color: #6B6B6B;">Bonjour <strong style="color:#2C2C2C;">{name}</strong>,</p>
        <p style="color: #6B6B6B;">
          Ton billet pour Repeat the Monkey #3 est en piece jointe (PDF).
          Presente le QR code a l'entree du festival.
        </p>

        <div style="text-align: center; margin: 28px 0;">
          <a href="{ticket_url}" style="
            background: #3D6B4F; color: white; padding: 14px 28px;
            border-radius: 50px; text-decoration: none; font-weight: 500;
            font-size: 14px; display: inline-block;
          ">Voir mon billet en ligne</a>
        </div>

        <div style="background: #EEF2E8; border: 1px solid #D1D9C8; border-radius: 10px; padding: 16px; margin-top: 20px;">
          <p style="color: #2C2C2C; font-weight: 500; margin: 0 0 6px; font-size: 14px;">
            Compte bar prepaye
          </p>
          <p style="color: #6B6B6B; margin: 0; font-size: 13px;">
            Recharge ton compte bar en ligne pour payer tes consos au festival.
            <a href="{BASE_URL}/wallet" style="color: #3D6B4F;">Recharger maintenant</a>
          </p>
        </div>
      </div>
      <p style="color: #999; font-size: 11px; text-align: center; margin-top: 16px;">
        Repeat the Monkey #3 &mdash; {BASE_URL}
      </p>
    </div>
    """

    resend.Emails.send({
        "from": EMAIL_FROM,
        "to": to_email,
        "subject": "Ton billet Repeat the Monkey #3 est confirme",
        "html": html,
        "attachments": [
            {
                "filename": "billet-repeat-the-monkey.pdf",
                "content": pdf_b64,
                "content_type": "application/pdf",
            }
        ],
    })
