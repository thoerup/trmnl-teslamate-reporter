import os
import logging
import schedule
import time
import requests
import paho.mqtt.subscribe as subscribe
from zoneinfo import ZoneInfo      
from datetime import datetime  

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("trmnl-teslamate-reporter")

# Load dev environment variables if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Get configuration from environment variables
FETCH_FREQUENCY = int(os.environ.get("FETCH_FREQUENCY", "15"))
MQTT_BROKER = os.environ.get("MQTT_BROKER", "mosquitto")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_USER = os.environ.get("MQTT_USERNAME")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
CAR_ID = int(os.environ.get("CAR_ID", "1"))

def fetch_data_mqtt():
    """Fetch data from MQTT"""
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
    """Post data to webhook endpoint"""
    if not data:
        logger.warning("No data to send")
        return
    payload = {
        "merge_variables": data
    }
    try:
        logger.debug(f"POSTing payload: {payload}")
        response = requests.post(WEBHOOK_URL, json=payload)
        if response.status_code == 200:
            logger.info(f"Successfully posted {len(data)} records to webhook")
        else:
            logger.error(f"Webhook post failed with status {response.status_code}: {response.text}")
    except Exception as e:
        logger.error(f"Error posting to webhook: {e}")

def report_data():
    """Main function to report data from MQTT to webhook"""
    logger.info("Starting data reporter job")
    data = fetch_data_mqtt()
    if data:
        post_to_webhook(data)
        logger.info("Data reporter job completed")
    else:
        logger.warning("Data reporter job failed")

def start_scheduler():
    """Set up and start the scheduler"""
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
    if not WEBHOOK_URL:
        logger.critical("WEBHOOK_URL environment variable is not set. Exiting.")
        exit(1)
    logger.info("Reporter service starting up")
    start_scheduler()
