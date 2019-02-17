#! /usr/bin/env python3
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

import asyncio as aio
import socket
import json
import math
from hashlib import md5
from time import time
from collections import OrderedDict
import aiohttp, random,string
import logging

PORT = 6668
RPORT = 63145
ADDRESS = ("255.255.255.255", 30011)

APIKEY='kqnykr87uwxn99wcyjvk'
APISECRET = 'm5tsnq9998wjdgunak9upxnyftg873jj'

REGIONMATCH={"america":"AZ","asia":"AY","europe":"EU"}
REGIONURL = {"AZ": 'https://a1.tuyaus.com/api.json',
             'AY': 'https://a1.tuyacn.com/api.json',
             'EU': 'https://a1.tuyaeu.com/api.json'}
SIGNKEY = [ 'a', 'v', 'lat', 'lon', 'lang', 'deviceId', 'imei',
            'imsi', 'appVersion', 'ttid', 'isH5', 'h5Token', 'os',
            'clientId', 'postData', 'time', 'n4h5', 'sid', 'sp']

log = logging.getLogger(__name__)

class TuyaCloud(object):
    """This class describe the minimum needed to interact
    with TuYa cloud so we can link devices
    """
    def __init__(self, email, passwd, region = "america", tz = "+00:00", apikey = APIKEY, apisecret = APISECRET):
        try:
            self.region = REGIONMATCH[region.lower()]
        except:
            raise Exception("Error: Region must be one of {}, not {}".format(REGIONMATCH.keys(),region))

        if len(apikey) != 20:
            raise Exception("Error: API Key must be 20 char long, it is {}.".format(len(apikey)))
        self.key = apikey

        if len(apisecret) != 32:
            raise Exception("Error: API Key must be 32 char long, it is {}.".format(len(apikey)))

        self.secret = apisecret
        self.email = email
        self.password = passwd
        self.tz = tz
        self.sessionid = None
        self.deviceid = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(44))
        self.token = ''
        self.tokensecret = ''


    async def _request(self, command, data):

        def shufflehash(data):
            prehash = md5(data.encode()).hexdigest()
            return prehash[8:16] + prehash[0:8] + prehash[24:32] + prehash[16:24]

        def sortOD(od):
            res = OrderedDict()
            for k, v in sorted(od.items()):
                if isinstance(v, dict):
                    res[k] = sortOD(v)
                else:
                    res[k] = v
            return res

        rawdata = {"a": command,
                 "deviceId": data.get("deviceId",self.deviceid),
                 "os": 'Linux',
                 "lang": 'en',
                 "v": '1.0',
                 "clientId": self.key,
                 "time": round(time()),
                 "postData": json.dumps(data,separators=(',', ':'))}

        if self.sessionid:
            rawdata["sid"] = self.sessionid

        sorteddata = sortOD(rawdata)
        log.debug("Request is {}".format(rawdata))
        tosign = ""
        for key in sorteddata:
            if key not in SIGNKEY or not rawdata[key]:
                continue
            tosign += key + "="
            if key == 'postData':
                tosign += shufflehash(rawdata[key])
            else:
                tosign += str(rawdata[key])
            tosign += "||"
        tosign += self.secret
        rawdata["sign"] = md5(tosign.encode()).hexdigest()
        async with aiohttp.ClientSession() as session:
            async with session.get(REGIONURL[self.region], params=rawdata) as resp:
                rdata = await resp.text()
                rdata = json.loads(rdata)

        if not rdata["success"]:
            myex = Exception("Error in request: Code: {}, Message: {}".format(rdata["errorCode"], rdata["errorMsg"]))
            myex.errcode = rdata["errorCode"]
            raise myex
        log.debug("Response to cloud request: {}".format(rdata["result"]))
        return rdata["result"]


    async def login(self):
        data = {"countryCode": self.region,
                "email": self.email,
                "passwd": md5(self.password.encode()).hexdigest()}

        resu = await self._request( 'tuya.m.user.email.password.login',data)
        self.sessionid = resu["sid"]
        return resu

    async def register(self):
        data = {"countryCode": self.region,
                "email": self.email,
                "passwd": md5(self.password.encode()).hexdigest()}

        resu = await self._request( 'tuya.m.user.email.register',data)
        self.sessionid = resu["sid"]
        return resu

    async def newtoken(self):
        data = {"timeZone": self.tz}
        resu = await self._request( 'tuya.m.device.token.create',data)
        self.token = resu['token']
        self.tokensecret = resu['secret']
        #log.debug("Got new token: {}".format(resu))
        return resu

    async def listtoken(self):
        data = {"token": self.token}
        resu = await self._request('tuya.m.device.list.token',data)
        #log.debug("Got token list: {}".format(resu))
        return resu



class TuyaProvision(aio.DatagramProtocol):

    def __init__(self, tuya = None, ssid = None, passphrase = None):
        self.target = ADDRESS
        self.loop = None
        self.tuya = tuya
        self.ssid = ssid
        self.passphrase = passphrase
        self.abortbroadcast = False
        self.provisiondata = []
        self.devices = []
        self.task = None

    def connection_made(self, transport: aio.transports.DatagramTransport):
        #log.debug('started')
        self.transport = transport
        sock = transport.get_extra_info("socket")  # type: socket.socket
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.loop.create_task(self._provision_devices())

    async def _provision_devices(self):
        await self._tuya_login()
        if not self.provisiondata:
            self.loop.create_task(self.seppuku())
            return

        await self.startbroadcast()
        self.loop.create_task(self.waitinfo())
        await self.sendlinkdata()

    async def _tuya_login(self):
        try:
            try:
                resu = await self.tuya.login()
            except:
                resu = await self.tuya.register()
            resu = await self.tuya.newtoken()
        except:
            await self.seppuku()
            return
        self.provisiondata = self._make_linkdata()

    async def waitinfo(self):
        cnt = 5
        for x in range(200):
            lodevs = await self.tuya.listtoken()
            if len(lodevs) > len(self.devices):
                self.devices = lodevs
                cnt = 5
            elif cnt == 0:
                self.abortbroadcast = True
                break
            elif len(self.devices):
                cnt -= 1
        self.register()
        await self.seppuku()

    def register(self):
        log.debug(self.devices)

    def datagram_received(self, data, addr):
        #We are not expecting data
        #log.debug('data received:', data, addr)
        pass

    async def startbroadcast(self):
        for x in range(144):
            for s in [1, 3, 6, 10]:
                string="\x00"*s
                self.transport.sendto(string.encode(), self.target)
            await aio.sleep(((x % 8) + 33)/1000.0)
            if self.abortbroadcast:
                log.debug("Broadcast aborted")
                break
        log.debug("Broadcast done")

    async def sendlinkdata(self):
        delay = 0
        for x in range(30):
            if self.abortbroadcast:
                break

            if delay > 26:
                delay = 6

            for s in self.provisiondata:
                string="\x00"*s
                self.transport.sendto(string.encode(), self.target)
                await aio.sleep(delay/1000.0)

            await aio.sleep(0.2)
            delay += 3

        self.abortbroadcast = False

    def _make_linkdata(self):

        def docrc(data):
            crc = 0
            for i in range(len(data)):
                crc = docrc1Byte(crc ^ data[i])
            return crc

        def docrc1Byte(abyte):
            crc1Byte = 0
            for i in range(8):
                if ( crc1Byte ^ abyte ) & 0x01 > 0:
                    crc1Byte ^= 0x18
                    crc1Byte >>= 1
                    crc1Byte |= 0x80
                else:
                    crc1Byte >>= 1
                abyte >>= 1

            return crc1Byte

        barray=bytearray(1)+self.passphrase.encode()
        clen = len(barray)
        barray[0] = clen-1
        lenpass = clen -1
        barray += bytearray(1) + (self.tuya.region+self.tuya.token+self.tuya.tokensecret).encode()
        barray[clen] = len(barray) - clen - 1
        lenrts = len(barray) - clen - 1
        clen = len(barray)
        barray += self.ssid.encode()
        lenssid = len(self.ssid.encode())

        rlen = len(barray)

        edata = []
        log.debug("\nLength are {} {} {}\n".format(lenpass, lenrts, lenssid))
        fstrlen = (lenpass + lenrts + lenssid + 2) % 256
        log.debug("\nStr length is {}".format(fstrlen))
        fstrlencrc = docrc([fstrlen])
        log.debug("\nCRC length is {}".format(fstrlencrc))

        edata.append((fstrlen // 16) | 16)
        edata.append((fstrlen % 16) | 32)
        edata.append((fstrlencrc // 16) | 48)
        edata.append((fstrlencrc % 16) | 64)

        edidx = 0
        seqcnt = 0
        while edidx < rlen:
            crcdata = []
            crcdata.append(seqcnt)
            for idx in range(4):
                crcdata.append(barray[edidx] if edidx < rlen else  0)
                edidx += 1
            crc = docrc(crcdata)
            edata.append((crc % 128) | 128)

            edata.append((seqcnt % 128) | 128)
            #data
            for idx in range(4):
                edata.append((crcdata[idx+1] % 256) | 256)
            seqcnt += 1
        log.debug("Link data is: {}".format(edata))
        return edata

    def start(self, loop):
        self.loop = loop
        coro = self.loop.create_datagram_endpoint(
            lambda: self, local_addr=('0.0.0.0', RPORT))

        self.task = self.loop.create_task(coro)
        return self.task

    async def seppuku(self):
        self.abortbroadcast = True
        await aio.sleep(1)
        self.transport.close()
        #log.debug("Dying")

