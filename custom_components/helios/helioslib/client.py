"""HTTP client for Helios easyControls ventilation units.

Design notes (from live protocol analysis of a KWL EC 500W R):

* The webserver serves connections serially with ~1 request/second
  sustained throughput, so this client does one connection per request
  and batches every read into a single ``werteN.xml`` page fetch.
* The device keeps a per-client session after login; there is no cookie.
  A 403 triggers exactly one transparent re-login + retry.
* A write is one POST per change (``vXXXXX=value`` to ``/info.htm``).
  Never write in a polling loop - write-on-change only.
"""

import http.client
import re
import threading
import time
import urllib.parse
from xml.etree import ElementTree

from . import variables

DEFAULT_PASSWORD = "!helios!"
DEFAULT_TIMEOUT = 8.0
INFO_PATH = "/info.htm"
DEFAULT_PAGE = variables.PAGE_SENSORS


class HeliosError(Exception):
    """Base error talking to the unit."""


class HeliosAuthError(HeliosError):
    """Login rejected (wrong password)."""


class HeliosConnectionError(HeliosError):
    """Network level failure."""


_PAIR_RE = re.compile(r"<ID>\s*(.*?)\s*</ID>\s*<VA>\s*(.*?)\s*</VA>", re.DOTALL)


def parse_parameter_xml(text):
    """Parse the ``<PARAMETER><ID>..</ID><VA>..</VA>..</PARAMETER> pages."""
    pairs = []
    try:
        root = ElementTree.fromstring(text.strip())
        current = None
        for element in root.iter():
            if element.tag == "ID":
                current = (element.text or "").strip()
            elif element.tag == "VA" and current is not None:
                pairs.append((current, (element.text or "").strip()))
                current = None
    except ElementTree.ParseError:
        pairs = [(a.strip(), b.strip()) for a, b in _PAIR_RE.findall(text)]
    return dict(pairs)


class HeliosClient:
    """Thread-safe client for one easyControls unit."""

    def __init__(self, host, password=DEFAULT_PASSWORD, port=80,
                 timeout=DEFAULT_TIMEOUT):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._password = password
        self._lock = threading.RLock()
        self._logged_in = False
        self._master_password = False
        self.stats = {
            "requests": 0,
            "errors": 0,
            "relogins": 0,
            "last_latency": None,
            "total_latency": 0.0,
        }

    # -- low level ---------------------------------------------------------
    def _request(self, method, path, body=None, auth_retry=True,
                 conn_retry=True):
        """One request on one fresh connection. Returns (status, text)."""
        with self._lock:
            payload = body.encode("utf-8") if isinstance(body, str) else body
            t0 = time.monotonic()
            conn = http.client.HTTPConnection(self.host, self.port,
                                              timeout=self.timeout)
            try:
                conn.request(
                    method, path, body=payload,
                    headers={"Content-Type": "application/x-www-form-urlencoded"})
                response = conn.getresponse()
                text = response.read().decode("utf-8", "replace")
                status = response.status
            except (OSError, http.client.HTTPException) as exc:
                self.stats["errors"] += 1
                if conn_retry:
                    # The device's session state can wedge after days of
                    # uptime: requests are dropped, or everything but the
                    # root page 403s (including the login page). A fresh
                    # login POST resets it (verified live 2026-11-14).
                    # Retry once after a forced re-login.
                    self.stats["relogins"] += 1
                    try:
                        self.login(force=True, conn_retry=False)
                    except HeliosError:
                        raise HeliosConnectionError(str(exc)) from exc
                    return self._request(method, path, body,
                                         auth_retry=False, conn_retry=False)
                raise HeliosConnectionError(str(exc)) from exc
            finally:
                try:
                    conn.close()
                except Exception:  # noqa: BLE001
                    pass
            latency = time.monotonic() - t0
            self.stats["requests"] += 1
            self.stats["last_latency"] = latency
            self.stats["total_latency"] += latency
            if status == 403 and auth_retry:
                self.stats["relogins"] += 1
                self.login(force=True)
                return self._request(method, path, body, auth_retry=False)
            return status, text

    # -- authentication -----------------------------------------------------
    def login(self, force=False, conn_retry=True):
        with self._lock:
            if self._logged_in and not force:
                return True
            status, _ = self._request("POST", INFO_PATH,
                                      "v00402=" + self._password,
                                      auth_retry=False,
                                      conn_retry=conn_retry)
            if status == 200:
                self._logged_in = True
                return True
            if status == 404:
                # Firmware quirk (see scripts.js): the master/service
                # password is acknowledged with a 404 response.
                self._logged_in = True
                self._master_password = True
                return True
            if status == 403:
                self._logged_in = False
                raise HeliosAuthError("password rejected by unit")
            raise HeliosError("login failed with HTTP %s" % status)

    @property
    def logged_in(self):
        return self._logged_in

    @property
    def master_password(self):
        return self._master_password

    # -- reads ----------------------------------------------------------------
    def get_page(self, page):
        """Fetch a generated batch page. Returns {variable: value}."""
        path = "/data/werte%s.xml" % page
        status, text = self._request("POST", path, "xml=" + path)
        if status == 200:
            data = parse_parameter_xml(text)
            if not data:
                raise HeliosError("page %s returned no variables" % page)
            return data
        if status == 404:
            raise HeliosError("page %s not available on this unit" % page)
        raise HeliosError("page %s: HTTP %s" % (page, status))

    def get_variables(self, names, pages=None):
        """Read the given variables using as few requests as possible."""
        if pages is None:
            pages = set()
            for name in names:
                pages.add(variables.PAGE_FOR_VAR.get(name, DEFAULT_PAGE))
        data = {}
        for page in sorted(pages):
            data.update(self.get_page(page))
        return {name: data.get(name) for name in names}

    def identify(self):
        """Device identity (type, article, MAC, serial, ...)."""
        return self.get_page(variables.PAGE_IDENTITY)

    def versions(self):
        """Firmware versions (v01101..)."""
        data = self.get_page(variables.PAGE_VERSION)
        return {key: value for key, value in data.items()
                if key.startswith("v011")}

    # -- writes -----------------------------------------------------------------
    def set_variable(self, name, value):
        """Write a single variable. Returns True on HTTP 200."""
        status, _ = self._request("POST", INFO_PATH, "%s=%s" % (name, value))
        return status == 200

    def set_variables(self, mapping):
        """Write several variables in ONE request (like the web UI forms)."""
        body = urllib.parse.urlencode({str(k): str(v) for k, v in mapping.items()})
        status, _ = self._request("POST", INFO_PATH, body)
        return status == 200

    # -- housekeeping ---------------------------------------------------------
    @property
    def average_latency(self):
        requests = self.stats["requests"] - self.stats["errors"]
        if requests <= 0:
            return None
        return self.stats["total_latency"] / requests

    def close(self):
        """Connections are per-request by design; nothing to close."""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False
