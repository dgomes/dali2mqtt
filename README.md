# dali2mqtt
DALI &lt;-> MQTT bridge

## About

This daemon is inspired in [zigbee2mqtt](https://github.com/Koenkk/zigbee2mqtt) and provides the means to integrate a DALI light controller into your Home Assistant setup.

Previously I developed a Home Assistant custom component (https://github.com/dgomes/home-assistant-custom-components/tree/master/light) but I've since decided to run Home Assistant in another device, away from the physical DALI Bus.

## How to use

### Create a Virtual Environment (recommended) and install the requirements
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Create a configuration file
You can create a configuration file when you call the daemon the first time

```bash
venv/bin/python3 ./dali-mqtt-daemon.py
```

Then just edit the file accordingly. You can also create the file with the right values, by using the arguments of dali-mqtt-daemon.py:

```
  --config CONFIG       configuration file
  --mqtt-server MQTT_SERVER
                        MQTT server
  --mqtt-port MQTT_PORT
                        MQTT port
  --mqtt-base-topic MQTT_BASE_TOPIC
                        MQTT base topic
  --dali-driver {hasseb,tridonic,dali_server}
                        DALI device driver
  --dali-lamps DALI_LAMPS
                        Number of lamps to scan
  --ha-discover-prefix HA_DISCOVER_PREFIX
                        HA discover mqtt prefix
```

### Setup systemd
edit dali2mqtt.service and change the path of python3 to the path of your venv, after:

```bash
sudo cp dali2mqtt.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable dali2mqtt.service 
```

### Give your user permissions to access the USB device
```bash
sudo adduser homeassistant plugdev 
cp 50-hasseb.rules /etc/udev/rules.d/
```
You might need to reboot your device after the last change.

In this example the user is **homeassistant**

### Check everything is OK
```bash
sudo systemctl start dali2mqtt.service 
sudo systemctl status dali2mqtt.service 
```

### Command line arguments and configuration file

When the daemon first runs, it creates a default `config.ini` file.
You can edit the file to customize your setup.
