import paho.mqtt.client as mqtt
import os

mqtt_broker = os.getenv('mqtt_broker')
mqtt_port = os.getenv('mqtt_port')

# Callback for når klienten kobler til broker
def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    topic = "test/topic"  # Samme topic som publisher
    client.subscribe(topic)  # Abonner på topic
    print(f"Subscribed to topic: {topic}")

# Callback for når en melding mottas
def on_message(client, userdata, msg):
    print(f"Received message: '{msg.payload.decode()}' on topic: '{msg.topic}'")

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

try:
    client.connect(mqtt_broker, mqtt_port, 60)
    print("Connected to MQTT broker")
    client.loop_forever()  # Blokkerer og lytter etter meldinger
except Exception as e:
    print(f"Failed to connect: {e}")
