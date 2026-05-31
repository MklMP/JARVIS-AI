import json
import hmac
import hashlib
from typing import Dict, Optional
from datetime import datetime
from utils.logger import setup_logger


class WebhookHandler:
    def __init__(self, secret: str = None):
        self.secret = secret or ''
        self.logger = setup_logger("webhook_handler")
        self.recent_signals = []

    def verify_signature(self, payload: bytes, signature: str) -> bool:
        if not self.secret:
            return True
        expected = hmac.new(
            self.secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def process_alert(self, data: dict) -> Optional[Dict]:
        try:
            action = data.get('action', '').lower()
            symbol = data.get('symbol', '')
            price = float(data.get('price', 0))
            confidence = float(data.get('confidence', 0))
            timestamp = data.get('timestamp', str(datetime.now()))

            if not symbol or action not in ('buy', 'sell'):
                self.logger.warning(f"Invalid alert data: {data}")
                return None

            signal = {
                'symbol': symbol,
                'action': action,
                'price': price,
                'confidence': confidence,
                'source': 'tradingview',
                'timestamp': timestamp,
                'received_at': datetime.now().isoformat()
            }

            self.recent_signals.append(signal)
            if len(self.recent_signals) > 100:
                self.recent_signals = self.recent_signals[-100:]

            self.logger.info(f"TV Alert: {action.upper()} {symbol} @ ${price:.2f} (conf: {confidence:.2f})")
            return signal

        except Exception as e:
            self.logger.error(f"Error processing webhook: {e}")
            return None

    def get_recent_signals(self, limit: int = 10) -> list:
        return self.recent_signals[-limit:]
