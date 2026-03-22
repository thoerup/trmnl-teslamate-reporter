import os
import logging
import schedule
import time
import requests
import paho.mqtt.subscribe as subscribe
from zoneinfo import ZoneInfo
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("trmnl-teslamate-reporter")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

FETCH_FREQUENCY = int(os.environ.get("FETCH_FREQUENCY", "15"))
MQTT_BROKER = os.environ.get("MQTT_BROKER", "mosquitto")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_USER = os.environ.get("MQTT_USERNAME")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
CAR_ID = int(os.environ.get("CAR_ID", "1"))

# Terminus config
TERMINUS_URL = os.environ.get("TERMINUS_URL")
TERMINUS_EMAIL = os.environ.get("TERMINUS_EMAIL")
TERMINUS_PASSWORD = os.environ.get("TERMINUS_PASSWORD")
TERMINUS_MODEL_ID = os.environ.get("TERMINUS_MODEL_ID", "11")

_terminus_access_token = None
_terminus_refresh_token = None
_terminus_token_time = None

TERMINUS_TEMPLATE = """
<style>
  .tesla-card * {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  }}
  .big {{ font-size: 1.5rem; font-weight: 700; line-height: 1; }}
  .lbl {{ font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.08em; color: #666; margin-top: 3px; }}
  .battery-bar {{ width: 100%; height: 8px; background: #e0e0e0; border-radius: 4px; margin-top: 5px; }}
  .battery-fill {{ height: 8px; border-radius: 4px; background: #000; }}
  .spacer {{ height: 13px; }}
  .since {{ font-size: 0.6rem; color: #666; text-align: center; margin-top: 6px; grid-column: span 2; }}
</style>
<div class="view view--quadrant">
  <div class="layout layout--col gap--none tesla-card">
    <div class="grid grid--cols-2 gap--small w--full">
      <div class="flex flex--col">
        <span class="big">{battery_level}%</span>
        <div class="battery-bar">
          <div class="battery-fill" style="width: {battery_level}%;"></div>
        </div>
        <span class="lbl">Battery</span>
      </div>
      <div class="flex flex--col">
        <span class="big">{climate_status}</span>
        <div class="spacer"></div>
        <span class="lbl">Climate</span>
      </div>
      <div class="b-h-gray-5 w-full" style="grid-column: span 2; margin: 4px 0;"></div>
      <div class="flex flex--col">
        <span class="big">{inside_temp}°C</span>
        <span class="lbl">Inside</span>
      </div>
      <div class="flex flex--col">
        <span class="big">{outside_temp}°C</span>
        <span class="lbl">Outside</span>
      </div>
      <div class="since">State since {since} · Fetched {last_updated}</div>
    </div>
  </div>
  <div class="title_bar">
    <svg fill="#000000" width="20" height="20" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">
      <path fill="#FFFFFF" stroke="#FFFFFF" stroke-width="10" d="M16 7.151l3.302-4.036c0 0 5.656 0.12 11.292 2.74-1.443 2.182-4.307 3.25-4.307 3.25-0.193-1.917-1.536-2.385-5.807-2.385l-4.479 25.281-4.51-25.286c-4.24 0-5.583 0.469-5.776 2.385 0 0-2.865-1.057-4.307-3.24 5.635-2.62 11.292-2.74 11.292-2.74l3.302 4.031h-0.005zM16 1.953c4.552-0.042 9.766 0.703 15.104 3.036 0.714-1.292 0.896-1.859 0.896-1.859-5.833-2.313-11.297-3.109-16-3.13-4.703 0.021-10.167 0.813-16 3.13 0 0 0.26 0.703 0.896 1.865 5.339-2.344 10.552-3.083 15.104-3.047z"/>
      <path fill="#000000" d="M16 7.151l3.302-4.036c0 0 5.656 0.12 11.292 2.74-1.443 2.182-4.307 3.25-4.307 3.25-0.193-1.917-1.536-2.385-5.807-2.385l-4.479 25.281-4.51-25.286c-4.24 0-5.583 0.469-5.776 2.385 0 0-2.865-1.057-4.307-3.24 5.635-2.62 11.292-2.74 11.292-2.74l3.302 4.031h-0.005zM16 1.953c4.552-0.042 9.766 0.703 15.104 3.036 0.714-1.292 0.896-1.859 0.896-1.859-5.833-2.313-11.297-3.109-16-3.13-4.703 0.021-10.167 0.813-16 3.13 0 0 0.26 0.703 0.896 1.865 5.339-2.344 10.552-3.083 15.104-3.047z"/>
    </svg>
    <span class="title">Tesla</span>
    <span class="instance">{display_name}</span>
  </div>
</div>
"""


def terminus_login():
    global _terminus_access_token, _terminus_refresh_token, _terminus_token_time
    try:
        response = requests.post(
            f"{TERMINUS_URL}/login",
            json={"login": TERMINUS_EMAIL, "password": TERMINUS_PASSWORD},
            headers={"Content-Type": "application/json"}
        )
        if response.status_code == 200:
            data = response.json()
            _terminus_access_token = data["access_token"]
            _terminus_refresh_token = data["refresh_token"]
            _terminus_token_time = datetime.now()
            logger.info("Terminus login successful")
            return True
        else:
            logger.error(f"Terminus login failed: {response.status_code} {response.text}")
            return False
    except Exception as e:
        logger.error(f"Terminus login error: {e}")
        return False


def terminus_refresh():
    global _terminus_access_token, _terminus_refresh_token, _terminus_token_time
    try:
        response = requests.post(
            f"{TERMINUS_URL}/api/jwt",
            json={"refresh_token": _terminus_refresh_token},
            headers={
                "Authorization": f"Bearer {_terminus_access_token}",
                "Content-Type": "application/json"
            }
        )
        if response.status_code == 200:
            data = response.json()
            _terminus_access_token = data["access_token"]
            _terminus_refresh_token = data["refresh_token"]
            _terminus_token_time = datetime.now()
            logger.info("Terminus token refreshed")
            return True
        else:
            logger.warning("Terminus token refresh failed, re-logging in")
            return terminus_login()
    except Exception as e:
        logger.error(f"Terminus token refresh error: {e}")
        return False


def terminus_get_token():
    global _terminus_token_time
    if _terminus_access_token is None:
        return terminus_login()
    age = (datetime.now() - _terminus_token_time).total_seconds()
    if age > 1500:
        return terminus_refresh()
    return True


def render_html(data):
    is_preconditioning = data.get("is_preconditioning", "false")
    is_climate_on = data.get("is_climate_on", "false")

    if is_preconditioning == "true":
        climate_status = "Heating"
    elif is_climate_on == "true":
        climate_status = "✓ Warm"
    else:
        climate_status = "Off"

    return TERMINUS_TEMPLATE.format(
        battery_level=data.get("battery_level", "?"),
        climate_status=climate_status,
        inside_temp=data.get("inside_temp", "?"),
        outside_temp=data.get("outside_temp", "?"),
        since=data.get("since", "?"),
        last_updated=data.get("last_updated", "?"),
        display_name=data.get("display_name", "Tesla"),
    )


def post_to_terminus(data):
    if not terminus_get_token():
        logger.error("Could not get Terminus token, skipping")
        return

    html = render_html(data)

    try:
        response = requests.post(
            f"{TERMINUS_URL}/api/screens",
            json={
                "screen": {
                    "model_id": TERMINUS_MODEL_ID,
                    "label": "Tesla",
                    "name": "tesla",
                    "content": html
                }
            },
            headers={
                "Authorization": f"Bearer {_terminus_access_token}",
                "Content-Type": "application/json"
            }
        )
        if response.status_code == 200:
            logger.info("Successfully posted Tesla screen to Terminus")
        else:
            logger.error(f"Terminus screen post failed: {response.status_code} {response.text}")
    except Exception as e:
        logger.error(f"Error posting to Terminus: {e}")


def fetch_data_mqtt():
    results = {}
    topics = [
        f"teslamate/cars/{CAR_ID}/state",
        f"teslamate/cars/{CAR_ID}/battery_level",
        f"teslamate/cars/{CAR_ID}/rated_battery_range_km",
        f"teslamate/cars/{CAR_ID}/version",
        f"teslamate/cars/{CAR_ID}/odometer",
        f"teslamate/cars/{CAR_ID}/display_name",
        f"teslamate/cars/{CAR_ID}/charger_power",
        f"teslamate/cars/{CAR_ID}/charger_voltage",
        f"teslamate/cars/{CAR_ID}/inside_temp",
        f"teslamate/cars/{CAR_ID}/outside_temp",
        f"teslamate/cars/{CAR_ID}/is_climate_on",
        f"teslamate/cars/{CAR_ID}/is_preconditioning",
        f"teslamate/cars/{CAR_ID}/since",
    ]

    auth = None
    if MQTT_USER and MQTT_PASSWORD:
        auth = {"username": MQTT_USER, "password": MQTT_PASSWORD}

    for topic in topics:
        result = [None]

        def fetch(t=topic, r=result):
            try:
                msg = subscribe.simple(t, hostname=MQTT_BROKER, port=MQTT_PORT, auth=auth, keepalive=1)
                if msg and msg.payload:
                    r[0] = msg.payload.decode().strip()
            except Exception as e:
                logger.error(f"Could not get MQTT topic {t}: {e}")

        import threading
        thread = threading.Thread(target=fetch)
        thread.start()
        thread.join(timeout=5)

        if result[0] is not None:
            key = topic.split("/")[-1]
            results[key] = result[0]
        else:
            logger.warning(f"Timeout or no data for topic {topic}, skipping")

    if "since" in results:
        try:
            utc_time = datetime.fromisoformat(results["since"].replace("Z", "+00:00"))
            local_time = utc_time.astimezone(ZoneInfo(os.environ.get("TZ", "UTC")))
            results["since"] = local_time.strftime("%H:%M")
        except Exception as e:
            logger.warning(f"Could not convert since timestamp: {e}")

    results["last_updated"] = datetime.now(ZoneInfo(os.environ.get("TZ", "UTC"))).strftime("%H:%M")
    return results


def post_to_webhook(data):
    if not data:
        logger.warning("No data to send")
        return

    payload = {"merge_variables": data}

    try:
        response = requests.post(WEBHOOK_URL, json=payload)
        if response.status_code == 200:
            logger.info(f"Successfully posted {len(data)} records to webhook")
        else:
            logger.error(f"Webhook post failed with status {response.status_code}: {response.text}")
    except Exception as e:
        logger.error(f"Error posting to webhook: {e}")


def report_data():
    logger.info("Starting data reporter job")
    data = fetch_data_mqtt()

    if data:
        if WEBHOOK_URL:
            post_to_webhook(data)
        if TERMINUS_URL:
            post_to_terminus(data)
    else:
        logger.warning("Data reporter job failed - no data")

    logger.info("Data reporter job completed")


def start_scheduler():
    logger.info("Starting scheduler")
    schedule.every(FETCH_FREQUENCY).minutes.do(report_data)
    report_data()

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user (CTRL+C). Exiting gracefully.")
        exit(0)


if __name__ == "__main__":
    if not WEBHOOK_URL and not TERMINUS_URL:
        logger.critical("Neither WEBHOOK_URL nor TERMINUS_URL is set. Exiting.")
        exit(1)

    logger.info("Reporter service starting up")
    start_scheduler()
