import io
import base64
import tempfile
import resend
from fpdf import FPDF
from app.config import RESEND_API_KEY, EMAIL_FROM, BASE_URL


def _generate_ticket_pdf(name: str, email: str, qr_base64: str) -> bytes:
    """Generate a beautiful PDF ticket with QR code."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=False)

    # ── Background color (cream) ──
    pdf.set_fill_color(245, 239, 224)
    pdf.rect(0, 0, 210, 297, "F")

    # ── Header bar (brown) ──
    pdf.set_fill_color(46, 26, 14)
    pdf.rect(0, 0, 210, 50, "F")

    # ── Title ──
    pdf.set_y(12)
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(245, 200, 66)  # yellow
    pdf.cell(0, 14, "SARCITOPIA", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(245, 239, 224)
    pdf.cell(0, 8, "La Prairie des Merveilles", align="C", new_x="LMARGIN", new_y="NEXT")

    # ── Ticket info section ──
    pdf.set_y(62)
    pdf.set_text_color(46, 26, 14)

    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, "Billet d'entree", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(8)

    # Dashed line
    pdf.set_draw_color(217, 205, 180)
    pdf.set_line_width(0.5)
    pdf.dashed_line(30, pdf.get_y(), 180, pdf.get_y(), 4, 3)
    pdf.ln(8)

    # Attendee info
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(122, 96, 69)
    pdf.cell(0, 7, "NOM", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(46, 26, 14)
    pdf.cell(0, 10, name, align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(4)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(122, 96, 69)
    pdf.cell(0, 7, "EMAIL", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(46, 26, 14)
    pdf.cell(0, 8, email, align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(10)

    # Dashed line
    pdf.dashed_line(30, pdf.get_y(), 180, pdf.get_y(), 4, 3)
    pdf.ln(10)

    # ── QR Code ──
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(122, 96, 69)
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
    pdf.set_text_color(122, 96, 69)
    pdf.cell(0, 5, "Ce billet est personnel et non-transferable.", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(12)

    # ── Info box ──
    pdf.set_fill_color(255, 248, 238)
    pdf.set_draw_color(217, 205, 180)
    box_y = pdf.get_y()
    pdf.rect(25, box_y, 160, 32, "DF")
    pdf.set_xy(30, box_y + 4)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(46, 26, 14)
    pdf.cell(150, 5, "Compte bar prepaye", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(30)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(122, 96, 69)
    pdf.multi_cell(150, 4,
        "Rechargez votre compte bar en ligne avant ou pendant le festival.\n"
        f"Connectez-vous sur {BASE_URL}/wallet pour recharger."
    )

    # ── Footer bar ──
    pdf.set_fill_color(46, 26, 14)
    pdf.rect(0, 275, 210, 22, "F")
    pdf.set_y(279)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(245, 239, 224)
    pdf.cell(0, 5, f"SARCITOPIA  |  {BASE_URL}", align="C")

    # Clean up temp file
    import os
    try:
        os.unlink(tmp_path)
    except OSError:
        pass

    return pdf.output()


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
    <div style="font-family: -apple-system, sans-serif; max-width: 600px; margin: auto; padding: 24px;">
      <div style="background: #2E1A0E; padding: 24px; border-radius: 12px 12px 0 0; text-align: center;">
        <h1 style="color: #F5C842; margin: 0; font-size: 28px;">SARCITOPIA</h1>
        <p style="color: rgba(245,239,224,0.6); margin: 4px 0 0; font-size: 13px;">La Prairie des Merveilles</p>
      </div>
      <div style="background: #fff8ee; padding: 28px; border: 1px solid #d9cdb4; border-top: none; border-radius: 0 0 12px 12px;">
        <h2 style="color: #2E1A0E; margin: 0 0 8px;">Ton billet est confirm\u00e9 !</h2>
        <p style="color: #7a6045;">Bonjour <strong>{name}</strong>,</p>
        <p style="color: #7a6045;">
          Ton billet pour Sarcitopia est en pi\u00e8ce jointe (PDF).
          Pr\u00e9sente le QR code \u00e0 l'entr\u00e9e du festival.
        </p>

        <div style="text-align: center; margin: 28px 0;">
          <a href="{ticket_url}" style="
            background: #F4632A; color: white; padding: 14px 28px;
            border-radius: 50px; text-decoration: none; font-weight: bold;
            font-size: 15px; display: inline-block;
          ">Voir mon billet en ligne \u2192</a>
        </div>

        <div style="background: #F5EFE0; border: 1px solid #d9cdb4; border-radius: 10px; padding: 16px; margin-top: 20px;">
          <p style="color: #2E1A0E; font-weight: bold; margin: 0 0 6px; font-size: 14px;">
            \U0001f37a Compte bar pr\u00e9pay\u00e9
          </p>
          <p style="color: #7a6045; margin: 0; font-size: 13px;">
            Recharge ton compte bar en ligne pour payer tes consos au festival !
            <a href="{BASE_URL}/wallet" style="color: #F4632A;">Recharger maintenant \u2192</a>
          </p>
        </div>
      </div>
      <p style="color: #999; font-size: 12px; text-align: center; margin-top: 16px;">
        Sarcitopia &mdash; {BASE_URL}
      </p>
    </div>
    """

    resend.Emails.send({
        "from": EMAIL_FROM,
        "to": to_email,
        "subject": "\U0001f389 Ton billet Sarcitopia est confirm\u00e9 !",
        "html": html,
        "attachments": [
            {
                "filename": "billet-sarcitopia.pdf",
                "content": pdf_b64,
                "content_type": "application/pdf",
            }
        ],
    })
