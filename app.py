from flask import Flask, request, send_file, render_template_string, abort
import os
import json
import io
import segno
from PIL import Image

app = Flask(__name__)
BASE_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(BASE_DIR, 'config.json')


def load_config():
    if not os.path.exists(CONFIG_PATH):
        return None
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def make_vcard(cfg: dict) -> str:
    name = cfg.get('name', '')
    fn = name
    parts = name.split()
    if len(parts) >= 2:
        first = parts[0]
        last = ' '.join(parts[1:])
    else:
        first = name
        last = ''

    lines = [
        'BEGIN:VCARD',
        'VERSION:3.0',
        f'N:{last};{first};;;',
        f'FN:{fn}',
    ]

    work = cfg.get('work_phone')
    mobile = cfg.get('mobile')
    email = cfg.get('email')
    website = cfg.get('website')

    if work:
        lines.append(f'TEL;WORK;VOICE:{work}')
    if mobile:
        lines.append(f'TEL;CELL:{mobile}')
    if email:
        lines.append(f'EMAIL;TYPE=INTERNET;TYPE=WORK:{email}')
    if website:
        lines.append(f'URL:{website}')

    lines.append('END:VCARD')
    return '\r\n'.join(lines)


HTML = '''
<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <title>vCard QR Generator</title>
  </head>
  <body>
    <h2>Upload Profile Picture (logo)</h2>
    <form method="post" enctype="multipart/form-data">
      <input type="file" name="logo" accept="image/*" required>
      <button type="submit">Generate QR</button>
    </form>
    {% if error %}
      <p style="color:crimson">{{ error }}</p>
    {% endif %}
  </body>
</html>
'''


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'GET':
        return render_template_string(HTML)

    # POST
    cfg = load_config()
    if not cfg:
        return render_template_string(HTML, error='Missing config.json in app directory.')

    try:
        vcard = make_vcard(cfg)
        qr = segno.make(vcard, error='H')
        buf = io.BytesIO()
        qr.save(buf, kind='png', scale=10)
        buf.seek(0)
        qr_img = Image.open(buf).convert('RGBA')
    except Exception as e:
        return render_template_string(HTML, error=f'QR generation error: {e}')

    logo_file = request.files.get('logo')
    if logo_file and logo_file.filename:
        try:
            logo = Image.open(logo_file.stream).convert('RGBA')
            qr_img = qr_img.convert('RGBA')

            # Make logo cover up to ~25% of QR area (i.e., ~50% width)
            max_logo_dim = int(min(qr_img.size) * 0.5)
            logo.thumbnail((max_logo_dim, max_logo_dim), Image.LANCZOS)

            pos = ((qr_img.width - logo.width) // 2, (qr_img.height - logo.height) // 2)
            qr_img.paste(logo, pos, mask=logo)
        except Exception:
            # If logo processing fails, continue without logo
            pass

    buf = io.BytesIO()
    qr_img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png', download_name='vcard_qr.png')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
