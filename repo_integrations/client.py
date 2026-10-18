"""Small direct readers; MCP configuration is metadata, never an implicit transport."""
import datetime
import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

READERS = {"github", "linear", "notion"}
OPTIONAL = {"browser", "tracker", "docs", "observability", "hosting", "database"}
ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")
REPO_NAME = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
UUID = re.compile(r"^[a-fA-F0-9]{8}-?[a-fA-F0-9]{4}-?[a-fA-F0-9]{4}-?[a-fA-F0-9]{4}-?[a-fA-F0-9]{12}$")
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
HOSTNAME = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,62}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,62}[A-Za-z0-9])?)*$")
API_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Overridable per provider for GHES and self-hosted or proxied APIs.
ENDPOINTS = {"github": {"host": "github.com"},
             "linear": {"endpoint": "https://api.linear.app/graphql"},
             "notion": {"endpoint": "https://api.notion.com/v1", "apiVersion": "2022-06-28"}}
# Secret-reference scheme -> the local CLI that resolves it (metadata only here).
SECRET_SCHEMES = {"op": "op", "vault": "vault"}


class IntegrationError(ValueError):
    """A safe, bounded diagnostic; never contains provider response bodies."""


def _keys(value, allowed, label):
    if not isinstance(value, dict) or set(value) - allowed:
        raise IntegrationError(f"Invalid {label} configuration fields")


def validate_config(config):
    _keys(config, {"schemaVersion", "readOnly", "limits", "providers"}, "root")
    if (type(config.get("schemaVersion")) is not int or config.get("schemaVersion") != 1) or config.get("readOnly") is not True:
        raise IntegrationError("schemaVersion=1 and readOnly=true are required")
    limits = config.get("limits", {})
    _keys(limits, {"maxPages", "pageSize", "maxItems", "maxTextChars"}, "limits")
    for key, default, maximum in [("maxPages", 3, 10), ("pageSize", 50, 100),
                                  ("maxItems", 50, 200), ("maxTextChars", 240, 500)]:
        value = limits.get(key, default)
        if type(value) is not int or not 1 <= value <= maximum:
            raise IntegrationError(f"{key} must be an integer between 1 and {maximum}")
    providers = config.get("providers")
    if not isinstance(providers, dict) or set(providers) - READERS - OPTIONAL - {"secrets"}:
        raise IntegrationError("Unknown providers")
    schemes = secret_schemes(config)
    for name, settings in providers.items():
        _keys(settings, {"enabled", "tokenEnv", "secretRefs", "repoAllowlist", "projectIds",
                         "pageAllowlist", "mcpUrl"} | set(ENDPOINTS.get(name, {}))
              | ({"schemes"} if name == "secrets" else set()), name)
        if "host" in settings and (not isinstance(settings["host"], str) or len(settings["host"]) > 253
                                   or not HOSTNAME.fullmatch(settings["host"])):
            raise IntegrationError(f"{name}.host must be a bare hostname")
        if "endpoint" in settings and (not isinstance(settings["endpoint"], str) or len(settings["endpoint"]) > 300
                                       or not re.fullmatch(r"https://[^\s/?#]+(?:/[^\s?#]*)?", settings["endpoint"])):
            raise IntegrationError(f"{name}.endpoint must be an HTTPS URL without query")
        if "apiVersion" in settings and not API_DATE.fullmatch(str(settings["apiVersion"])):
            raise IntegrationError(f"{name}.apiVersion must be a YYYY-MM-DD version")
        if type(settings.get("enabled", False)) is not bool:
            raise IntegrationError(f"{name}.enabled must be boolean")
        if "tokenEnv" in settings and not ENV_NAME.fullmatch(str(settings["tokenEnv"])):
            raise IntegrationError(f"{name}.tokenEnv must name an environment variable")
        refs = settings.get("secretRefs", [])
        prefixes = tuple(f"{scheme}://" for scheme in schemes)
        if not isinstance(refs, list) or any(not isinstance(x, str) or not x.startswith(prefixes) or len(x) > 300 for x in refs):
            raise IntegrationError(f"{name}.secretRefs must contain {'/'.join(prefixes)} metadata references")
        if "mcpUrl" in settings and (not isinstance(settings["mcpUrl"], str) or
                                    not settings["mcpUrl"].startswith("https://") or
                                    len(settings["mcpUrl"]) > 300):
            raise IntegrationError(f"{name}.mcpUrl must be HTTPS metadata")
        for field, pattern in [("repoAllowlist", REPO_NAME), ("projectIds", UUID), ("pageAllowlist", UUID)]:
            if field in settings:
                values = settings[field]
                if not isinstance(values, list) or len(values) > 20 or any(not isinstance(x, str) or not pattern.fullmatch(x) for x in values):
                    raise IntegrationError(f"Invalid {name}.{field}")
        if name in {"linear", "notion"} and settings.get("enabled") and not settings.get("tokenEnv"):
            raise IntegrationError(f"{name}.tokenEnv is required when enabled")
        scope = {"github": "repoAllowlist", "linear": "projectIds", "notion": "pageAllowlist"}.get(name)
        if scope and settings.get("enabled") and not settings.get(scope):
            raise IntegrationError(f"{name}.{scope} is required when enabled")
    return config


def secret_schemes(config):
    """Allowed secret-reference schemes (providers.secrets.schemes, default op)."""
    schemes = ((config.get("providers") or {}).get("secrets") or {}).get("schemes", ["op"])
    if (not isinstance(schemes, list) or not schemes or len(set(map(str, schemes))) != len(schemes)
            or any(x not in SECRET_SCHEMES for x in schemes)):
        raise IntegrationError("secrets.schemes must list distinct schemes from: " + ", ".join(sorted(SECRET_SCHEMES)))
    return schemes


def setting(config, provider, key):
    return config["providers"][provider].get(key, ENDPOINTS[provider][key])


def load_config(path):
    try:
        return validate_config(json.loads(Path(path).read_text(encoding="utf8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntegrationError("Cannot read valid integration configuration") from exc


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    # Never forward Authorization to a redirected host, including in tests.
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise IntegrationError("Provider redirect refused")


def default_http(method, url, headers, payload):
    body = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.build_opener(_NoRedirect()).open(request, timeout=20) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise IntegrationError("Provider response exceeds byte limit")
        return json.loads(raw)
    except urllib.error.HTTPError as exc:
        raise IntegrationError(f"Provider HTTP error {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        raise IntegrationError("Provider read failed") from None


def default_cli(args):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise IntegrationError("GitHub CLI unavailable or timed out") from None
    if result.returncode:
        raise IntegrationError("GitHub CLI read failed")
    if len(result.stdout.encode()) > MAX_RESPONSE_BYTES:
        raise IntegrationError("GitHub response exceeds byte limit")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        raise IntegrationError("GitHub returned invalid JSON") from None


class IntegrationClient:
    def __init__(self, config, *, http_transport=None, cli_transport=None, environ=None,
                 available=None, clock=None):
        self.config = validate_config(config)
        self.http = http_transport or default_http
        self.cli = cli_transport or default_cli
        self.env = os.environ if environ is None else environ
        self.available = available or (lambda name: shutil.which(name) is not None)
        self.clock = clock or (lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
        self.limits = {"maxPages": 3, "pageSize": 50, "maxItems": 50, "maxTextChars": 240,
                       **config.get("limits", {})}

    def _safe_text(self, value, limit=None):
        text = str(value or "")
        for provider in self.config["providers"].values():
            secret = self.env.get(provider.get("tokenEnv", ""))
            if secret:
                text = text.replace(secret, "[REDACTED]")
        text = re.sub(r"(?:gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+|lin_api_[A-Za-z0-9_]+|(?:secret|ntn)_[A-Za-z0-9_]+)", "[REDACTED]", text)
        return text[:limit or self.limits["maxTextChars"]]

    def doctor(self):
        capabilities = []
        for name, settings in sorted(self.config["providers"].items()):
            enabled = settings.get("enabled", False)
            credential = bool(self.env.get(settings.get("tokenEnv", "")))
            reader = name in READERS
            status = "disabled"
            if enabled:
                if name == "secrets":
                    tools = [SECRET_SCHEMES[s] for s in secret_schemes(self.config)]
                    status = "metadata-only" if all(self.available(t) for t in tools) else "unavailable"
                elif not reader:
                    status = "unsupported-reader"
                elif name == "github":
                    status = "available-unverified" if self.available("gh") else "unavailable"
                else:
                    status = "available-unverified" if credential else "missing-credential"
            capabilities.append({"provider": name, "status": status, "readerImplemented": reader,
                                 "credentialPresent": credential, "mcpMetadataConfigured": bool(settings.get("mcpUrl")),
                                 "externalWrites": False})
        return {"schemaVersion": 1, "readOnly": True, "capabilities": capabilities}

    def _request(self, provider, method, url, payload=None):
        settings = self.config["providers"][provider]
        token = self.env.get(settings.get("tokenEnv", ""))
        if not token:
            raise IntegrationError("Credential environment variable is missing")
        headers = {"Content-Type": "application/json", "Authorization": token if provider == "linear" else f"Bearer {token}"}
        if provider == "notion":
            headers["Notion-Version"] = setting(self.config, "notion", "apiVersion")
        try:
            data = self.http(method, url, headers, payload)
        except IntegrationError:
            raise
        except Exception:
            raise IntegrationError("Provider transport failed") from None
        if not isinstance(data, dict):
            raise IntegrationError("Provider returned invalid response shape")
        return data

    def read(self, provider):
        try:
            return self._read(provider)
        except IntegrationError:
            raise
        except Exception:
            raise IntegrationError("Provider response could not be safely interpreted") from None

    def _read(self, provider):
        settings = self.config["providers"].get(provider)
        if not settings or not settings.get("enabled"):
            raise IntegrationError("Provider is not enabled")
        if provider not in READERS:
            raise IntegrationError("Provider has no implemented reader")
        items, scopes, complete, pages = [], [], True, 0
        if provider == "github":
            for repo in settings["repoAllowlist"]:
                scope_complete = False
                for page in range(1, self.limits["maxPages"] + 1):
                    try:
                        data = self.cli(["gh", "api", "--hostname", setting(self.config, "github", "host"), "--method", "GET",
                                         f"repos/{repo}/pulls?state=open&per_page={self.limits['pageSize']}&page={page}"])
                    except IntegrationError:
                        raise
                    except Exception:
                        raise IntegrationError("GitHub transport failed") from None
                    if not isinstance(data, list) or len(data) > self.limits["pageSize"]:
                        raise IntegrationError("GitHub returned invalid pull request page")
                    pages += 1
                    for pr in data:
                        if not isinstance(pr, dict) or type(pr.get("number")) is not int:
                            raise IntegrationError("GitHub returned invalid pull request")
                        head = pr.get("head")
                        if not isinstance(head, dict) or not re.fullmatch(r"[a-fA-F0-9]{40,64}", str(head.get("sha", ""))):
                            raise IntegrationError("GitHub pull request head is missing")
                        items.append({"repo": repo, "number": pr["number"], "title": self._safe_text(pr.get("title")),
                                      "head": self._safe_text(head["sha"], limit=64),
                                      "draft": pr.get("draft") is True})
                    if len(data) < self.limits["pageSize"]:
                        scope_complete = True
                        break
                    if len(items) >= self.limits["maxItems"]:
                        break
                scopes.append({"repo": repo, "scope": "open-pull-requests", "complete": scope_complete})
                complete &= scope_complete
                if len(items) >= self.limits["maxItems"]:
                    complete &= repo == settings["repoAllowlist"][-1]
                    break
        elif provider == "linear":
            for project in settings["projectIds"]:
                cursor, scope_complete = None, False
                for _ in range(self.limits["maxPages"]):
                    query = "query($project: String!, $first: Int!, $after: String) { issues(filter: {project: {id: {eq: $project}}}, first: $first, after: $after) { nodes { id identifier title updatedAt state { name type } } pageInfo { hasNextPage endCursor } } }"
                    data = self._request(provider, "POST", setting(self.config, "linear", "endpoint"), {
                        "query": query, "variables": {"project": project, "first": self.limits["pageSize"], "after": cursor}})
                    if data.get("errors"):
                        raise IntegrationError("Linear GraphQL returned errors")
                    connection = (data.get("data") or {}).get("issues")
                    nodes, more, next_cursor = self._connection(connection)
                    pages += 1
                    for issue in nodes:
                        if not isinstance(issue, dict) or not issue.get("identifier"):
                            raise IntegrationError("Linear returned invalid issue")
                        items.append({"project": project, "identifier": self._safe_text(issue["identifier"], limit=64),
                                      "title": self._safe_text(issue.get("title")),
                                      "updatedAt": self._safe_text(issue.get("updatedAt")),
                                      "state": self._safe_text((issue.get("state") or {}).get("name"))})
                    if not more:
                        scope_complete = True
                        break
                    if next_cursor == cursor:
                        raise IntegrationError("Linear pagination cursor did not advance")
                    cursor = next_cursor
                    if len(items) >= self.limits["maxItems"]:
                        break
                scopes.append({"project": project, "scope": "project-issues", "complete": scope_complete})
                complete &= scope_complete
                if len(items) >= self.limits["maxItems"]:
                    complete &= project == settings["projectIds"][-1]
                    break
        else:
            for page_id in settings["pageAllowlist"]:
                cursor, scope_complete = None, False
                for _ in range(self.limits["maxPages"]):
                    url = f"{setting(self.config, 'notion', 'endpoint').rstrip('/')}/blocks/{page_id}/children?page_size={self.limits['pageSize']}"
                    if cursor:
                        from urllib.parse import quote
                        url += "&start_cursor=" + quote(cursor, safe="")
                    data = self._request(provider, "GET", url)
                    if data.get("object") == "error":
                        raise IntegrationError("Notion returned an API error")
                    nodes = data.get("results")
                    if not isinstance(nodes, list) or type(data.get("has_more")) is not bool:
                        raise IntegrationError("Notion pagination completeness is unknown")
                    if len(nodes) > self.limits["pageSize"]:
                        raise IntegrationError("Notion page exceeds configured size")
                    pages += 1
                    for block in nodes:
                        if not isinstance(block, dict) or not block.get("id") or not isinstance(block.get("type"), str):
                            raise IntegrationError("Notion returned invalid block")
                        kind = block["type"]
                        content = block.get(kind) or {}
                        texts = content.get("rich_text", []) if isinstance(content, dict) else []
                        text = "".join(str(part.get("plain_text", "")) for part in texts if isinstance(part, dict))
                        items.append({"page": page_id, "id": self._safe_text(block["id"], limit=64), "type": self._safe_text(kind),
                                      "text": self._safe_text(text), "hasChildren": block.get("has_children") is True})
                    if not data["has_more"]:
                        scope_complete = True
                        break
                    next_cursor = data.get("next_cursor")
                    if not isinstance(next_cursor, str) or not next_cursor or next_cursor == cursor or len(next_cursor) > 500:
                        raise IntegrationError("Notion pagination cursor is missing or did not advance")
                    cursor = next_cursor
                    if len(items) >= self.limits["maxItems"]:
                        break
                scopes.append({"page": page_id, "scope": "top-level-blocks", "complete": scope_complete,
                               "descendantsRead": False})
                complete &= scope_complete
                if len(items) >= self.limits["maxItems"]:
                    complete &= page_id == settings["pageAllowlist"][-1]
                    break
        omitted = max(0, len(items) - self.limits["maxItems"])
        if omitted:
            complete = False
        return {"provider": provider, "fetchedAt": self.clock(), "complete": bool(complete),
                "readOnly": True, "content": "bounded-summary", "maxTextChars": self.limits["maxTextChars"],
                "scopes": scopes, "pagesRead": pages,
                "items": items[:self.limits["maxItems"]], "omittedItems": omitted}

    def _connection(self, connection):
        if not isinstance(connection, dict) or not isinstance(connection.get("nodes"), list):
            raise IntegrationError("Linear issue connection is missing")
        info = connection.get("pageInfo")
        if not isinstance(info, dict) or type(info.get("hasNextPage")) is not bool:
            raise IntegrationError("Linear pagination completeness is unknown")
        cursor = info.get("endCursor")
        if info["hasNextPage"] and (not isinstance(cursor, str) or not cursor or len(cursor) > 500):
            raise IntegrationError("Linear next cursor is missing")
        if len(connection["nodes"]) > self.limits["pageSize"]:
            raise IntegrationError("Linear page exceeds configured size")
        return connection["nodes"], info["hasNextPage"], cursor
