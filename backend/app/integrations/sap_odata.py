import base64
import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

from app.core.config import BACKEND_DIR, settings


CONNECTOR_TYPE = "sap_odata"


class ConnectorConfigurationError(Exception):
    pass


class ConnectorRequestError(Exception):
    pass


@dataclass
class ConnectorResult:
    ok: bool
    status: str
    message: str
    metadata: Dict[str, Any]
    capabilities: Dict[str, Any]


class ErpConnector(Protocol):
    connector_type: str
    mode: str

    def metadata(self) -> Dict[str, Any]:
        ...

    def capabilities(self) -> Dict[str, Any]:
        ...

    def test_connection(self) -> ConnectorResult:
        ...

    def fetch_materials(self, *, entity_set: Optional[str] = None, max_records: Optional[int] = None) -> List[Dict[str, Any]]:
        ...


def sanitized_url(value: str) -> Optional[str]:
    if not value:
        return None
    parsed = urllib.parse.urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        return value.split("?")[0]
    host = parsed.hostname or parsed.netloc
    port = f":{parsed.port}" if parsed.port else ""
    return urllib.parse.urlunparse((parsed.scheme, f"{host}{port}", "", "", "", ""))


def sanitized_error(exc: Exception) -> str:
    if isinstance(exc, ConnectorConfigurationError):
        return str(exc)
    if isinstance(exc, urllib.error.HTTPError):
        return f"SAP OData request failed with HTTP {exc.code}."
    if isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", None)
        if isinstance(reason, socket.timeout):
            return "SAP OData request timed out."
        return "SAP OData endpoint could not be reached."
    if isinstance(exc, TimeoutError):
        return "SAP OData request timed out."
    return "SAP OData request failed. Check sanitized connector configuration and network reachability."


class MockSapODataConnector:
    connector_type = CONNECTOR_TYPE
    mode = "mock"

    def __init__(self, fixture_path: Optional[Path] = None, entity_set: Optional[str] = None):
        self.fixture_path = fixture_path or BACKEND_DIR / "sample-data" / "sap_odata_materials_mock.json"
        self.entity_set = entity_set or settings.SAP_ODATA_ENTITY_SET

    def metadata(self) -> Dict[str, Any]:
        return {
            "connector_type": self.connector_type,
            "mode": self.mode,
            "entity_set": self.entity_set,
            "fixture": str(self.fixture_path.name),
            "external_network": False,
        }

    def capabilities(self) -> Dict[str, Any]:
        return {
            "test_connection": True,
            "fetch_materials": True,
            "supports_max_records": True,
            "authentication": "none",
            "network_required": False,
        }

    def test_connection(self) -> ConnectorResult:
        records = self.fetch_materials()
        return ConnectorResult(
            ok=True,
            status="CONNECTED",
            message="Mock SAP OData connector is available without external network access.",
            metadata={**self.metadata(), "record_count": len(records)},
            capabilities=self.capabilities(),
        )

    def fetch_materials(self, *, entity_set: Optional[str] = None, max_records: Optional[int] = None) -> List[Dict[str, Any]]:
        with self.fixture_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        results = payload.get("d", {}).get("results", [])
        if max_records is not None:
            results = results[:max_records]
        return [dict(row) for row in results]


class SapODataConnector:
    connector_type = CONNECTOR_TYPE
    mode = "live"

    def __init__(
        self,
        *,
        base_url: str,
        entity_set: str,
        timeout_seconds: int,
        auth_mode: str,
        username: str = "",
        password: str = "",
        bearer_token: str = "",
    ):
        self.base_url = base_url.rstrip("/")
        self.entity_set = entity_set
        self.timeout_seconds = max(int(timeout_seconds or 10), 1)
        self.auth_mode = (auth_mode or "none").lower()
        self.username = username
        self.password = password
        self.bearer_token = bearer_token

    def _validate(self) -> None:
        if not self.base_url:
            raise ConnectorConfigurationError("SAP_ODATA_BASE_URL is required when SAP_ODATA_MODE=live.")
        if self.auth_mode not in {"none", "basic", "bearer"}:
            raise ConnectorConfigurationError("SAP_ODATA_AUTH_MODE must be one of none, basic, or bearer.")
        if self.auth_mode == "basic" and (not self.username or not self.password):
            raise ConnectorConfigurationError("SAP_ODATA_USERNAME and SAP_ODATA_PASSWORD are required for basic auth.")
        if self.auth_mode == "bearer" and not self.bearer_token:
            raise ConnectorConfigurationError("SAP_ODATA_BEARER_TOKEN is required for bearer auth.")
        if not self.entity_set:
            raise ConnectorConfigurationError("SAP_ODATA_ENTITY_SET is required.")

    def _headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.auth_mode == "basic":
            token = base64.b64encode(f"{self.username}:{self.password}".encode("utf-8")).decode("ascii")
            headers["Authorization"] = f"Basic {token}"
        elif self.auth_mode == "bearer":
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        return headers

    def _request_json(self, url: str) -> Dict[str, Any]:
        self._validate()
        request = urllib.request.Request(url, headers=self._headers(), method="GET")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except Exception as exc:
            raise ConnectorRequestError(sanitized_error(exc)) from exc

    def metadata(self) -> Dict[str, Any]:
        return {
            "connector_type": self.connector_type,
            "mode": self.mode,
            "base_url": sanitized_url(self.base_url),
            "entity_set": self.entity_set,
            "auth_mode": self.auth_mode,
            "timeout_seconds": self.timeout_seconds,
        }

    def capabilities(self) -> Dict[str, Any]:
        return {
            "test_connection": True,
            "fetch_materials": True,
            "supports_max_records": True,
            "authentication": self.auth_mode,
            "network_required": True,
        }

    def test_connection(self) -> ConnectorResult:
        self._validate()
        metadata_url = f"{self.base_url}/$metadata"
        request = urllib.request.Request(metadata_url, headers=self._headers(), method="GET")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                status_code = getattr(response, "status", 200)
        except Exception as exc:
            raise ConnectorRequestError(sanitized_error(exc)) from exc
        return ConnectorResult(
            ok=True,
            status="CONNECTED",
            message=f"SAP OData metadata endpoint responded with HTTP {status_code}.",
            metadata=self.metadata(),
            capabilities=self.capabilities(),
        )

    def fetch_materials(self, *, entity_set: Optional[str] = None, max_records: Optional[int] = None) -> List[Dict[str, Any]]:
        selected_entity = entity_set or self.entity_set
        query = {}
        if max_records:
            query["$top"] = str(max_records)
        url = f"{self.base_url}/{selected_entity}"
        if query:
            url = f"{url}?{urllib.parse.urlencode(query)}"
        payload = self._request_json(url)
        rows = payload.get("d", {}).get("results")
        if rows is None:
            rows = payload.get("value", [])
        if not isinstance(rows, list):
            raise ConnectorRequestError("SAP OData material response did not contain a list of records.")
        return [dict(row) for row in rows]


def get_sap_connector(*, entity_set: Optional[str] = None):
    mode = (settings.SAP_ODATA_MODE or "mock").lower()
    if mode == "mock":
        return MockSapODataConnector(entity_set=entity_set or settings.SAP_ODATA_ENTITY_SET)
    if mode == "live":
        return SapODataConnector(
            base_url=settings.SAP_ODATA_BASE_URL,
            entity_set=entity_set or settings.SAP_ODATA_ENTITY_SET,
            timeout_seconds=settings.SAP_ODATA_TIMEOUT_SECONDS,
            auth_mode=settings.SAP_ODATA_AUTH_MODE,
            username=settings.SAP_ODATA_USERNAME,
            password=settings.SAP_ODATA_PASSWORD,
            bearer_token=settings.SAP_ODATA_BEARER_TOKEN,
        )
    raise ConnectorConfigurationError("SAP_ODATA_MODE must be either mock or live.")
