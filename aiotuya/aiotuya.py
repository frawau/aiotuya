#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#
# This module provides a library to control Tuya devices over the LAN
# The various devices expose the functions of the devices in a developper-friendly
# way. Note that in order to be able to set the devices, a key must be lnown. the
# key can be aquired by using the provisioning functions.
#
# Copyright (c) 2019 François Wautier
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
# of the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies
# or substantial portions of the Software.
#
# Portion of this code is covered by the following license
#
# Copyright 2003 Paul Scott-Murphy, 2014 William McBrine
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR
# IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# Lesser General Public License for more details.

# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301
# USA

import sys
import logging

import asyncio as aio
import base64
import json
from collections import OrderedDict
from colorsys import hsv_to_rgb, rgb_to_hsv
from Crypto.Cipher import AES
from hashlib import md5
from time import time

MAXNORESP = 5
DFLTPORT = 6668
DFLTVERS = "3.1"
DISCCNT = 3

log = logging.getLogger(__name__)

class TuyaException(Exception):
    pass

class TuyaCipher():

    def __init__(self, key, version="3.1"):
        self.key = key
        try:
            self.version = version.encode()
        except:
            print("This is it {}".format(version))
            self.version = version
        self.cipher = AES.new(self.key, AES.MODE_ECB)

    def decrypt(self, rawdata):
        if self.version:
            data = base64.b64decode(rawdata[19:])
        else:
            data = rawdata

        data = self.cipher.decrypt(data)
        try:
            return json.loads(data[:data.rfind(b'}')+1])
        except:
            return data

    def encrypt(self, rawdata):
        data=json.dumps(rawdata,separators=(',', ':')).encode()
        if len(data)%16 :
            pbyte = int.to_bytes(16 - len(data)%16, 1, "big")
            data += pbyte * (16 - len(data)%16)

        data = self.cipher.encrypt(data)
        if self.version:
            data = base64.b64encode(data)
        return data, self.md5(data)

    def md5(self,data):
        thisdata = b"data="+data+b"||lpv="+self.version+b"||"+self.key.encode()
        return md5(thisdata).hexdigest().lower()[8:24].encode()


class TuyaMessage():

    def __init__(self, cipher = None):
        self.cipher = cipher
        self.leftover = ""

    def parse(self, data):
        if data is None:
            raise TuyaException("No data to parse")
        if len(data) < 16:
            raise TuyaException("Message too short to be parsed")

        processmsg = True
        result = []

        while processmsg:
            prefix = data[:4]

            if prefix != b'\x00\x00\x55\xaa':
                result.append((999,TuyaException("Incorrect prefix")))
                break

            suffix = data[-4:]

            if suffix != b'\x00\x00\xaa\x55':
                result.append((999, TuyaException("Incorrect suffix")))
                break

            cmdbyte = data[11:12]
            msgsize = int.from_bytes(data[12:16],"big")

            if msgsize != len(data[12:-4]):
                self.leftover = data[16+msgsize:]
                data = data[:16+msgsize]
                log.debug("{} vs {}".format(msgsize,len(data[12:-4])))
                log.debug("Leftover is {}".format(self.leftover))
            else:
                self.leftover = ''
                processmsg = False


            #Removing Prefix, Msg size, also crc and suffix
            mydata = data[16:-8]
            returncode = int.from_bytes(mydata[:4],"big")
            log.debug("Return Code is {}".format(returncode))
            if returncode:
                log.debug("Error: {}".format(data))
            #Removing 0x00 padding
            try:
                while mydata[0:1] == b'\x00':
                    mydata = mydata[1:]
            except:
                #Empty message
                result.append((returncode, None))
                if self.leftover:
                    continue
                else:
                    break

            if self.cipher and cmdbyte != b'\x0a':
                result.append((returncode, self.cipher.decrypt(mydata)))
            else:
                #log.debug("Loading {}".format(mydata[:mydata.decode().rfind('}')+1]))
                try:
                    result.append((returncode, json.loads(mydata.decode()[:mydata.decode().rfind('}')+1])))
                except:
                    result.append((returncode, mydata))
        return result

    def encode(self, command, data):
        if command == "get":
            cmdbyte = b'\x0a'
        elif command == 'set':
            cmdbyte = b'\x07'
        else:
            raise TuyaException("Unknown command")

        if isinstance(data, dict):
            payload = json.dumps(data,separators=(',', ':')).encode()
        elif isinstance(data, str):
            payload = data.encode()
        elif isinstance(data,bytes):
            payload = data
        else:
            raise TuyaException("Don't know who to send {}".format(data.__class__))

        prefix = b'\x00\x00\x55\xaa'+ b'\x00'*7 + cmdbyte
        #CRC
        payload += b'\x00'*4   #Apparently not checked, so we dpn't bother
        #Suffix
        payload += b'\x00\x00\xaa\x55'
        try:
            return prefix + int.to_bytes(len(payload),4,"big") + payload
        except Exception as e:
            log.debug("Error was {}".format(e))
            return None




class TuyaDevice(aio.Protocol):
    """Connection to a given Tuya device.

        :param: devid: The device id
        :type devud: string
        :param: key: The device encryption key
        :type key: string
        :param ip_addr: The device IPv4 address
        :type ip_addr: string
        :param port: The port used by the unicast connection
        :type port: into
        :param parent: Parent object with register/unregister methods
        :type parent: object
        :returns: an asyncio DatagramProtocol to handle communication with the device
        :rtype: DatagramProtocol
    """

    dpsmap = []
    dpsvalmap = [ ]

    def __init__(self,devid, key, ip_addr, port=DFLTPORT, parent=[], vers=DFLTVERS, heartbeat=10):
        self.devid = devid
        self.ip = ip_addr
        self.port = port
        if not isinstance(parent,list):
            self.parent = [parent]
        else:
            self.parent = parent
        self.cipher = TuyaCipher(key, vers)
        self.message = TuyaMessage(cipher=self.cipher)
        self.hb = heartbeat
        self.hbtask = None
        self.transport = None
        self.loop = None
        self.task = None
        self.noresponse = 0
        self.disconnect_count = DISCCNT
        self.last_status = {}
        self.raw_dps = False


    def start(self, loop):
        """Starting the control of the device
        """
        self.loop = loop
        coro = self.loop.create_connection(
            lambda: self, self.ip, self.port)

        self.task = self.loop.create_task(coro)
        return self.task

    def connection_made(self, transport):
        self.transport = transport
        #Start heartbeat
        #log.debug("Starting HB")
        #self.initial_command()
        self.hbtask = self.loop.create_task(self.heartbeat())
        for aparent in self.parent:
            aparent.register(self)

    def initial_command(self):
        """Om case a device needs an initial command to behave correctly"""
        pass

    def data_received(self, data):
        #log.debug("Got data")
        self.disconnect_count = DISCCNT
        dev_data = {} #For the except.. just in case
        try:
            for rcode, rcvdata in self.message.parse(data):
                log.debug("Processing received data {}, {}".format(rcode,rcvdata))
                if not rcvdata:
                    continue
                if rcode:
                    for aparent in self.parent:
                        aparent.got_error(self,dev_data)
                    continue
                #log.debug('Raw Data received: {!r}'.format(rcvdata))
                dev_data={}
                if "devId" in rcvdata:
                    dev_data["devId"] = rcvdata["devId"]
                if "dps" in rcvdata:
                    for x in rcvdata["dps"]:
                        try:
                            dev_data[self.dpsmap[int(x)-1]] = rcvdata["dps"][x]
                        except:
                            if self.raw_dps:
                                dev_data[x] = rcvdata["dps"][x]
                dev_data = self.normalize_data(dev_data)
                for x in dev_data:
                    self.last_status[x] = dev_data[x]
                for aparent in self.parent:
                    aparent.got_data(dev_data)
                else:
                    log.debug('Data received: {!r}'.format(dev_data))
        except Exception as e:
            log.debug("Error XX: {} {} {}".format(e, data ,dev_data))

    def normalize_data(self, data):
        """Here we can normalize the way data is presented to the appyaOCSwitch("58063204bcddc281a9c5",'992c28c42da4551c',"192.168.7.160", heartbeat=10)
dev2.starlication

        By default, nothing
        """
        return data

    def connection_lost(self, exc):
        if self.hbtask:
            self.hbtask.cancel()
        self.transport = None
        for aparent in self.parent:
            aparent.unregister(self)
        else:
            log.debug("Connection lost")

    async def heartbeat(self):
        log.debug("HB Started for {}".format(self.devid))
        try:
            while True:
                if self.disconnect_count == 0:
                    raise Exception
                #Get the status
                self.disconnect_count -= 1
                self.query()
                await aio.sleep(self.hb)
                log.debug("HB Lapsed for {}".format(self.devid))

        except:
            self.hbtask = None
        finally:
            self.seppuku()
            return

    def query(self, prop=None):
        """Query some device property
        """
        payload = self.message.encode("get", OrderedDict([("devId", self.devid), ("gwId", self.devid)]))
        #log.debug("Sending Data : {}".format(payload))
        self.transport.write(payload)

    def set(self, values):
        dps = {}
        for x in values:
            dps['%d'%(self.dpsmap.index(x)+1)] = self.dpsvalmap[self.dpsmap.index(x)](values[x])
        self.raw_set(dps)

    def raw_set(self, dps):
        payload = OrderedDict([("devId", self.devid), ("uid", ''), ("t", str(round(time()))), ("dps", dps)])
        payload, md5 = self.cipher.encrypt(payload)
        payload = self.message.encode("set",self.cipher.version+md5+payload)
        self.transport.write(payload)

    def add_parent(self,parent):
        if not isinstance(parent,list):
            self.parent.append(parent)
        else:
            self.parent += parent

    def seppuku(self):
        """Japanese for ritual disembowelment. Also know as Hara-Kiri
        """
        if self.transport:
            self.transport.close()
        self.transport = None

    def close(self):
        """For ignoramus who cannot remember seppuku.
        """
        self.seppuku()

    def die_motherfucker(self):
        """For americans
        """
        self.seppuku()


class TuyaSwitch(TuyaDevice):
    """Connection to a given Tuya switch device.

        :param: devid: The device id
        :type devud: string
        :param: key: The device encryption key
        :type key: string
        :param ip_addr: The device IPv4 address
        :type ip_addr: string
        :param port: The port used by the unicast connection
        :type port: into
        :param parent: Parent object with register/unregister methods
        :type parent: object
        :returns: an asyncio DatagramProtocol to handle communication with the device
        :rtype: DatagramProtocol
    """

    dpsmap = ["power"]
    dpsvalmap = [ lambda x: True if x in [True, 1, "on","On","ON", "oN"] else False ]

    def on(self):
         self.set({"power": True})

    def off(self):
         self.set({"power": False})

    def set_power(self, state):
        try:
            self.set({"power": state})
        except Exception as e:
            log.debug("ERROR: Could not set Switch power: {}".format(e))

    def get_power(self):
        try:
            return self.last_status["power"]
        except:
            return None

    def normalize_data(self, data):
        """Here we can normalize the way data is presented to the application

        By default, nothing
        """
        if "power" in data:
            data["power"] = "on" if data["power"] else "off"

        return data


class TuyaOCSwitch(TuyaDevice):
    """Connection to a given Tuya Open/Close/Idle device.

        :param: devid: The device id
        :type devud: string
        :param: key: The device encryption key
        :type key: string
        :param ip_addr: The device IPv4 address
        :type ip_addr: string
        :param port: The port used by the unicast connection
        :type port: into
        :param parent: Parent object with register/unregister methods
        :type parent: object
        :returns: an asyncio DatagramProtocol to handle communication with the device
        :rtype: DatagramProtocol
    """

    dpsmap = ["state"]
    dpsvalmap = [ lambda x: str(1+["open","close","idle"].index(x.lower())) ]

    def __init__(self,devid, key, ip_addr, port=DFLTPORT, parent=[], vers=DFLTVERS, heartbeat=10, invert = False):
        super().__init__(devid, key, ip_addr, port, parent, vers, heartbeat)
        self.inverted = invert


    def open(self):
        if self.inverted:
            self.close()
        else:
            self.set({"state": 'open'})

    def close(self):
        if self.inverted:
            self.open()
        else:
            self.set({"state": 'close'})

    def idle(self):
         self.set({"state": 'idle'})

    def set_state(self, state):
        try:
            if self.inverted and state.lower() in ["open","close"]:
                state = "close" if state == "open" else "open"
            self.set({"state": state})
        except Exception as e:
            log.debug("ERROR: Could not set Switch state: {}".format(e))

    def get_state(self):
        try:
            return self.last_status["state"]
        except:
            return None

    def initial_command(self):
        """For some reason, my curtain switch needs a set command before it will behave
        """
        self.idle()

    def normalize_data(self, data):
        """Here we can normalize the way data is presented to the application

        By default, nothing
        """
        if "state" in data:
            if data["state"] == '2':
                if self.inverted:
                    data["state"]="opening"
                else:
                    data["state"]="closing"
            elif data["state"] == '1':
                if self.inverted:
                    data["state"]="closing"
                else:
                    data["state"]="opening"
            else:
                data["state"]="idling"

        return data





class TuyaLight(TuyaDevice):
    """Connection to a given Tuya Open/Close/Idle device.

        :param: devid: The device id
        :type devud: string
        :param: key: The device encryption key
        :type key: string
        :param ip_addr: The device IPv4 address
        :type ip_addr: string
        :param port: The port used by the unicast connection
        :type port: into
        :param parent: Parent object with register/unregister methods
        :type parent: object
        :returns: an asyncio DatagramProtocol to handle communication with the device
        :rtype: DatagramProtocol
    """
    maxk = 9000
    mink = 2000
    dpsmap = ["power", "mode", "brightness","temperature","colour"] #
    dpsvalmap = [ lambda x: True if x in [True, 1, "on","On","ON", "oN"] else False,
                 lambda x: x.lower() if x.lower() in ['white','colour','scene','scene_1','scene_2','scene_3','scene_4'] else 'white',
                 lambda x: x if x in range(25,256) else min(max(x,25),255),
                 lambda x: round((((min(x,TuyaLight.maxk) - TuyaLight.mink)*255)/(TuyaLight.maxk - TuyaLight.mink)) if x >= TuyaLight.mink else 0),
                 lambda x: TuyaLight.hsv_to_tuya(x)
                 ]


    def __init__(self,devid, key, ip_addr, port=DFLTPORT, parent=[], vers=DFLTVERS, heartbeat=10):
        super().__init__(devid, key, ip_addr, port, parent, vers, heartbeat)
        self.transition = None
        self.last_white = [50, 6500]
        self.last_colour = [180, 50, 50]

    @staticmethod
    def hsv_to_tuya(colour):
        """ Here colour is a list containing h (0-360), s (0-100), v (0-100)
        """
        rgb = [round(x*255) for x in hsv_to_rgb(*[ x(y) for x,y in zip([lambda x: x/360, lambda x: x/100, lambda x: x/100],colour)])]
        hsv = [round(x(y)*255) for x,y in zip([lambda x: x/360, lambda x: x/100, lambda x: x/100],colour)]
        return "".join([ '%02x'%x for x in rgb+[0]+hsv])

    @staticmethod
    def rgb_to_tuya(colour):
        """ Here colour is a list containing r (0-255), g (0-255), b (0-255)
        """
        rgb = colour
        hsv = [round(x*255) for x in rgb_to_hsv(*map(lambda x: x/255,colour))]
        return "".join(["%02x"%x for x in rgb+[0]+hsv])

    @staticmethod
    def tuya_to_hsv(colour):
        """ Colour is a string with rrggbb00hhssvv. With hex values.
        """
        hsvstr = colour[-6:]
        result = []
        result.append( round((int(hsvstr[0:2],16)*360)/255))
        result.append( round((int(hsvstr[2:4],16)*100)/255))
        result.append( round((int(hsvstr[4:6],16)*100)/255))
        return result

    @staticmethod
    def tuya_to_rgb(colour):
        """ Colour is a string with rrggbb00hhssvv. With hex values.
        """
        hsvstr = colour[:6]
        return [int(hsvstr[x:x+2],16) for x in range(0,len(hsvstr),2)]

    def on(self):
        if self.last_status["mode"] == "white":
            self.set_white(self.last_white[0], self.last_white[1])
        elif self.last_status["mode"] == "colour":
             self.set_colour(self.last_colour)
        else:
            self.set({"power": True})

    def off(self):
        if self.last_status["mode"] == "white":
            self.last_white = [self.last_status["brightness"], self.last_status["temperature"]]
        elif self.last_status["mode"] == "colour":
            self.last_colour = self.last_status["colour"]
        self.set({"power": False})

    def set_white(self, bright, temp = 6500):
        """ Set white mode with brightness and temperature"""
        log.debug("Set white {} {}".format(bright, temp))
        try:
            self.set({"power": True, "mode": "white", "brightness": bright, "temperature": temp})
        except Exception as e:
            log.debug("ERROR: Could not set Light white: {}".format(e))

    def set_colour(self,colour):
        try:
            self.set({"power": True, "mode": "colour", "colour": colour})
            self.last_colour = colour
        except Exception as e:
            log.debug("ERROR: Could not set Light colour: {}".format(e))

    def set_colour_rgb(self,colour):
        try:
            self.set({"power": True, "mode": "colour", "colour": [round(x*255) for x in rgb_to_hsv(*map(lambda x: x/255,colour))]})
        except Exception as e:
            log.debug("ERROR: Could not set Light rgb colour: {}".format(e))


    def fadein_white(self, bright, temp, duration=3.0):
        """Fade in white with duration"""
        xx = self.loop.create_task(self._white_transition([25, temp], [bright, temp], duration))

    def fadeout_white(self, duration=3.0):
        """Fade in white with duration"""
        self.last_white= [self.last_status["brightness"], self.last_status["temperature"]]
        xx = self.loop.create_task(self._white_transition(self.last_white, [25, self.last_white[1]], duration))

    def transition_white(self, end, duration):

        xx = self.loop.create_task(self._white_transition([self.last_status["brightness"], self.last_status["temperature"]], end, duration))


    async def _white_transition(self, start, end, duration):
        log.debug("\n\nWhite transition {} {} {}".format(start, end, duration))
        if start[0] == end[0] and start[1] == end[1]:
            await aio.sleep(0)
            if end[0]<= 25:
                self.off()
            else:
                self.set_white(end[0],end[1])
            return
        cnt = 3
        log.debug("White trans {} {}".format(self.devid, self.transition))
        if self.transition is True:
            self.transition = False
            while not self.transition is None:
                log.debug("White trans wait")
                await aio.sleep(0.1)
                cnt -=1
                if not cnt:
                    return

        elif self.transition is False:
            return

        self.transition =  True

        steps = round(duration*5)  #We send every 0.2 secs
        for x in range(steps+1):
            if self.transition is False or self.transport is None:
                self.transition = None
                return
            b = start[0] + round(((end[0]-start[0])*x)/steps)
            t = start[1] + round(((end[1]-start[1])*x)/steps)
            self.set_white(b, t)
            await aio.sleep(0.2)

        self.set_white(end[0], end[1])
        if end[0]<= 25:
            self.off()
        self.transition =  None


    def fadein_colour(self, colour, duration=3.0):
        """Fade in white with duration"""
        xx = self.loop.create_task(self._colour_transition([colour[0], colour[1], 0], colour, duration))

    def fadeout_colour(self, duration=3.0):
        """Fade in white with duration"""
        self.last_colour= self.last_status["colour"]
        xx = self.loop.create_task(self._colour_transition(self.last_colour, [self.last_colour[0],self.last_colour[1], 0], duration))


    def transition_colour(self, end, duration):

        xx = self.loop.create_task(self._colour_transition(self.last_colour, end, duration))

    async def _colour_transition(self, start, end, duration):
        log.debug("\n\nColour transition {} {} {}".format(start, end, duration))
        if start[0] == end[0] and start[1] == end[1] and start[2] == end[2]:
            await aio.sleep(0)
            if end[2] <= 0:
                self.off()
            return
        cnt = 3
        if self.transition is True:
            self.transition = False
            while not self.transition is None:
                await aio.sleep(0.1)
                cnt -=1
                if not cnt:
                    return

        elif self.transition is False:
            return

        self.transition =  True

        steps = round(duration*5)  #We send every 0.2 secs
        log.debug("Steps is {}".format(steps))
        if start[0] > end[0]:
            if start[0] - end[0] < 180:
                #we go negative
                hdelta = round((end[0] - start[0])/steps)
            else:
                hdelta = round((end[0] - start[0] + 360)/steps)
        else:

            if end[0] - start[0] < 180:
                hdelta = round((end[0] - start[0])/steps)
            else:
                hdelta = 0 - round((start[0] - end[0] + 360)/steps)

        log.debug("hdelta is {}".format(hdelta))
        for x in range(steps):
            if self.transition is False:
                self.transition = None
                return
            h = (start[0] + hdelta*x)%360
            s = start[1] + round(((end[1]-start[1])*x)/steps)
            v = start[2] + round(((end[2]-start[2])*x)/steps)
            log.debug("Colour to {}".format([h,s,v]))
            self.set_colour([h,s,v])
            await aio.sleep(0.2)

        self.set_colour(end)
        if end[2]<= 1:
            self.off()
        self.transition =  None


    def normalize_data(self, data):
        """Here we can normalize the way data is presented to the application

        By default, nothing
        """
        if "power" in data:
            data["power"] = data["power"] and "On" or "Off"
        if "temperature" in data:
            data["temperature"] = self.mink + round(((self.maxk-self.mink) * data["temperature"])/255)
        if "colour" in data:
            data["colour"] = TuyaLight.tuya_to_hsv(data["colour"])

        return data



class TuyaScanner(aio.DatagramProtocol):
    """This will monitor UDP broadcast from Tuya devices"""

    def __init__(self, parent= None,ip='0.0.0.0', port=6666):
        self.ip = ip
        self.port = port
        self.loop = None
        self.message = TuyaMessage()
        self.task = None
        self.parent = parent

    def connection_made(self, transport):
        log.debug("Scanner Connected")
        self.transport = transport
        sock = transport.get_extra_info("socket")  # type: socket.socket
        #sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        #sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    def datagram_received(self, rdata, addr):
        resu =self.message.parse(rdata)
        for code, data in resu:
            log.debug('broadcast received: {}'.format(data))
            if self.parent:
                self.parent.notify(data)

    def start(self, loop):
        """Starting the control of the device
        """
        self.loop = loop
        coro = self.loop.create_datagram_endpoint(
            lambda: self, local_addr= (self.ip, self.port))

        self.task = self.loop.create_task(coro)
        return self.task

    def close(self):
        if self.transport:
            self.transport.close()
            self.transport = None


class TuyaManager:
    """This class manages Tuya devices. It will create devices when notified,
    if will also destroy and recreate them when the IP address changes. It will only create devices
    for which it knows an encryption key

    This works by looking for broadcast packets. If the device type is unknown, we start with a
    generic TuyaDevice set with raw_dps, upon receiving a status we try to figure out what the device
    actually is.

    DEWARE  TuyaManager is used as parent for the generic TuyaDevice, so the method register will be called.
    When overloading register, make sure you understand the consequences

    """

    def __init__(self, knowndevs={}, dev_parent = [], loop = None):
        """ knowndevs should be a dictionary. The key is the device id
            and the value, the encryption key. dev_parent is the device parent,
            with register/unregister/got_data methods
        """
        self.known_devices = knowndevs
        self.running_devices = {}
        self.pending_devices = {}
        self.version_devices = {}
        self.ignore_devices = []
        self.error_device = {}
        self.loop = aio.get_event_loop() if loop is None else loop
        self.dev_parent = dev_parent
        self.load_keys()


    def notify(self,data):
        dclass = None
        if "gwId" not in data or "ip" not in data:
            #Nothing we can do
            return

        if data["gwId"] in self.ignore_devices:
            log.debug("Ignoring {}".format(data["gwId"]))
            return

        if data["gwId"] in self.running_devices:
            if self.running_devices[data["gwId"]].ip == data["ip"] and self.running_devices[data["gwId"]].transport:
                #No change
                return
            dclass = self.running_devices[data["gwId"]].__class__
            self.running_devices[data["gwId"]].seppuku()
            del(self.running_devices[data["gwId"]])

        if data["gwId"] in self.pending_devices:
            #Wow!... This sucker broadcasts like crazy... or we have a problem
            self.pending_devices[data["gwId"]].attemps -= 1
            if self.pending_devices[data["gwId"]].attemps == 0:
                self.pending_devices[data["gwId"]].seppuku()
                del(self.pending_devices[data["gwId"]])
            return

        if data["gwId"] not in self.known_devices:
            #No key.... we are fucked
            return

        try:
            self.version_devices[data["gwId"]] = data["version"]
        except:
            self.version_devices[data["gwId"]] = DFLTVERS
        #OK... either we know the class or we dpn't
        if dclass:
            #Great we know it
            self.running_devices[data["gwId"]] = dclass(data["gwId"], self.known_devices[data["gwId"]], data["ip"], parent=self.dev_parent, vers=self.version_devices[data["gwId"]])
            self.running_devices[data["gwId"]].start( loop = self.loop )
        else:
            #First time, we need to figure out what the device is
            self.pending_devices[data["gwId"]] = TuyaDevice(data["gwId"], self.known_devices[data["gwId"]], data["ip"], parent=[self], vers=self.version_devices[data["gwId"]],heartbeat=2)
            self.pending_devices[data["gwId"]].raw_dps = True
            self.pending_devices[data["gwId"]].attemps = 0
            self.pending_devices[data["gwId"]].start(self.loop)

    def register(self,dev):
        #Avoid overloading.... it will run when a "pending" device connects
        pass

    def unregister(self,dev):
        #Just delete the pending id
        try:
            del(self.pending_devices[dev.devid])
        except:
            pass

    def new_key(self, devid, key):
        self.known_devices[devid] = key
        if devid in self.ignore_devices:
            self.ignore_devices.remove(devid)
        self.persist_keys()


    def persist_keys(self):
        pass

    def load_keys(self):
        pass


    def got_data(self,data):
        """We are trying to figure out the device type"""
        if "devId" not in data: #Ooops
            return

        if data["devId"] not in self.pending_devices:
            log.debug("Oops, devid {} should not sent data here.".format(data["devId"]))
            return

        tclass = None
        discdev = self.pending_devices[data["devId"]]
        if len(data) == 2 and '1' in data and data['1'] in ['1', '2', '3']:
            tclass = TuyaOCSwitch
        elif len(data) == 2 and '1' in data and data['1'] in [True, False]:
            tclass = TuyaSwitchscanner
        elif len(data) == 11 and '2' in data and data['2'] in ["white", "colour", "scene"]:
            tclass = TuyaLight
        else:
            self.ignore_devices.append(data["devId"])

        if tclass:
            newdev = tclass(discdev.devid, self.known_devices[discdev.devid],discdev.ip, parent = self.dev_parent, vers=self.version_devices[data["devId"]])
            self.running_devices[newdev.devid] = newdev
            newdev.start(self.loop)
        else:
            log.debug("No match for {}".format(data))
        self.pending_devices[data["devId"]].seppuku()
        del(self.pending_devices[data["devId"]])

    def got_error(self, dev, data):
        """Looks like we got a problem. Given how we do things, this must be from one of the pending
        devices, i.e. some generic device. Let's try to send a command to see if that fix things."""
        log.debug("Got error from {}: {}".format(dev.devid,data))
        if dev.devid not in self.error_device:
            self.error_device[dev.devid] = 0
            #Only the first time around
            dev.raw_set({'1':False})
        elif self.error_device[dev.devid] == 1:
            #Try the second time around
            dev.raw_set({'1':'3'})

        self.error_device[dev.devid] += 1
        if self.error_device[dev.devid]>=5:
            try:
                log.debug("Done trying with {}".format(dev.devid))
                self.ignore_devices.append(dev.devid)
                self.pending_devices[dev.devid].seppuku()
                del(self.error_device[dev.devid])
            except Exception as e:
                log.debug("Error disabling dev {}, {}".format(dev.devid, e))



    def close(self):
        log.debug("On closing we have:")
        log.debug("           running : {}".format(self.running_devices))
        log.debug("           pending : {}".format(self.pending_devices))
        log.debug("          ignoring : {}".format(self.ignore_devices))
        for x in self.pending_devices.values():
            x.seppuku()
        for x in self.running_devices.values():
            x.seppuku()





if __name__ == '__main__':
    async def runit(man):
        await aio.sleep(4)
        for dev in man.running_devices.values():
            log.debug("Id is {}".format(dev.devid))
            if dev.devid == "01200864dc4f22025723":
                dev.set_white(100,6500)
                await aio.sleep(3)
                dev.set_colour([100,80,80])
                await aio.sleep(3)
                dev.transition_colour([320, 40, 50], 10)
                await aio.sleep(10)
                #dev.on()
        #dev.fadein_white(85,5500,10)
                dev.transition_colour([180, 90, 100], 7)
                await aio.sleep(3)
                dev.fadeout_white(4)

    async def runwhite(dev):
        await aio.sleep(3)
        #dev.set_white(100,6500)
        #dev.fadeout_white(10)
        #dev.fadein_white(85,5500,10)
        dev.transition_white([50, 3500], [80, 8000], 5)
        await aio.sleep(3)
        dev.fadeout_colour(4)

    logging.basicConfig(
                level=logging.DEBUG,
                format='%(levelname)7s: %(message)s',
                stream=sys.stderr,
            )

    loop = aio.get_event_loop()
    manager = TuyaManager({"01200864dc4f22025723":'93699bfd4c5b720d', "58063204bcddc281a9c5":'5a88e1d60b7f3641'})
    scanner = TuyaScanner(parent=manager)
    scanner.start(loop)
    #dev = TuyaLight("01200864dc4f22025723",'93699bfd4c5b720d',"192.168.7.90", heartbeat=20)
    #dev.start(loop)
    #dev2 = TuyaOCSwitch("58063204bcddc281a9c5",'992c28c42da4551c',"192.168.7.160", heartbeat=10)
    #dev2.start(loop)
    xx = loop.create_task(runit(manager))
    #xx = loop.create_task(toggleit2(dev2))
    try:
        loop.run_forever()
    except:
        for dev in manager.running_devices:
            try:
                dev.off()
            except:
                pass
        scanner.close()
        manager.close()
        loop.run_until_complete(aio.sleep(2))
        pass
