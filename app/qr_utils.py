import io
import base64
import qrcode
from qrcode.image.pil import PilImage
from app.config import BASE_URL


def generate_qr_base64(token: str) -> str:
    """Generate a QR code for the given token and return it as a base64 PNG string."""
    # The QR code encodes a URL that the admin scanner will read
    url = f"{BASE_URL}/admin/scan/{token}"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img: PilImage = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode("utf-8")
