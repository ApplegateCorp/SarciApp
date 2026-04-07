import resend
from app.config import RESEND_API_KEY, EMAIL_FROM, BASE_URL


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
        <h2 style="color: #2C2C2C; margin: 0 0 8px; font-size: 18px;">Réinitialiser votre mot de passe</h2>
        <p style="color: #6B6B6B;">Bonjour <strong style="color:#2C2C2C;">{name}</strong>,</p>
        <p style="color: #6B6B6B;">
          Cliquez sur le bouton ci-dessous pour définir un nouveau mot de passe.
          Ce lien est valable <strong>15 minutes</strong>.
        </p>

        <div style="text-align: center; margin: 28px 0;">
          <a href="{reset_link}" style="
            background: #3D6B4F; color: white; padding: 14px 28px;
            border-radius: 50px; text-decoration: none; font-weight: 500;
            font-size: 14px; display: inline-block;
          ">Réinitialiser mon mot de passe</a>
        </div>

        <p style="color: #999; font-size: 12px;">
          Si vous n'avez pas demandé cette réinitialisation, ignorez cet email.
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
        "subject": "Réinitialisation de votre mot de passe",
        "html": html,
    })


def send_welcome_email(to_email: str, name: str, has_account: bool):
    """
    Send a welcome email after HelloAsso ticket purchase.
    Explains the bar platform and invites the user to create an account
    (or log in if they already have one).
    """
    if not RESEND_API_KEY or RESEND_API_KEY == "re_REPLACE_ME":
        return

    resend.api_key = RESEND_API_KEY

    if has_account:
        cta_text = "Accéder à mon compte"
        cta_url = f"{BASE_URL}/ticket"
        account_msg = "Ton compte est déjà actif et ton billet a été associé automatiquement."
    else:
        cta_text = "Créer mon compte"
        cta_url = f"{BASE_URL}/register"
        account_msg = (
            "Crée ton compte sur la plateforme avec <strong>le même email que celui "
            "utilisé sur HelloAsso</strong> pour retrouver ton billet et activer "
            "ton QR code."
        )

    html = f"""
    <div style="font-family: 'Roboto', -apple-system, sans-serif; max-width: 600px; margin: auto; padding: 24px;">
      <div style="background: #2C2C2C; padding: 24px; border-radius: 12px 12px 0 0; text-align: center;">
        <h1 style="color: #fff; margin: 0; font-size: 22px; letter-spacing: 0.04em; text-transform: uppercase;">Repeat the Monkey #3</h1>
        <p style="color: rgba(255,255,255,0.5); margin: 4px 0 0; font-size: 12px;">3 - 4 - 5 Juillet 2026</p>
      </div>
      <div style="background: #ffffff; padding: 28px; border: 1px solid #D1D9C8; border-top: none; border-radius: 0 0 12px 12px;">
        <h2 style="color: #2C2C2C; margin: 0 0 8px; font-size: 18px;">Bienvenue au festival !</h2>
        <p style="color: #6B6B6B;">Bonjour <strong style="color:#2C2C2C;">{name}</strong>,</p>
        <p style="color: #6B6B6B;">
          Merci pour ton achat sur HelloAsso ! Ton billet pour
          <strong style="color:#2C2C2C;">Repeat the Monkey #3</strong> est confirmé.
        </p>

        <p style="color: #6B6B6B;">{account_msg}</p>

        <div style="text-align: center; margin: 28px 0;">
          <a href="{cta_url}" style="
            background: #3D6B4F; color: white; padding: 14px 28px;
            border-radius: 50px; text-decoration: none; font-weight: 500;
            font-size: 14px; display: inline-block;
          ">{cta_text}</a>
        </div>

        <div style="background: #EEF2E8; border: 1px solid #D1D9C8; border-radius: 10px; padding: 16px; margin-top: 20px;">
          <p style="color: #2C2C2C; font-weight: 500; margin: 0 0 6px; font-size: 14px;">
            Comment ça marche ?
          </p>
          <p style="color: #6B6B6B; margin: 0 0 10px; font-size: 13px;">
            Le festival utilise une plateforme en ligne pour le bar :
          </p>
          <ol style="color: #6B6B6B; font-size: 13px; margin: 0; padding-left: 18px; line-height: 1.8;">
            <li>Crée ton compte sur <a href="{BASE_URL}" style="color: #3D6B4F;">{BASE_URL.replace('https://', '')}</a></li>
            <li>Ton QR code personnel est généré automatiquement</li>
            <li>Recharge ton solde bar en ligne (avant ou pendant le festival)</li>
            <li>Au bar, le barman scanne ton QR code pour déduire tes consos</li>
          </ol>
        </div>

        <div style="background: #EEF2E8; border: 1px solid #D1D9C8; border-radius: 10px; padding: 16px; margin-top: 12px;">
          <p style="color: #2C2C2C; font-weight: 500; margin: 0 0 6px; font-size: 14px;">
            Infos pratiques
          </p>
          <p style="color: #6B6B6B; margin: 0; font-size: 13px;">
            3, 4 et 5 juillet 2026<br/>
            <a href="https://maps.app.goo.gl/Bnioi1dDNKMd6aP47" style="color: #3D6B4F;">Le Bangin Châtenoy</a><br/>
            Plus d'infos sur <a href="{BASE_URL}/info" style="color: #3D6B4F;">la page informations pratiques</a>.
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
        "subject": "Bienvenue au Repeat the Monkey #3 !",
        "html": html,
    })
