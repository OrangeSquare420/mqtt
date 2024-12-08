import paho.mqtt.client as mqtt
import hashlib
import base64
import unicodedata
from paho.mqtt.properties import Properties
from paho.mqtt.packettypes import PacketTypes

# Funksjon for å normalisere strenger (brukernavn og passord)
def normalize_string(input_string):
    return unicodedata.normalize('NFKC', input_string)

# Funksjon for å beregne client-first-message for SCRAM
def generate_scram_message(username, password):
    username = normalize_string(username)
    password = normalize_string(password)
    client_nonce = base64.b64encode(b"random-client-nonce").decode()
    client_first_message = f"n={username},r={client_nonce}"
    hashed_password = hashlib.sha256(password.encode('utf-8')).hexdigest()
    
    # Logge client_first_message for å se hva som blir sendt til serveren
    print(f"Client First Message: {client_first_message}")
    
    return client_first_message, hashed_password, client_nonce

# Funksjon for å publisere statusmelding
def publish_status_message(client, status_topic, message):
    print(f"Publishing to topic {status_topic}: {message}")  # Logge dataen som publiseres
    client.publish(status_topic, message)
    print(f"Published status message: '{message}' to topic: {status_topic}")

# MQTT Broker-innstillinger
mqtt_broker = "junction.proxy.rlwy.net"
mqtt_port = 11898
mqtt_user = "scram"
mqtt_pass = "scram"

# Enhetens serienummer
device_serial_number = "BKQ90NKC3D"

# MQTT-emner basert på enhetens serienummer
toggle_topic = f"{device_serial_number}/toggle"
status_topic = f"{device_serial_number}/status"

# SCRAM-autentisering
client_first_message, hashed_password, client_nonce = generate_scram_message(mqtt_user, mqtt_pass)

# Properties for CONNECT med autentiseringsmetode og initial data
connect_properties = Properties(PacketTypes.CONNECT)
connect_properties.AuthenticationMethod = "SCRAM-SHA-256"
connect_properties.AuthenticationData = client_first_message.encode()

# Callback for tilkobling
def on_connect(client, userdata, flags, rc, reason_code=None, properties=None):
    print(f"Connection return code: {rc}")
    if reason_code:
        print(f"Reason code: {reason_code}")
    if rc == 0:
        print("Connected successfully to MQTT broker.")
        publish_status_message(client, status_topic, "Device connected successfully.")
    else:
        print(f"Failed to connect to MQTT broker, return code {rc}")
        publish_status_message(client, status_topic, f"Connection failed: return code {rc}")

# Callback for autentisering (for MQTT v5 SCRAM-sekvens)
def on_auth(client, userdata, reason_code, properties=None):
    print(f"Authentication response received. Reason Code: {reason_code}")
    if properties and properties.AuthenticationData:
        server_first_message = properties.AuthenticationData.decode()
        
        # Logge server_first_message for å kontrollere hva serveren sender
        print(f"Server First Message: {server_first_message}")
    else:
        print("No AuthenticationData received from the server.")

    if reason_code == 0:
        client_final_message = f"c=biws,r={client_nonce},p={hashed_password}"
        
        # Logge client_final_message for å sjekke hva som sendes som siste autentiseringsmelding
        print(f"Client Final Message: {client_final_message}")
        
        auth_properties = Properties(PacketTypes.AUTH)
        auth_properties.AuthenticationData = client_final_message.encode()
        client.reauthenticate(auth_properties)
    else:
        print("Authentication failed.")
        publish_status_message(client, status_topic, "Authentication failed.")

# Callback for melding
def on_message(client, userdata, message):
    print(f"Received message: {message.payload.decode()} on topic {message.topic}")

# Initialiser MQTT-klient
client = mqtt.Client(client_id=f"client_{device_serial_number}", protocol=mqtt.MQTTv5)
client.on_connect = on_connect
client.on_message = on_message
client.on_auth = on_auth

# Koble til med SCRAM-egenskaper
print("Attempting to connect with SCRAM...")
client.connect(mqtt_broker, mqtt_port, properties=connect_properties)

# Start loop
client.loop_start()

try:
    while True:
        command = input("Enter command (1=toggle, 2=status): ")
        if command == '1':
            client.publish(toggle_topic, "toggle")
            print(f"Published 'toggle' to {toggle_topic}")
        elif command == '2':
            publish_status_message(client, status_topic, "Status check: Device operational.")
        else:
            print("Invalid command")
except KeyboardInterrupt:
    print("Exiting...")
    publish_status_message(client, status_topic, "Device disconnecting...")
    client.loop_stop()
    client.disconnect()
