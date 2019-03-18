# aiotuya

aiotuya ia a Python library for LAN control of Tuya devices. It can detect, provision
and control devices that connect to the [Tuya Cloud](https://www.tuya.com).

To make things easy to the user, aiotuya comes with an application key and secret
that were provided by [Tuya Cloud](https://www.tuya.com). We request that you
do not use these key and secret for any other purpose.

# Acknowledgement

All credits for figuring out how those device communicate goes to [codetheweb](https://github.com/codetheweb/tuyapi)
and all the participants to this [conversation](https://github.com/codetheweb/tuyapi/issues/5). All I did is
port their work to Python with asyncio and added bugs.

# Installation

Coming soon... we will upload to Pypi

In the meantime....

``` shell
python3 setup.py install
```

# Usage

The easiest way to start is running the module

``` shell
python3 -m aiotuya
```

Which, the first time around, will give you absolutely nothing. You want to
start with

``` shell
python3 -m aiotuya -e me@myself.com -p mypass -s WIFISSID -P WIFISECRET
```

After you hit the "Enter" you should get

``` shell
Hit "Enter" to start
Use Ctrl-C to quit

Select Device:

            [0]     Provision new devices
```


Ready you devices for configuration and hit 0 followed by enter.

Then wait, hiting the "Enter" key from time to time.

You can also use the '-d' option to get debug messages. These are not suitable for human consumption and are
known to cause cancer in rats.

## Provisioning Caveat

For provisioning to work, you must be able to send broadcast packets over WiFi.
In my case, I was only able to use provisioning on a laptop connected to my
house WiFi. Trying from a wired computer did not work. Apparently my router (Asus RT-AC5300)
did not relay the packets. Your milage may vary.

Provisioning is also working on a RPi3 connected through WiFi (Note that I use a USB WiFi dongle to
connect, not the RPi3 WiFi module)

Provisioning is NOT YET working from a RPi2 (wire connected) with a WiFi dongle.


## Remembering devices keys

During the provisioning process, the device will register with the [Tuya Cloud](https://www.tuya.com).
Once the registration has succeeded, the provisioning system will receive a key to be used
when communicating with the device. By default, aiotuya will save the pairs (device id, key) in a CSV file
in your home directory. The default file name is .aiotuya

# The devices

At this time (Feb '19) aiotuya will handle 3 types of devices

## Switch

A simple On/Off switch is provided by ``` TuyaSwitch ``` . It has 2 methods:

* on()
* off()

And the status will be reported as

``` python
{'state': 'on'}
{'state': 'off'}
```

## Open/Close/Idle Switch

This is the kind of switch that can be used for curtains, garage doors and so on. It is
provided with ``` TuyaOCSwitch ```.  It has 3 methods:

* open()
* close()
* idle()

And the state value can be one of:

* closing
* opening
* idling

## LED lights

This is a colour LED light. It is provided by  ``` TuyaLight ``` and offers the following methods:

* on()
* off()
* set_white( brightness, K)
* set_colour([hue, saturation, value])
* set_colour_rgb([pred, green, blue])
* transition_white([bright, K], duration)
* transition_colour([h, s, v], duration)
* fadein_white(bright, K, duration)
* fadeout_white(duration)
* fadein_colour([h, s, v], duration)
* fadeout_colour(duration)

## Other Devices

Other devices can be added, but I do not have the information needed to add them.

## Devices caveat

aiotuya keeps a connection to the device, and send a heartbeat status request every timout secs
(10 secs by default). This allows it to receive real time status messages upon changes in the device status
(e.g. button pressed on a switch). The downside is that Tuya devices seem to only accept one such a
connection, so aiotuya has exclusive control of the device via LAN. Fortunately, the devices stop broacasting their presence
when they have a network connection, so other application should not be able to find them. I have not tried to see if the
cloud API was still working in that case.

# How to use aiotuya

Create a class to manage your devices. The class should have at least 4 methods:

* register(self, device)
  This will be used to report when a new device has been found.
* unregister(self,device)
  This is called when connection to a device is lost.
* got_data(self, data)
  This is called when a device receive data. The data should be a dictionary. The 'devId' can be used to iscriminate which device received the data
* got_error(self, device, data)
  This is called when an error is received. The device is passed as parameter.


Subclass TuyaManager, if you want to persists the device keys, by overloading 2 methods:

* load_keys(self)
  Loading the known keys in the dictionary self.known_devices. called in __init__
* persist_keys(self)
  Save the keys, called when new keys are reported.

After that

``` python
MyDevs= Devices()
loop = aio.get_event_loop()
manager = DevManager(dev_parent=MyDevs)
scanner = tuya.TuyaScanner(parent=manager)
scanner.start(loop)
```
## How does it work

Tuya devices, when they are not connected, broadcast their presence on the network, TuyaScanner listen
for those broadcasts and pass them on to TuyaManager.

If the key is known, TuyaManager will create a TuyaDevice generic instance with raw_dps set, using itself as device manager.
Upon receiving the device status data, Tuyamanager will try to figure out the type of device and create the proper instance
using the application device manager to control the device.

TuyaManager figures out the type of device it is dealing with by issuing a status request and inspecting the returned value.
If an error is returned, ot will try sending a command. The reason for this is that my OC Switch, after powering up, will return
a "json struct data unvalid" error to any status request until either, a button is pressed or a valid command is issued. The behaviour
of Tuyamanager is meant to circumvent this problem.

# Status

0.1.0b1: Initial version. Works for me with a LED lightbulb and a Open/Close switch
