import hashlib
import base64
import os
import logging
import paho.mqtt.client as mqtt
import requests
from paho.mqtt.properties import Properties
from paho.mqtt.packettypes import PacketTypes

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

# Function to generate SCRAM client-first-message
def generate_scram_message(username):
    logger.debug(f"Generating SCRAM client-first-message for username: {username}")
    client_nonce = base64.b64encode(os.urandom(16)).decode()  # Random client nonce
    client_first_message = f"n={username},r={client_nonce}"
    logger.debug(f"Generated client-first-message: {client_first_message}")
    return client_first_message, client_nonce

# Function to hash password with salt and iterations using PBKDF2 (SCRAM-specific)
def scram_hash(password, salt, iterations):
    logger.debug(f"Hashing password with salt: {salt} and iterations: {iterations}")
    hashed = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), base64.b64decode(salt), iterations)
    logger.debug(f"Generated hashed password: {base64.b64encode(hashed).decode()}")
    return hashed

# MQTT broker settings
mqtt_broker = os.getenv('mqtt_broker')
mqtt_port = os.getenv('mqtt_port')
mqtt_user = os.getenv('mqtt_user')
mqtt_pass = os.getenv('mqtt_pwd')

device_series_number = os.getenv('device_series_number')

# MQTT topics based on the device serial number
toggle_topic = f"{device_series_number}/toggle"
status_topic = f"{device_series_number}/status"

# SCRAM authentication setup
client_first_message, client_nonce = generate_scram_message(mqtt_user)

# Properties for CONNECT with Authentication Method and Initial Data
connect_properties = Properties(PacketTypes.CONNECT)
connect_properties.AuthenticationMethod = "SCRAM-SHA-256"
connect_properties.AuthenticationData = client_first_message.encode()

# External service URL for authentication
auth_service_url = "https://your-auth-service-url.com/authenticate"

# Function to get authentication data from external HTTP service
def get_authentication_data(username):
    try:
        response = requests.post(auth_service_url, json={"username": username})
        if response.status_code == 200:
            data = response.json()
            logger.debug(f"Received authentication data: {data}")

            # Extract required data from the response
            stored_key = data['stored_key']
            server_key = data['server_key']
            salt = data['salt']
            iterations = data.get('iterations', 4096)  # Default to 4096 if not provided
            is_superuser = data.get('is_superuser', False)
            acl = data.get('acl', [])
            expire_at = data.get('expire_at', None)

            return stored_key, server_key, salt, iterations, is_superuser, acl, expire_at
        else:
            logger.error(f"Failed to get authentication data from service. Status code: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Error while getting authentication data: {e}")
        return None

# Callback for connection status
def on_connect(client, userdata, flags, rc, reason_code=None, properties=None):
    logger.debug(f"Received connection callback with return code: {rc}")
    if rc == 0:
        logger.info("Connected successfully to MQTT broker.")
        publish_status_message(client, status_topic, "Device connected successfully.")
    else:
        logger.error(f"Failed to connect to MQTT broker, return code {rc}")
        publish_status_message(client, status_topic, f"Connection failed: return code {rc}")
        if reason_code:
            logger.error(f"Reason code: {reason_code}")

# Callback for authentication (for MQTT v5 SCRAM sequence)
def on_auth(client, userdata, reason_code, properties=None):
    logger.debug(f"Received authentication callback with reason code: {reason_code}")
    if reason_code == 0:  # Continue SCRAM handshake if needed
        server_first_message = properties.AuthenticationData.decode()
        logger.info(f"Server First Message: {server_first_message}")
        try:
            # Extract salt and iterations from server's first message
            server_salt = server_first_message.split(',')[0].split('=')[1]
            iterations = int(server_first_message.split(',')[1].split('=')[1])
            logger.debug(f"Extracted server salt: {server_salt}, iterations: {iterations}")

            # Get authentication data from external service
            auth_data = get_authentication_data(mqtt_user)
            if auth_data:
                stored_key, server_key, salt, iterations, is_superuser, acl, expire_at = auth_data

                # Hash the password with the server's salt and iterations
                hashed_password = scram_hash(mqtt_pass, salt, iterations)

                # Prepare the client-final-message
                client_final_message = f"c=biws,r={client_nonce},p={base64.b64encode(hashed_password).decode()}"
                logger.debug(f"Generated client-final-message: {client_final_message}")

                auth_properties = Properties(PacketTypes.AUTH)
                auth_properties.AuthenticationData = client_final_message.encode()
                logger.debug(f"Sending AuthenticationData: {client_final_message}")
                client.reauthenticate(auth_properties)
        except Exception as e:
            logger.error(f"Error during authentication: {e}")
            publish_status_message(client, status_topic, "Authentication failed.")
    else:
        logger.error(f"Authentication failed with reason code {reason_code}.")
        publish_status_message(client, status_topic, "Authentication failed.")

# Callback for message handling
def on_message(client, userdata, message):
    logger.info(f"Received message: {message.payload.decode()} on topic {message.topic}")

# Function to publish a status message
def publish_status_message(client, status_topic, message):
    client.publish(status_topic, message)
    logger.info(f"Published status message: '{message}' to topic: {status_topic}")

# Initialize MQTT client
client = mqtt.Client(client_id=f"client_{device_series_number}", protocol=mqtt.MQTTv5)
client.on_connect = on_connect
client.on_message = on_message
client.on_auth = on_auth

# Connect with SCRAM properties
logger.info("Attempting to connect with SCRAM...")
client.connect(mqtt_broker, mqtt_port, properties=connect_properties)

# Start loop
client.loop_start()

try:
    while True:
        command = input("Enter command (1=toggle, 2=status): ")
        if command == '1':
            client.publish(toggle_topic, "toggle")
            logger.info(f"Published 'toggle' to {toggle_topic}")
        elif command == '2':
            publish_status_message(client, status_topic, "Status check: Device operational.")
        else:
            logger.warning("Invalid command")
except KeyboardInterrupt:
    logger.info("Exiting...")
    publish_status_message(client, status_topic, "Device disconnecting...")
    client.loop_stop()
    client.disconnect()
