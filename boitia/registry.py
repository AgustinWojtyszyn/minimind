"""Owner-only publication of verified shared engine URLs. No credentials in the public manifest."""
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


PROVIDER_FIELDS = {"kaggle": "kaggle_url", "modal": "modal_url",
                   "zerogpu": "zerogpu_url", "cpu": "cpu_url", "cloudflare": "cloudflare_url"}


def validate_provider_url(provider, url):
    if provider == "kaggle":
        return validate_tunnel(url)
    patterns = {
        "modal": r"https://[a-z0-9-]+\.modal\.run|https://[a-z0-9-]+\.[a-z0-9-]+\.modal\.direct",
        "zerogpu": r"https://[a-z0-9-]+\.hf\.space",
        "cpu": r"https://boitia\.agustinwojtyszyn\.com",
        "cloudflare": r"https://boitia-ai\.[a-z0-9-]+\.workers\.dev",
    }
    if provider not in patterns or not isinstance(url,str) or not re.fullmatch(patterns[provider],url):
        raise ValueError("URL de motor remoto inválida.")
    return url


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def publish_engine(url, token, *, provider="kaggle", opener=None):
    """Only update the fixed public registry; never print credentials or HTTP bodies."""
    url = validate_provider_url(provider, url)
    field = PROVIDER_FIELDS[provider]
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
            if document.get(field) == url:
                return False
            # Only publish the URL and timestamp; never infer credentials from the environment.
            retained = {}
            for kind,key in PROVIDER_FIELDS.items():
                if key in document:
                    value = document[key]
                    retained[key] = None if value is None else validate_provider_url(kind, value)
            retained[field] = url
            document = {"version":1, **retained,
                        "updated_at":datetime.datetime.now(datetime.timezone.utc).isoformat()}
            content = base64.b64encode((json.dumps(document, indent=2) + "\n").encode()).decode()
            request("PUT", payload={"message": "Register active BoitIA engine", "branch": "master",
                                     "sha": current["sha"], "content": content})
            return True
        except urllib.error.HTTPError as err:
            if err.code == 409 and attempt == 0:
                continue
            raise RuntimeError(f"GitHub rechazó la publicación (HTTP {err.code}).") from None
    raise RuntimeError("El registro cambió simultáneamente.")
