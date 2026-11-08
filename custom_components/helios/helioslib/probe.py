"""Probe harness for Helios easyControls units.

Purpose: characterise (and later regression-test) the device webserver.
Baselines recorded on 2026-11-08 (stock firmware 2.27, healthy state):

* serial GETs:      11-36 ms
* 8 parallel GETs:  tail up to ~1.0 s
* 16 parallel GETs: quantized ~1s/2s/3s/5s steps  (~1 request/s ceiling)
* Modbus/TCP 502:   closed unless v01200 'Modbus activated' is enabled
"""

import http.client
import socket
import statistics
import struct
import time
from concurrent.futures import ThreadPoolExecutor

MODBUS_PORT = 502
KWL_UNIT_ID = 180


def _one_http_get(host, port, path, timeout):
    t0 = time.monotonic()
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        conn.request("GET", path)
        resp = conn.getresponse()
        resp.read()
        return time.monotonic() - t0
    finally:
        conn.close()


def probe_serial(host, port=80, count=5, path="/", timeout=8.0):
    """Serial GETs, one connection each. Returns latencies (None on error)."""
    latencies = []
    for _ in range(count):
        try:
            latencies.append(_one_http_get(host, port, path, timeout))
        except (OSError, http.client.HTTPException):
            latencies.append(None)
    return latencies


def probe_parallel(host, port=80, count=16, path="/", timeout=25.0):
    """count simultaneous GETs - exposes the serial accept behaviour."""
    with ThreadPoolExecutor(max_workers=count) as pool:
        jobs = [
            pool.submit(_one_http_get, host, port, path, timeout)
            for _ in range(count)
        ]
        out = []
        for job in jobs:
            try:
                out.append(job.result())
            except (OSError, http.client.HTTPException):
                out.append(None)
        return out


def summarize(latencies):
    """Latency summary incl. 0.5s quantization histogram."""
    ok = [x for x in latencies if x is not None]
    summary = {"count": len(latencies), "failures": len(latencies) - len(ok)}
    if not ok:
        return summary
    ordered = sorted(ok)
    summary.update({
        "min_s": round(ordered[0], 4),
        "mean_s": round(statistics.fmean(ok), 4),
        "median_s": round(statistics.median(ok), 4),
        "p95_s": round(ordered[max(0, int(len(ordered) * 0.95) - 1)], 4),
        "max_s": round(ordered[-1], 4),
    })
    bins = {}
    for x in ok:
        b = round(x * 2) / 2
        bins[b] = bins.get(b, 0) + 1
    summary["histogram_0.5s"] = {("%gs" % k): v for k, v in sorted(bins.items())}
    return summary


def probe_batch(client, page, count=3):
    """Latency of logged-in batch page reads (the client's normal load)."""
    results = []
    for _ in range(count):
        t0 = time.monotonic()
        try:
            data = client.get_page(page)
            results.append({
                "latency_s": round(time.monotonic() - t0, 4),
                "variables": len(data),
            })
        except Exception as exc:  # noqa: BLE001 - report, don't crash
            results.append({"error": str(exc)})
    return results


def modbus_probe(host, port=MODBUS_PORT, timeout=3.0, var="v00102", varlen=1):
    """Check the Modbus/TCP gateway (needs v01200 'Modbus activated')."""
    result = {"host": host, "port": port, "port_open": False,
              "read": None, "error": None}
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
    except OSError as exc:
        result["error"] = "connect failed: %s" % exc
        return result
    result["port_open"] = True
    try:
        sock.settimeout(timeout)
        # 1) FC16: write the query string "vXXXXX" (NUL padded to even bytes)
        query = var.encode("ascii") + b"\x00"
        if len(query) % 2:
            query += b"\x00"
        pdu = struct.pack(">BHHB", 16, 1, len(query) // 2, len(query)) + query
        sock.sendall(struct.pack(">HHHB", 1, 0, len(pdu) + 1, KWL_UNIT_ID) + pdu)
        sock.recv(1024)
        # 2) FC3: read the answer registers starting at address 1
        answer_len = len(var) + 1 + varlen
        data_len = (answer_len + 2) // 2 * 2
        pdu = struct.pack(">BHH", 3, 1, data_len // 2)
        sock.sendall(struct.pack(">HHHB", 2, 0, len(pdu) + 1, KWL_UNIT_ID) + pdu)
        resp = sock.recv(1024)
        if len(resp) >= 10:
            raw = resp[9:9 + resp[8]]
            result["read"] = raw.split(b"\x00")[0].decode("ascii", "replace")
    except (OSError, struct.error) as exc:
        result["error"] = str(exc)
    finally:
        sock.close()
    return result


def regression(host, password="!helios!", parallel_small=8, parallel_big=16):
    """Full baseline/verification suite. JSON-serializable for diffing."""
    report = {
        "http_serial": {"latencies": probe_serial(host, count=5)},
        "http_parallel_%d" % parallel_small: {
            "latencies": probe_parallel(host, count=parallel_small)},
        "http_parallel_%d" % parallel_big: {
            "latencies": probe_parallel(host, count=parallel_big)},
        "modbus": modbus_probe(host),
    }
    for key in list(report):
        if isinstance(report[key], dict) and "latencies" in report[key]:
            report[key]["summary"] = summarize(report[key]["latencies"])
    from .client import HeliosClient
    client = HeliosClient(host, password)
    try:
        client.login()
        report["login"] = {"ok": True}
        report["batch_werte8"] = probe_batch(client, 8, count=3)
    except Exception as exc:  # noqa: BLE001
        report["login"] = {"ok": False, "error": str(exc)}
    finally:
        client.close()
    return report
