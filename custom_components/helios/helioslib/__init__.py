"""helioslib - lightweight HTTP client and probe harness for Helios easyControls units.

The library talks the native easyControls web protocol:

* login:       POST ``v00402=<password>``   -> ``/info.htm``
* batch read:  POST ``xml=/data/werteN.xml`` -> ``/data/werteN.xml``
  (returns dozens of variables as ``<ID>/<VA>`` pairs in one request)
* write:       POST ``vXXXXX=value``        -> ``/info.htm``

It deliberately avoids the one-request-per-variable pattern used by the
Modbus/TCP gateway and the old eazyctrl based clients: the device serves
HTTP serially with roughly one request/second sustained throughput, so
batching is the only way to poll it politely.
"""

from .client import (
    DEFAULT_PASSWORD,
    HeliosAuthError,
    HeliosClient,
    HeliosConnectionError,
    HeliosError,
    parse_parameter_xml,
)
from . import probe, variables

__version__ = "0.5.0"

__all__ = [
    "DEFAULT_PASSWORD",
    "HeliosAuthError",
    "HeliosClient",
    "HeliosConnectionError",
    "HeliosError",
    "parse_parameter_xml",
    "probe",
    "variables",
]
