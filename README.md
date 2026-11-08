# homeassistant-helios

A custom component for Home Assistant to connect Helios ventilation
systems (easyControls). Tested on Helios KWL EC 300 W, 340D and 500W R;
most functions will work on other Helios devices.

![Example screenshot](screenshot.png)

## What changed vs. the old eazyctrl-based version

The easyControls webserver serves connections **serially with roughly
one request/second** sustained throughput (measured on a KWL EC 500W R:
16 parallel requests quantize into ~1s/2s/3s/5s steps). The old
integration sent one Modbus/TCP request pair per variable, every 5
seconds, plus two unconditional writes per cycle - which is what made
the unit slow to answer and eventually hang.

The new client (`helioslib`, bundled with the component, pure stdlib):

* polls **one generated batch page** (`werte8.xml`, 103 variables)
  per cycle - the same mechanism the stock web UI uses
* **writes only on change**, mode + stage batched into one request
* defaults to a **20 s** polling interval (5-600 s via Options)
* validates the login during config flow (password field added)

## Layout

* `custom_components/helios/helioslib/` - the client library
  (`client.py` HTTP batch protocol, `variables.py` page/variable map,
  `probe.py` probe + regression harness). Usable outside Home
  Assistant; no external dependencies.
* `custom_components/helios/*.py` - thin Home Assistant plumbing that
  only calls the library.
* `../tools/test_client.py` (repo root) - CLI test client: page
  discovery, probe, monitoring, and a regression harness for verifying
  firmware patches.

## Installation

1. Make sure your Helios has been connected to the local network and
   you know its IP address.

2. Install **Helios ventilation** via HACS or copy the
   `custom_components/helios` folder to your Home Assistant
   `/config/custom_components/` folder.

3. Restart Home Assistant, go to Settings > Devices & Services >
   Add Integration and select **Helios**.

4. Enter host, name, and the web interface password (the device
   default is `!helios!`).

## Service: `helios.fan_boost`

Temporarily run the fan at a boost speed, then restore the previous
stage:

```yaml
service: helios.fan_boost
data:
  entity_id: fan.helios
  speed: high      # off | low | medium | high | max
  duration: 60     # minutes
```

## Firmware patch verification (tools)

The test client doubles as a regression harness for firmware work on
the unit:

```sh
python3 tools/test_client.py regression --out baseline.json
python3 tools/test_client.py probe --parallel 16
python3 tools/test_client.py monitor --interval 20 --count 100
```

Record a `baseline.json` on the stock firmware, re-run after flashing a
patched image and diff the reports (serial/parallel latencies, batch
read latency, Modbus/TCP gateway status).

## Feedback

Feedback, pull requests and any other contribution are welcome. Please
let me know how it works on other Helios models.

