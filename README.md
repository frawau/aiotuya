# aiotuya

aiotuya ia a Python library for LAN control of Tuya devices. It can detect, provision
and control devices that connect to the [Tuya Cloud](https://www.tuya.com).

To make things easy to the user, aiotuya comes with an application id and key
that were provided by [Tuya Cloud](https://www.tuya.com). We request that you
do not use these id and key for any other purpose.

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

The wait, hiting the "Enter" key from time to time.

## Provisioning Caveat

For provisioning to work, you must be able to send broadcast packets over WiFi.
In my case, I was only able to use provisioning on a laptop connected to my
house WiFi. Trying from a wired computer did not work. Apparently my router (Asus RT-5300)
did not relay the packets. Your milage may vary.

## Remembering devices keys

During the provisioning process, the device will register with the [Tuya Cloud](https://www.tuya.com).
Once the registration has succeeded, the provisioning system will receive a key to be used
when communicating with the device. By default, aiotuya will save the pairs (device id, key) in a CSV file
in your home directory. The default file name is .aiotuya

# The devices

At this time aiotuya will gandle 3 types of devices

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
    ^ idle()

And the state value can be one of:
    ^ closing
    * opening
    * idling

## LED lights

This is a colour LED light. It is provided by  ``` TuyaLight ``` and offers the following methods:
    ^ on()
    * off()
    * set_white( brightness, Temperature)
    * set_colour([hue, saturation, value])
    * set_colour_rgb(pred, green, blue])
    * transition_white([bright, K], duration)
    * transition_colour([h, s, v], duration)
    * fadein_white(bright, K, duration)
    * fadeout_white(duration)
    * fadein_colour([h, s, v], duration)
    * fadeout_colour(duration)

## Other Devices

Other devices can be added, but I do not have the information needed to add them.





