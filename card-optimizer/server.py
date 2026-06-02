#!/usr/bin/env python3
"""Card Optimizer — serves the app and proxies Claude API calls for merchant categorization."""
import datetime
import json
import os
import re
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler

# Change to the directory containing this script so static files are served correctly.
os.chdir(os.path.dirname(os.path.abspath(__file__)))


def load_dotenv():
    """Load key=value pairs from .env into os.environ (no extra dependencies)."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if not os.path.exists(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value

load_dotenv()


class CardOptimizerHandler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/api/claude':
            self._handle_claude()
        elif self.path == '/api/refresh-card-data':
            self._handle_refresh_card_data()
        else:
            self.send_response(404)
            self.end_headers()

    def _get_anthropic_client(self):
        try:
            import anthropic
        except ImportError:
            self._error(500, 'anthropic package not installed. Run: pip install anthropic')
            return None
        if not os.environ.get('ANTHROPIC_API_KEY'):
            self._error(500, 'ANTHROPIC_API_KEY not set.')
            return None
        return anthropic.Anthropic()

    def _handle_claude(self):
        client = self._get_anthropic_client()
        if not client:
            return
        length = int(self.headers.get('Content-Length', 0))
        try:
            body = json.loads(self.rfile.read(length))
        except Exception:
            self._error(400, 'Invalid JSON body')
            return
        try:
            msg = client.messages.create(
                model='claude-haiku-4-5-20251001',
                max_tokens=2048,
                messages=body.get('messages', []),
            )
            text = msg.content[0].text
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(text.encode('utf-8'))
        except Exception as e:
            self._error(500, str(e))

    def _handle_refresh_card_data(self):
        client = self._get_anthropic_client()
        if not client:
            return
        prompt = """Return ONLY valid JSON (no markdown, no prose) with current rewards data for these two credit cards.

Schema:
{
  "cards": [
    {
      "id": "csp",
      "name": "Chase Sapphire Preferred",
      "issuer": "Chase",
      "currency": "Ultimate Rewards",
      "short": "CSP",
      "annualFee": <number>,
      "cpp": <realistic cents-per-point via transfer partners, number>,
      "base": <catch-all earn multiplier, number>,
      "earn": {
        "<category_id>": <multiplier — only include if above base>
      },
      "perksValue": [
        { "label": "<perk name>", "value": <annual dollar value> }
      ]
    },
    {
      "id": "venx",
      "name": "Capital One Venture X",
      "issuer": "Capital One",
      "currency": "Capital One Miles",
      "short": "Venture X",
      "annualFee": <number>,
      "cpp": <number>,
      "base": <number>,
      "earn": { "<category_id>": <multiplier> },
      "perksValue": [ { "label": "<string>", "value": <number> } ]
    }
  ],
  "transferPartners": {
    "csp": [
      { "name": "<partner>", "type": "<air|hotel>", "ratio": "<e.g. 1:1>", "cpp": <number>, "sweet": "<one-line tip>" }
    ],
    "venx": [ ... same structure ... ]
  }
}

Category IDs for earn rates:
- dining (restaurants, cafes, food delivery)
- groceries (supermarkets)
- travel (airlines, hotels, car rental — general)
- portal_flight (flights booked via the card's own travel portal)
- portal_hotel (hotels booked via the card's own travel portal)
- transit (rideshare, taxis, public transit)
- gas (gas stations)
- streaming (streaming/music subscriptions)
- online (online retail)
- drugstore (pharmacies)
- utilities (phone, internet, recurring bills)

Rules:
- Only include earn categories where the multiplier exceeds the base rate
- For cpp, use realistic transfer-partner-weighted averages, not cash-back value
- For transferPartners, list ALL current partners for each card, sorted by cpp descending
- Return ONLY the JSON object, nothing else"""

        try:
            msg = client.messages.create(
                model='claude-sonnet-4-6',
                max_tokens=4096,
                messages=[{'role': 'user', 'content': prompt}],
            )
            text = msg.content[0].text.strip()
            # Strip markdown fences if present
            text = re.sub(r'^```(?:json)?\s*', '', text)
            text = re.sub(r'\s*```$', '', text).strip()
            # Extract outermost JSON object
            start, end = text.find('{'), text.rfind('}')
            if start >= 0 and end > start:
                text = text[start:end + 1]
            data = json.loads(text)
            # Stamp with server time so the UI can show "last updated"
            data['fetchedAt'] = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
            out = json.dumps(data).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(out)
        except Exception as e:
            self._error(500, str(e))

    def _error(self, code, message):
        self.send_response(code)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(message.encode('utf-8'))

    def end_headers(self):
        # Disable caching for JS/JSX/HTML so edits are always picked up immediately.
        if any(ext in self.path for ext in ('.js', '.jsx', '.html')):
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        super().end_headers()

    def log_message(self, fmt, *args):
        # Only log API calls, not every static file request.
        if self.path == '/api/claude':
            super().log_message(fmt, *args)


if __name__ == '__main__':
    if not os.environ.get('ANTHROPIC_API_KEY'):
        print('⚠  ANTHROPIC_API_KEY not set — AI categorization will use keyword fallback.')
    port = int(os.environ.get('PORT', 3000))
    server = HTTPServer(('localhost', port), CardOptimizerHandler)
    print(f'Card Optimizer → http://localhost:{port}')
    print('Press Ctrl+C to stop.')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')
