import paho.mqtt.client as mqtt
import os

# MQTT broker settings
mqtt_broker = os.getenv('mqtt_broker')
mqtt_port = os.getenv('mqtt_port')
mqtt_user = os.getenv('mqtt_user')
mqtt_pass = os.getenv('mqtt_pwd')

device_series_number = os.getenv('device_series_number')


# MQTT topic and message
TOPIC = f"{device_series_number}/status"
MESSAGE = "Hello, MQTT with SCRAM-SHA-256"

# SCRAM Authentication Method
AUTH_METHOD = "SCRAM-SHA-256"

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print(f"Connected successfully to {mqtt_broker}:{mqtt_port}")
        client.publish(TOPIC, MESSAGE)
        print(f"Message '{MESSAGE}' published to topic '{TOPIC}'")
    else:
        print(f"Connection failed with reason code: {reason_code}")

def on_publish(client, userdata, mid):
    print(f"Message ID: {mid} published successfully!")

# Create MQTT client with protocol version 5
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, protocol=mqtt.MQTTv5)

# Set username and password for SCRAM authentication
client.username_pw_set(mqtt_user, mqtt_pass)

# Assign event callbacks
client.on_connect = on_connect
client.on_publish = on_publish

# Connect to the broker
client.connect(mqtt_broker, mqtt_port)

# Start the network loop to process callbacks
client.loop_forever()
