# trmnl-teslamate-reporter

Forked from [eden881/trmnl-teslamate-reporter](https://github.com/eden881/trmnl-teslamate-reporter).

Use this to push data from a local Teslamate deployment to the TRMNL plugin via a webhook.

## Changes from upstream

- Added MQTT timeout handling — each topic now has a 5 second timeout, so the reporter no longer hangs indefinitely if a topic has no retained message (e.g. when the car is asleep)
- Added `last_updated` field — timestamp of when data was last successfully fetched, in local time
- Added `since` field — timestamp of when the car last changed state, converted to local time (DST-aware via `TZ` environment variable)
- Added the following additional MQTT topics:
  - `inside_temp` — interior temperature in °C
  - `outside_temp` — exterior temperature in °C
  - `is_climate_on` — whether climate control is active
  - `is_preconditioning` — whether the car is actively preconditioning
  - `since` — timestamp of last state change

## Exposed Variables

The following variables are posted to the TRMNL webhook and available in your plugin template:

| Variable | Example | Description |
|---|---|---|
| `state` | `online` | Vehicle state (online, asleep, offline, charging, driving) |
| `battery_level` | `71` | Battery level percentage |
| `rated_battery_range_km` | `290` | Rated range in km |
| `display_name` | `Manse` | Vehicle name |
| `odometer` | `26222` | Odometer in km |
| `version` | `2026.2.3` | Software version |
| `charger_voltage` | `230` | Charger voltage (V) |
| `charger_power` | `11` | Charger power (kW) |
| `inside_temp` | `20.5` | Interior temperature (°C) |
| `outside_temp` | `1.0` | Exterior temperature (°C) |
| `is_climate_on` | `true` | Whether climate control is on |
| `is_preconditioning` | `false` | Whether car is preconditioning |
| `since` | `10:19` | Local time of last state change |
| `last_updated` | `10:37` | Local time data was last fetched |

## Example Quadrant Template

A morning-focused quadrant template showing battery, climate and temperatures:
```html
