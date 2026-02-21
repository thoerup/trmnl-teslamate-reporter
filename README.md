# trmnl-teslamate-reporter

Forked from [eden881/trmnl-teslamate-reporter](https://github.com/eden881/trmnl-teslamate-reporter).

Use this to push data from a local Teslamate deployment to the TRMNL plugin via a webhook.

## Changes from upstream

- Added MQTT timeout handling — each topic now has a 5 second timeout, so the reporter no longer hangs indefinitely if a topic has no retained message (e.g. when the car is asleep)
- Added the following additional MQTT topics:
  - `inside_temp` — interior temperature in °C
  - `outside_temp` — exterior temperature in °C
  - `is_climate_on` — whether climate control is active
  - `is_preconditioning` — whether the car is actively preconditioning

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

## Usage

Build from this fork in your `docker-compose.yml`:
```yaml
trmnl-reporter:
  build:
    context: https://github.com/thoerup/trmnl-teslamate-reporter.git
  environment:
    - TZ=Europe/Copenhagen
    - WEBHOOK_URL=https://usetrmnl.com/api/custom_plugins/YOUR_TOKEN_HERE
  volumes:
    - /etc/localtime:/etc/localtime:ro
  depends_on:
    teslamate:
      condition: service_started
    mosquitto:
      condition: service_started
```

This configuration assumes you have the MQTT feature in Teslamate enabled, named
the broker's service `mosquitto`, and named the main app `teslamate`.

Replace `WEBHOOK_URL` with your own URL from the plugin's page on the TRMNL dashboard.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `MQTT_BROKER` | `mosquitto` | MQTT broker hostname |
| `MQTT_PORT` | `1883` | MQTT broker port |
| `MQTT_USERNAME` | | MQTT username (if required) |
| `MQTT_PASSWORD` | | MQTT password (if required) |
| `WEBHOOK_URL` | | TRMNL webhook URL (required) |
| `CAR_ID` | `1` | Teslamate car ID |
| `FETCH_FREQUENCY` | `15` | How often to fetch data, in minutes |
