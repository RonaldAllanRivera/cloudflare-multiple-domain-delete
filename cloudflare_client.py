import time
from typing import Any, Dict, Optional, Tuple

import requests


class CloudflareAPIError(Exception):
    """Raised when Cloudflare API returns a non-success response."""


class CloudflareClient:
    def __init__(
        self,
        api_token: Optional[str] = None,
        email: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: str = "https://api.cloudflare.com/client/v4",
        timeout: int = 30,
        max_retries: int = 5,
    ) -> None:
        self.api_token = api_token
        self.email = email
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

        if not self.api_token and not (self.email and self.api_key):
            raise ValueError(
                "Cloudflare credentials missing. Provide CLOUDFLARE_API_TOKEN or CLOUDFLARE_EMAIL + CLOUDFLARE_API_KEY."
            )

    def _headers(self) -> Dict[str, str]:
        if self.api_token:
            return {
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
            }
        return {
            "X-Auth-Email": self.email or "",
            "X-Auth-Key": self.api_key or "",
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        retry = 0
        backoff = 1.0
        while True:
            resp = requests.request(
                method=method,
                url=url,
                headers=self._headers(),
                params=params,
                json=json,
                timeout=self.timeout,
            )
            # Rate limit handling
            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After")
                wait_s = float(retry_after) if retry_after else backoff
                if retry >= self.max_retries:
                    raise CloudflareAPIError(
                        f"Rate limited and max retries exceeded for {method} {path}"
                    )
                time.sleep(wait_s)
                retry += 1
                backoff = min(backoff * 2, 30)
                continue

            # Other non-success
            if not resp.ok:
                try:
                    data = resp.json()
                except Exception:
                    data = {"errors": [{"message": resp.text}]}
                message = self._format_error_message(data, resp.status_code)
                raise CloudflareAPIError(
                    f"HTTP {resp.status_code} for {method} {path}: {message}"
                )

            return resp.json()

    @staticmethod
    def _format_error_message(data: Dict[str, Any], status: int) -> str:
        # Cloudflare returns errors like {"success": false, "errors": [{"code": 123, "message": "..."}], "messages": []}
        if isinstance(data, dict) and "errors" in data and data["errors"]:
            parts = []
            for err in data["errors"]:
                code = err.get("code")
                msg = err.get("message")
                parts.append(f"{code}: {msg}" if code is not None else f"{msg}")
            return "; ".join(parts)
        # Fallback
        return str(data)

    def get_zone_by_name(self, domain: str) -> Optional[Dict[str, Any]]:
        params = {
            "name": domain.strip().lower(),
            "match": "all",
            "per_page": 50,
        }
        data = self._request("GET", "/zones", params=params)
        results = data.get("result", []) if isinstance(data, dict) else []
        for z in results:
            if z.get("name", "").lower() == domain.strip().lower():
                return z
        return None

    def delete_zone(self, zone_id: str) -> Tuple[bool, str]:
        data = self._request("DELETE", f"/zones/{zone_id}")
        success = bool(data.get("success")) if isinstance(data, dict) else False
        if success:
            return True, "Deleted"
        # In case success is False but no HTTP error thrown, extract reason
        msg = self._format_error_message(data, 200)
        return False, msg
