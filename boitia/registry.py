"""Owner-only publication of a verified Kaggle URL. No secrets in the public manifest."""
import base64
import datetime
import json
import re
import urllib.error
import urllib.request

REGISTRY_API = "https://api.github.com/repos/AgustinWojtyszyn/minimind/contents/docs/engine.json"
PUBLIC_ORIGIN = "https://agustinwojtyszyn.github.io"


def validate_tunnel(url):
    if not isinstance(url, str) or not re.fullmatch(r"https://[a-z0-9-]+\.trycloudflare\.com", url):
        raise ValueError("URL de túnel inválida.")
    return url


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def publish_engine(url, token, *, opener=None):
    """Only update the fixed public registry; never print credentials or HTTP bodies."""
    url = validate_tunnel(url)
    if not token:
        raise ValueError("Falta el secreto del propietario.")
    opener = opener or urllib.request.build_opener(NoRedirect())
    headers = {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "BoitIA-owner-registry"}

    def request(method, suffix="", payload=None):
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(REGISTRY_API + suffix, data=body, method=method,
                                     headers={**headers, "Content-Type": "application/json"})
        with opener.open(req, timeout=15) as response:
            return json.load(response)

    for attempt in range(2):
        try:
            current = request("GET", "?ref=master")
            document = json.loads(base64.b64decode(current["content"]))
            if document.get("version") != 1:
                raise ValueError("Versión de registro desconocida.")
            if document.get("kaggle_url") == url:
                return False
            # Only publish the URL and timestamp; never infer credentials from the environment.
            document = {"version": 1, "kaggle_url": url,
                        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()}
            content = base64.b64encode((json.dumps(document, indent=2) + "\n").encode()).decode()
            request("PUT", payload={"message": "Register active BoitIA engine", "branch": "master",
                                     "sha": current["sha"], "content": content})
            return True
        except urllib.error.HTTPError as err:
            if err.code == 409 and attempt == 0:
                continue
            raise RuntimeError(f"GitHub rechazó la publicación (HTTP {err.code}).") from None
    raise RuntimeError("El registro cambió simultáneamente.")
