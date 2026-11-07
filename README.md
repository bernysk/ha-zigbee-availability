# Zigbee Availability

Get notified when a **ZHA** Zigbee device stays unavailable longer than a set time,
and again when it comes back. Set it up in the UI and exclude devices by picking them
or by putting a label on them.

> **ZHA only for now.** Zigbee2MQTT support is planned. If you use Z2M and can test,
> contributions are welcome.

## What it does

- Checks every ZHA device every 30 seconds. A device counts as **unavailable** when
  *all* of its enabled ZHA entities are `unavailable`, so one flaky entity doesn't trigger
  an alert. The timeout starts when the *last* entity goes unavailable. A device counts as
  back only once an entity reports a real value; `unknown` doesn't count, so startup
  doesn't produce false "back online" messages.
- When a device has been unavailable longer than your **timeout**, it sends **one**
  message. Devices that cross the timeout together are grouped into a single message.
- Optionally sends a **"back online"** message with how long the device was gone.
- Optionally keeps a **persistent notification** in HA listing every device that is
  offline right now. It disappears when everything is back.
- Survives restarts. Timers and the "already alerted" state are stored, so a restart
  neither resets the countdown nor repeats an alert.

## Installation

### Marketplace (HACS)

1. In Home Assistant, open the **Marketplace** (or HACS on versions before 2026.11).
2. Add `https://github.com/bernysk/ha-zigbee-availability` as a **custom repository**,
   category **Integration**.
3. Install **Zigbee Availability** and restart Home Assistant.

### Manual

Copy `custom_components/zigbee_availability` into your `config/custom_components/`
folder and restart Home Assistant.

## Setup

**Settings → Devices & services → Add integration → Zigbee Availability**

| Option | Default | Description |
|---|---|---|
| Timeout | 15 min | How long a device must be unavailable before you're notified. |
| Notify targets | none | Notify services such as `notify.mobile_app_phone`, or notify entities. You can pick several. |
| Notify when a device comes back | on | Sends a recovery message for devices you were alerted about. |
| Show a persistent notification | on | Keeps a list of offline devices in the HA notification panel. |
| Excluded devices | none | ZHA devices that are never monitored. |
| Excluded labels | none | Devices with one of these labels are not monitored. Entities with one of these labels are left out when deciding whether their device is unavailable. |

You can change everything later under **Configure** on the integration.

> **Tip:** create a label such as `No unavailable alert`, select it under *Excluded
> labels*, and from then on you can exclude any device from its device page without
> reopening these settings.

### The timeout adds to ZHA's own timeout

ZHA only marks a device unavailable after it hasn't heard from it for a while. By default
that's about **2 hours for mains-powered** and **6 hours for battery** devices. You can
change these in the ZHA integration's options (*Configure → Global options*). Your
timeout here starts counting once ZHA has marked the device unavailable.

Suggested settings:

| | ZHA setting | Notes |
|---|---|---|
| Mains-powered | 600–1800 s | ZHA actively checks these, so a short value is safe. |
| Battery | 10800–21600 s (default) | Many sensors only check in every 1–4 h. Lower values cause false alarms. |

With mains at 900 s in ZHA and a 5-minute timeout here, you hear about a dead plug after
about 20 minutes.

## Test notification

The integration's device page has a **Send test notification** button. It sends a test
message to every notify target and shows an error naming any target that failed, such
as a renamed phone. Press it after setup and whenever you change targets. You can also
call `button.press` on `button.zigbee_availability_send_test_notification` from an
automation.

## Sensor

`sensor.zigbee_availability_unavailable_devices`: the number of devices past the
timeout.

| Attribute | Content |
|---|---|
| `devices` | Devices past the timeout: `device_id`, `name`, `since` |
| `pending` | Devices unavailable but not yet past the timeout |
| `timeout_minutes` | The configured timeout |

Example dashboard card:

```yaml
type: markdown
content: >
  {% for d in state_attr('sensor.zigbee_availability_unavailable_devices', 'devices') %}
  - **{{ d.name }}** since {{ as_timestamp(d.since) | timestamp_custom('%d.%m. %H:%M') }}
  {% else %}
  All Zigbee devices online.
  {% endfor %}
```

## Events

Use these for your own automations, for example to send a TTS announcement or create a
to-do item.

| Event | Data |
|---|---|
| `zigbee_availability_device_unavailable` | `device_id`, `name`, `since` |
| `zigbee_availability_device_available` | `device_id`, `name`, `since`, `duration_seconds` |

```yaml
triggers:
  - trigger: event
    event_type: zigbee_availability_device_unavailable
actions:
  - action: tts.speak
    target:
      entity_id: tts.home_assistant_cloud
    data:
      media_player_entity_id: media_player.kitchen
      message: "{{ trigger.event.data.name }} is offline."
```

## Compared to a template sensor

The popular
[Unavailable Entities Sensor](https://github.com/jazzyisj/unavailable-entities-sensor)
package lists *every* entity that is `unknown` or `unavailable` across your whole
setup, which is good for general cleanup. This integration does one narrower job:

- It works per **device**, not per entity, so a dead plug is one alert, not five.
- It **sends alerts**: one message per outage, plus recovery, instead of a list you
  build notifications around yourself.
- It **survives restarts**. Template sensors rely on `last_changed`, which resets on every
  restart, so timers start over.
- It is set up in the UI. You don't need to edit YAML, run `jq` on `.storage` files or
  enable packages.

## Development

Tests use
[pytest-homeassistant-custom-component](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component)
and need Linux or macOS, because HA's test runner doesn't work on Windows.

```bash
pip install -r requirements_test.txt
ruff check . && ruff format --check .
pytest
```

## License

MIT
