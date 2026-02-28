from datetime import date
from uuid import UUID
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from typing import Dict, Any, Optional
import logging

from app.services.auth_manager import auth_manager
from app.core.config import settings

logger = logging.getLogger(__name__)

class APIRequestError(Exception):
    pass

class APIHTTPError(APIRequestError):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(message)

class APINetworkError(APIRequestError):
    pass

def serialize_dates(obj: Any) -> Any:
    if isinstance(obj, date):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {key: serialize_dates(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [serialize_dates(item) for item in obj]
    return obj

def retry_api_call():
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException, APINetworkError)),
        reraise=True
    )

class BaseClient:
    def __init__(self, base_url: str, timeout: float = 10.0):
        self.base_url = base_url
        self.timeout = httpx.Timeout(timeout, connect=5.0)
        self.default_headers = {"Content-Type": "application/json"}

    async def _get_headers(self, user_telegram_id: Optional[int] = None) -> Dict[str, str]:
        headers = self.default_headers.copy()
        if user_telegram_id:
            token = await auth_manager.get_token(user_telegram_id)
            if token:
                headers["Authorization"] = f"Bearer {token}"
            else:
                logger.warning(f"NO TOKEN for {user_telegram_id}")
        return headers

class CandidateAPIClient(BaseClient):
    def __init__(self):
        super().__init__(f"{settings.CANDIDATE_SERVICE_URL}/candidates", timeout=15.0)

    @retry_api_call()
    async def register_candidate_profile(self, profile_data: dict) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/"
        payload = serialize_dates(profile_data.copy())
        tg_id = payload.get('telegram_id')
        logger.info(payload)
        headers = await self._get_headers(tg_id)
        logger.info(f"Registering candidate {tg_id} with headers keys: {list(headers.keys())}")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code == 409:
                    logger.info(f"Candidate {tg_id} already exists (409).")
                    return None
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                raise APIHTTPError(e.response.status_code, f"HTTP error: {e.response.text}")
            except httpx.RequestError as e:
                raise APINetworkError(f"Network error: {str(e)}")

    @retry_api_call()
    async def get_candidate_by_telegram_id(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        headers = await self._get_headers(telegram_id)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(f"{self.base_url}/by-telegram/{telegram_id}", headers=headers)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404: return None
                raise APIHTTPError(e.response.status_code, e.response.text)
            except httpx.RequestError as e:
                raise APINetworkError(str(e))

    @retry_api_call()
    async def update_candidate_profile(self, telegram_id: int, profile_data: dict) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/by-telegram/{telegram_id}"
        payload = serialize_dates(profile_data.copy())
        headers = await self._get_headers(telegram_id)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.patch(url, json=payload, headers=headers)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                raise APIHTTPError(e.response.status_code, e.response.text)
            except httpx.RequestError as e:
                raise APINetworkError(str(e))

    @retry_api_call()
    async def replace_resume(self, telegram_id: int, file_id: UUID) -> bool:
        url = f"{self.base_url}/by-telegram/{telegram_id}/resume"
        payload = {"file_id": str(file_id)}
        headers = await self._get_headers(telegram_id)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.put(url, json=payload, headers=headers)
                response.raise_for_status()
                return True
            except httpx.HTTPStatusError as e:
                raise APIHTTPError(e.response.status_code, e.response.text)
            except httpx.RequestError as e:
                raise APINetworkError(str(e))

    @retry_api_call()
    async def replace_avatar(self, telegram_id: int, file_id: UUID) -> bool:
        url = f"{self.base_url}/by-telegram/{telegram_id}/avatar"
        payload = {"file_id": str(file_id)}
        headers = await self._get_headers(telegram_id)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.put(url, json=payload, headers=headers)
                response.raise_for_status()
                return True
            except Exception as e:
                logger.error(f"Avatar replace error: {e}")
                return False

    @retry_api_call()
    async def delete_avatar(self, telegram_id: int) -> bool:
        url = f"{self.base_url}/by-telegram/{telegram_id}/avatar"
        headers = await self._get_headers(telegram_id)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.delete(url, headers=headers)
                if response.status_code == 404: return True 
                response.raise_for_status()
                return True
            except Exception as e:
                logger.error(f"Avatar delete error: {e}")
                return False

    @retry_api_call()
    async def delete_resume(self, telegram_id: int) -> bool:
        url = f"{self.base_url}/by-telegram/{telegram_id}/resume"
        headers = await self._get_headers(telegram_id)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.delete(url, headers=headers)
                if response.status_code == 404: return True
                response.raise_for_status()
                return True
            except Exception as e:
                logger.error(f"Resume delete error: {e}")
                return False

class EmployerAPIClient(BaseClient):
    def __init__(self):
        super().__init__(f"{settings.EMPLOYER_SERVICE_URL}/employers", timeout=20.0)

    @retry_api_call()
    async def get_or_create_employer(self, telegram_id: int, username: str) -> Optional[Dict[str, Any]]:
        payload = {"telegram_id": telegram_id, "contacts": {"telegram": f"@{username}"}}
        headers = await self._get_headers(telegram_id)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(f"{self.base_url}/", json=payload, headers=headers)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"Employer creation error: {e}")
                return None
    
    @retry_api_call()
    async def update_employer_profile(self, employer_id: str, update_data: dict) -> Optional[Dict[str, Any]]:
        """Обновление профиля работодателя (PATCH)."""
        url = f"{self.base_url}/{employer_id}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.patch(url, json=update_data, headers=self.default_headers)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Error updating employer {employer_id}: {e.response.text}")
                raise APIHTTPError(e.response.status_code, e.response.text)
            except httpx.RequestError as e:
                raise APINetworkError(str(e))

    @retry_api_call()
    async def create_search_session(self, employer_id: str, filters: dict) -> Optional[Dict[str, Any]]:
        payload = {"title": f"Search for {filters.get('role', 'candidate')}", "filters": filters}
        payload = serialize_dates(payload)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(f"{self.base_url}/{employer_id}/searches", json=payload, headers=self.default_headers)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"Search session error: {e}")
                return None
    
    @retry_api_call()
    async def get_next_candidate(self, session_id: str) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/searches/{session_id}/next"
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(url, headers=self.default_headers)
                if response.status_code == 404: return None
                response.raise_for_status()
                data = response.json()
                return data.get("candidate")
            except Exception as e:
                logger.error(f"Get next candidate error: {e}")
                raise

    @retry_api_call()
    async def save_decision(self, session_id: str, candidate_id: str, decision: str) -> bool:
        url = f"{self.base_url}/searches/{session_id}/decisions"
        payload = {"candidate_id": candidate_id, "decision": decision}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                await client.post(url, json=payload, headers=self.default_headers)
                return True
            except Exception as e:
                logger.error(f"Decision save error: {e}")
                return False

    @retry_api_call()
    async def request_contacts(self, employer_id: str, candidate_id: str) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/{employer_id}/contact-requests"
        payload = {"candidate_id": candidate_id}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, json=payload, headers=self.default_headers)
                return response.json()
            except Exception as e:
                logger.error(f"Contact request error: {e}")
                return None
    
    @retry_api_call()
    async def respond_to_contact_request(self, request_id: str, granted: bool) -> bool:
        url = f"{self.base_url}/contact-requests/{request_id}"
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                await client.put(url, json={"granted": granted}, headers=self.default_headers)
                return True
            except Exception as e:
                logger.error(f"Respond request error: {e}")
                return False
    
    @retry_api_call()
    async def get_contact_request_details(self, request_id: str) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/contact-requests/{request_id}/details"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url, headers=self.default_headers)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"Error getting request details: {e}")
                return None

class FileAPIClient(BaseClient):
    def __init__(self):
        super().__init__(f"{settings.FILE_SERVICE_URL}/files", timeout=60.0)

    @retry_api_call()
    async def upload_file(
        self, 
        filename: str, 
        file_data: bytes, 
        content_type: str, 
        owner_id: int, 
        file_type: str
    ) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/upload"
        
        data = {"owner_telegram_id": str(owner_id), "file_type": file_type}
        files = {'file': (filename, file_data, content_type)}
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                headers = await self._get_headers(owner_id)
                if "Content-Type" in headers:
                    del headers["Content-Type"]

                response = await client.post(url, data=data, files=files, headers=headers)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"File upload error: {e}")
                return None

    @retry_api_call()
    async def get_download_url_by_file_id(self, file_id: UUID) -> Optional[str]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(f"{self.base_url}/{file_id}/url")
                response.raise_for_status()
                data = response.json()
                return data.get("download_url")
            except Exception as e:
                logger.error(f"Error getting download url for {file_id}: {e}")
                if isinstance(e, httpx.HTTPStatusError):
                    logger.error(f"Response body: {e.response.text}")
                return None

    @retry_api_call()
    async def delete_file(self, file_id: UUID, owner_telegram_id: int) -> bool:
        params = {"owner_telegram_id": owner_telegram_id}
        headers = await self._get_headers(owner_telegram_id)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                await client.delete(f"{self.base_url}/{file_id}", params=params, headers=headers)
                return True
            except Exception:
                return False

class SearchAPIClient(BaseClient):
    def __init__(self):
        super().__init__(f"{settings.SEARCH_SERVICE_URL}/search", timeout=5.0)

    async def trigger_reindex(self, admin_tg_id: int) -> bool:
        headers = await self._get_headers(admin_tg_id)
        url = f"{self.base_url}/index/rebuild"
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.post(url, headers=headers)
                resp.raise_for_status()
                return True
            except Exception as e:
                logger.error(f"Reindex failed: {e}")
                return False

candidate_api_client = CandidateAPIClient()
employer_api_client = EmployerAPIClient()
file_api_client = FileAPIClient()
search_api_client = SearchAPIClient()