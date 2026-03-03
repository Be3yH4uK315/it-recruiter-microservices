from datetime import date
from uuid import UUID
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
)
from typing import Dict, Any, Optional
import logging

from app.services.auth_manager import auth_manager
from app.core.config import settings
from app.core.resources import resources

logger = logging.getLogger(__name__)


# ============================================================================
# EXCEPTION CLASSES
# ============================================================================


class APIError(Exception):
    """Base exception for API errors."""

    pass


class APIHTTPError(APIError):
    """HTTP error from API (4xx, 5xx)."""

    def __init__(self, status_code: int, message: str, response_text: str = None):
        self.status_code = status_code
        self.response_text = response_text
        super().__init__(f"HTTP {status_code}: {message}")


class APINetworkError(APIError):
    """Network error (timeout, connection refused)."""

    pass


# ============================================================================
# RETRY LOGIC
# ============================================================================


def is_retriable_error(exception: Exception) -> bool:
    """Determines if a request should be retried."""
    if isinstance(exception, (httpx.RequestError, httpx.TimeoutException)):
        return True

    if isinstance(exception, APINetworkError):
        return True

    if isinstance(exception, APIHTTPError):
        retriable_status_codes = {
            429,
            500,
            502,
            503,
            504,
        }
        return exception.status_code in retriable_status_codes

    return False


def retry_api_call():
    """Retry decorator with support for 429 Rate Limit."""
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception(is_retriable_error),
        reraise=True,
    )


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def serialize_dates(obj: Any) -> Any:
    """Recursively serialize datetime objects to ISO format strings."""
    if isinstance(obj, date):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {key: serialize_dates(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [serialize_dates(item) for item in obj]
    return obj


# ============================================================================
# BASE CLIENT
# ============================================================================


class BaseClient:
    """Base class for API clients."""

    def __init__(self, base_url: str, timeout: float = 10.0):
        self.base_url = base_url
        self.timeout = httpx.Timeout(timeout, connect=5.0)
        self.default_headers = {"Content-Type": "application/json"}

    async def _get_headers(self, user_telegram_id: Optional[int] = None) -> Dict[str, str]:
        """Получить заголовки с токеном авторизации, если user_telegram_id предоставлен."""
        headers = self.default_headers.copy()
        if user_telegram_id:
            token = await auth_manager.get_token(user_telegram_id)
            if token:
                headers["Authorization"] = f"Bearer {token}"
            else:
                logger.warning(f"NO TOKEN for {user_telegram_id}")
        return headers

    async def _request(
        self, method: str, url: str, **kwargs
    ) -> httpx.Response:
        """Сделать HTTP-запрос с использованием общего HTTP-клиента."""
        if not resources.http_client:
            raise RuntimeError("HTTP client not initialized. Check startup sequence.")

        try:
            response = await resources.http_client.request(
                method, url, **kwargs
            )
            return response
        except httpx.TimeoutException as e:
            raise APINetworkError(f"Timeout: {str(e)}")
        except httpx.RequestError as e:
            raise APINetworkError(f"Network error: {str(e)}")


# ============================================================================
# CANDIDATE API CLIENT
# ============================================================================


class CandidateAPIClient(BaseClient):
    def __init__(self):
        super().__init__(
            f"{settings.CANDIDATE_SERVICE_URL}/candidates", timeout=15.0
        )

    @retry_api_call()
    async def register_candidate_profile(
        self, profile_data: dict
    ) -> Dict[str, Any]:
        """Создать профиль кандидата. Ожидается, что profile_data содержит 'telegram_id'."""
        url = f"{self.base_url}/"
        payload = serialize_dates(profile_data.copy())
        tg_id = payload.get("telegram_id")
        headers = await self._get_headers(tg_id)

        logger.info(f"Registering candidate {tg_id}")

        try:
            response = await self._request(
                "POST", url, json=payload, headers=headers, timeout=self.timeout
            )

            if response.status_code == 409:
                raise APIHTTPError(409, "Candidate already exists", response.text)

            response.raise_for_status()
            logger.info(f"Candidate registered successfully: {tg_id}")
            return response.json()
        except httpx.HTTPStatusError as e:
            raise APIHTTPError(
                e.response.status_code,
                f"HTTP error: {e.response.text[:200]}",
                e.response.text,
            )

    @retry_api_call()
    async def get_candidate_by_telegram_id(
        self, telegram_id: int
    ) -> Dict[str, Any]:
        """Получить профиль кандидата по Telegram ID."""
        headers = await self._get_headers(telegram_id)

        try:
            response = await self._request(
                "GET",
                f"{self.base_url}/by-telegram/{telegram_id}",
                headers=headers,
                timeout=self.timeout,
            )

            if response.status_code == 404:
                raise APIHTTPError(404, "Candidate not found", response.text)

            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise APIHTTPError(e.response.status_code, e.response.text)

    @retry_api_call()
    async def update_candidate_profile(
        self, telegram_id: int, profile_data: dict
    ) -> Dict[str, Any]:
        """Обновить профиль кандидата по Telegram ID."""
        url = f"{self.base_url}/by-telegram/{telegram_id}"
        payload = serialize_dates(profile_data.copy())
        headers = await self._get_headers(telegram_id)

        try:
            response = await self._request(
                "PATCH", url, json=payload, headers=headers, timeout=self.timeout
            )
            response.raise_for_status()
            logger.info(f"Candidate profile updated: {telegram_id}")
            return response.json()
        except httpx.HTTPStatusError as e:
            raise APIHTTPError(e.response.status_code, e.response.text)

    @retry_api_call()
    async def replace_resume(self, telegram_id: int, file_id: UUID) -> bool:
        """Заменить резюме кандидата."""
        url = f"{self.base_url}/by-telegram/{telegram_id}/resume"
        payload = {"file_id": str(file_id)}
        headers = await self._get_headers(telegram_id)

        try:
            response = await self._request(
                "PUT", url, json=payload, headers=headers, timeout=self.timeout
            )
            response.raise_for_status()
            logger.info(f"Resume replaced for candidate {telegram_id}")
            return True
        except httpx.HTTPStatusError as e:
            raise APIHTTPError(e.response.status_code, e.response.text)

    @retry_api_call()
    async def replace_avatar(self, telegram_id: int, file_id: UUID) -> bool:
        """Заменить аватар кандидата."""
        url = f"{self.base_url}/by-telegram/{telegram_id}/avatar"
        payload = {"file_id": str(file_id)}
        headers = await self._get_headers(telegram_id)

        try:
            response = await self._request(
                "PUT", url, json=payload, headers=headers, timeout=self.timeout
            )
            response.raise_for_status()
            logger.info(f"Avatar replaced for candidate {telegram_id}")
            return True
        except httpx.HTTPStatusError as e:
            raise APIHTTPError(e.response.status_code, e.response.text)

    @retry_api_call()
    async def delete_avatar(self, telegram_id: int) -> bool:
        """Удалить аватар кандидата."""
        url = f"{self.base_url}/by-telegram/{telegram_id}/avatar"
        headers = await self._get_headers(telegram_id)

        try:
            response = await self._request(
                "DELETE", url, headers=headers, timeout=self.timeout
            )

            if response.status_code == 404:
                logger.info(f"Avatar not found for candidate {telegram_id}")
                return True

            response.raise_for_status()
            logger.info(f"Avatar deleted for candidate {telegram_id}")
            return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return True
            raise APIHTTPError(e.response.status_code, e.response.text)

    @retry_api_call()
    async def delete_resume(self, telegram_id: int) -> bool:
        """Удалить резюме кандидата."""
        url = f"{self.base_url}/by-telegram/{telegram_id}/resume"
        headers = await self._get_headers(telegram_id)

        try:
            response = await self._request(
                "DELETE", url, headers=headers, timeout=self.timeout
            )

            if response.status_code == 404:
                logger.info(f"Resume not found for candidate {telegram_id}")
                return True

            response.raise_for_status()
            logger.info(f"Resume deleted for candidate {telegram_id}")
            return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return True
            raise APIHTTPError(e.response.status_code, e.response.text)


# ============================================================================
# EMPLOYER API CLIENT
# ============================================================================


class EmployerAPIClient(BaseClient):
    def __init__(self):
        super().__init__(
            f"{settings.EMPLOYER_SERVICE_URL}/employers", timeout=20.0
        )

    @retry_api_call()
    async def get_or_create_employer(
        self, telegram_id: int, username: str
    ) -> Dict[str, Any]:
        """Создать или получить профиль работодателя."""
        payload = {
            "telegram_id": telegram_id,
            "contacts": {"telegram": f"@{username}"},
        }
        headers = await self._get_headers(telegram_id)

        try:
            response = await self._request(
                "POST",
                f"{self.base_url}/",
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            logger.info(f"Employer created/retrieved: {telegram_id}")
            return response.json()
        except httpx.HTTPStatusError as e:
            raise APIHTTPError(e.response.status_code, e.response.text)

    @retry_api_call()
    async def update_employer_profile(
        self, employer_id: str, update_data: dict
    ) -> Dict[str, Any]:
        """Обновить профиль работодателя."""
        url = f"{self.base_url}/{employer_id}"

        try:
            response = await self._request(
                "PATCH",
                url,
                json=update_data,
                headers=self.default_headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            logger.info(f"Employer updated: {employer_id}")
            return response.json()
        except httpx.HTTPStatusError as e:
            raise APIHTTPError(e.response.status_code, e.response.text)

    @retry_api_call()
    async def create_search_session(
        self, employer_id: str, filters: dict
    ) -> Dict[str, Any]:
        """Создать сессию поиска кандидатов с заданными фильтрами."""
        payload = {
            "title": f"Search for {filters.get('role', 'candidate')}",
            "filters": filters,
        }
        payload = serialize_dates(payload)

        try:
            response = await self._request(
                "POST",
                f"{self.base_url}/{employer_id}/searches",
                json=payload,
                headers=self.default_headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            logger.info(f"Search session created for employer {employer_id}")
            return response.json()
        except httpx.HTTPStatusError as e:
            raise APIHTTPError(e.response.status_code, e.response.text)

    @retry_api_call()
    async def get_next_candidate(self, session_id: str) -> Dict[str, Any]:
        """Получить следующего кандидата в сессии поиска."""
        url = f"{self.base_url}/searches/{session_id}/next"

        try:
            response = await self._request(
                "POST",
                url,
                headers=self.default_headers,
                timeout=30.0,
            )

            if response.status_code == 404:
                raise APIHTTPError(404, "Session not found", response.text)

            response.raise_for_status()
            data = response.json()
            return data.get("candidate")
        except httpx.HTTPStatusError as e:
            raise APIHTTPError(e.response.status_code, e.response.text)

    @retry_api_call()
    async def save_decision(
        self, session_id: str, candidate_id: str, decision: str
    ) -> bool:
        """Сохранить решение по кандидату в сессии поиска."""
        url = f"{self.base_url}/searches/{session_id}/decisions"
        payload = {"candidate_id": candidate_id, "decision": decision}

        try:
            response = await self._request(
                "POST",
                url,
                json=payload,
                headers=self.default_headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            logger.info(f"Decision saved for candidate {candidate_id}")
            return True
        except httpx.HTTPStatusError as e:
            raise APIHTTPError(e.response.status_code, e.response.text)

    @retry_api_call()
    async def request_contacts(
        self, employer_id: str, candidate_id: str
    ) -> Dict[str, Any]:
        """Запросить контактные данные кандидата."""
        url = f"{self.base_url}/{employer_id}/contact-requests"
        payload = {"candidate_id": candidate_id}

        try:
            response = await self._request(
                "POST",
                url,
                json=payload,
                headers=self.default_headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            logger.info(f"Contact request created for candidate {candidate_id}")
            return response.json()
        except httpx.HTTPStatusError as e:
            raise APIHTTPError(e.response.status_code, e.response.text)

    @retry_api_call()
    async def respond_to_contact_request(
        self, request_id: str, granted: bool
    ) -> bool:
        """Ответить на запрос контактов от работодателя."""
        url = f"{self.base_url}/contact-requests/{request_id}"

        try:
            response = await self._request(
                "PUT",
                url,
                json={"granted": granted},
                headers=self.default_headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            logger.info(f"Contact request response recorded: {request_id}")
            return True
        except httpx.HTTPStatusError as e:
            raise APIHTTPError(e.response.status_code, e.response.text)

    @retry_api_call()
    async def get_contact_request_details(
        self, request_id: str
    ) -> Dict[str, Any]:
        """Получить детали запроса контактов."""
        url = f"{self.base_url}/contact-requests/{request_id}/details"

        try:
            response = await self._request(
                "GET",
                url,
                headers=self.default_headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise APIHTTPError(e.response.status_code, e.response.text)


# ============================================================================
# FILE API CLIENT
# ============================================================================


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
        file_type: str,
    ) -> Dict[str, Any]:
        """Загрузить файл и получить его ID. file_type может быть 'resume' или 'avatar'."""
        url = f"{self.base_url}/upload"

        data = {"owner_telegram_id": str(owner_id), "file_type": file_type}
        files = {"file": (filename, file_data, content_type)}

        headers = await self._get_headers(owner_id)
        if "Content-Type" in headers:
            del headers["Content-Type"]

        try:
            response = await self._request(
                "POST",
                url,
                data=data,
                files=files,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            logger.info(f"File uploaded for user {owner_id}: {filename}")
            return response.json()
        except httpx.HTTPStatusError as e:
            raise APIHTTPError(e.response.status_code, e.response.text)

    @retry_api_call()
    async def get_download_url_by_file_id(self, file_id: UUID) -> str:
        """Получить URL для скачивания файла по его ID."""
        try:
            response = await self._request(
                "GET",
                f"{self.base_url}/{file_id}/url",
                timeout=self.timeout,
            )

            if response.status_code == 404:
                raise APIHTTPError(404, f"File not found: {file_id}")

            response.raise_for_status()
            data = response.json()
            return data.get("download_url")
        except httpx.HTTPStatusError as e:
            raise APIHTTPError(e.response.status_code, e.response.text)

    @retry_api_call()
    async def delete_file(self, file_id: UUID, owner_telegram_id: int) -> bool:
        """Удалить файл."""
        params = {"owner_telegram_id": owner_telegram_id}
        headers = await self._get_headers(owner_telegram_id)

        try:
            response = await self._request(
                "DELETE",
                f"{self.base_url}/{file_id}",
                params=params,
                headers=headers,
                timeout=self.timeout,
            )

            if response.status_code == 404:
                logger.info(f"File not found: {file_id}")
                return True

            response.raise_for_status()
            logger.info(f"File deleted: {file_id}")
            return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return True
            raise APIHTTPError(e.response.status_code, e.response.text)


# ============================================================================
# SEARCH API CLIENT
# ============================================================================


class SearchAPIClient(BaseClient):
    def __init__(self):
        super().__init__(f"{settings.SEARCH_SERVICE_URL}/search", timeout=5.0)

    @retry_api_call()
    async def trigger_reindex(self, admin_tg_id: int) -> bool:
        """Запустить процесс переиндексации. Доступно только для администраторов."""
        headers = await self._get_headers(admin_tg_id)
        url = f"{self.base_url}/index/rebuild"

        try:
            response = await self._request(
                "POST", url, headers=headers, timeout=self.timeout
            )
            response.raise_for_status()
            logger.info("Search index rebuild triggered")
            return True
        except httpx.HTTPStatusError as e:
            raise APIHTTPError(e.response.status_code, e.response.text)


# ============================================================================
# SINGLETON INSTANCES
# ============================================================================

candidate_api_client = CandidateAPIClient()
employer_api_client = EmployerAPIClient()
file_api_client = FileAPIClient()
search_api_client = SearchAPIClient()