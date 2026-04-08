from __future__ import annotations

import hashlib
import hmac


class TokenHashService:
    def hash_token(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def verify_token(self, *, raw_token: str, token_hash: str) -> bool:
        calculated = self.hash_token(raw_token)
        return hmac.compare_digest(calculated, token_hash)
