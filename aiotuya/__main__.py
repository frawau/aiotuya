#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#
# This application is an example on how to use aiotuya
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
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR
# IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE
import argparse
import csv
import logging
import os
import random
import string
import sys
import asyncio as aio
import aiotuya as tuya
from functools import partial


labels = { tuya.TuyaSwitch: "Switch",  tuya.TuyaOCSwitch: "Open/Close Switch", tuya.TuyaLight: "LED Light"}

capabilities = {
    tuya.TuyaSwitch:   [("On", lambda x: x.on(), []),
                        ("Off", lambda x: x.off(), [])],
    tuya.TuyaOCSwitch: [("Open", lambda x: x.open(), []),
                        ("Close", lambda x: x.close(), []),
                        ("Idle", lambda x: x.idle(), [])],
    tuya.TuyaLight:    [("On", lambda x: x.on(), []),
                        ("Off", lambda x: x.off(), []),
                        ("White", lambda x, y, z: x.set_white(y,z),["Brighness", "K"]),
                        ("Colour", lambda x, y, z, t: x.set_colour([y,z,t]),["Hue", "Saturation", "Brightness"])]
    }


#Simple device control from console
class Devices():
    """ A simple class with a register and  unregister methods
    """
    def __init__(self):
        self.devices=[]
        self.boi=None #bulb of interest

    def register(self,device):
        self.devices.append(device)
        self.devices.sort(key=lambda x: x.devid)

    def unregister(self,device):
        idx=0
        for x in list([ y.devid for y in self.devices]):
            if x == device.devid:
                del(self.devices[idx])
                break
            idx+=1

    def got_data(self, data):
        pass

    def got_error(self,dev, data):
        pass

def readin():
    """Reading from stdin and displaying menu"""
    global manager

    selection = sys.stdin.readline().strip("\n")
    MyDevs.devices.sort(key=lambda x: x.devid)
    lov=[ x for x in selection.split(" ") if x != ""]
    if lov:
        if MyDevs.boi:
            capa = capabilities[MyDevs.boi.__class__]
            #try:
            if True:
                fidx = int(lov[0])

                if fidx == 0:
                    MyDevs.boi = None

                elif fidx == len(capa)+2:
                    print("Status is:")
                    for x,y in MyDevs.boi.last_status.items():
                        print("\t{}:\t{}".format(x,y))
                    print("")
                    MyDevs.boi = None

                elif fidx > len(capa):
                    print("\nError: Not a valid selection.\n")
                else:
                    capa = capa[fidx-1]
                    if len(lov) < len(capa[2])+1:
                        if len(capa[2])>1:
                            print("\nError: You must specify %s and %s.\n"%(", ".join(capa[2][:-1]),capa[2][-1]))
                        else:
                            print("\nError: You must specify %s.\n"%(", ".join(capa[2][0])))
                    else:
                        capa[1](MyDevs.boi,*[ int(z) for z in lov[1:]])
                        MyDevs.boi = None
            #except:
                #print ("\nError: Selection must be a number.\n")
        else:
            #try:
            if int(lov[0]) > 0:
                if int(lov[0]) <=len(MyDevs.devices):
                    MyDevs.boi=MyDevs.devices[int(lov[0])-1]
                else:
                    print("\nError: Not a valid selection.\n")
            elif int(lov[0])  == 0:
                #provision
                myprov=DevProvision(manager)
                xx = myprov.start(loop)


            #except:
                #print ("\nError: Selection must be a number.\n")

    if MyDevs.boi:
        capa = capabilities[MyDevs.boi.__class__]
        print("Select Function for {} {}:".format(labels[MyDevs.boi.__class__], MyDevs.boi.devid))
        idx = 0
        for x in capa:
            idx += 1
            mstr = "\t[%d]\t%s"%(idx, x[0])
            if len(x[2]):
                for y in x[2]:
                    mstr += " <%s>"%y
            print(mstr)
        print("")
        idx+=2
        print("\t[%d]\tCurrent Status"%idx)
        print("\t[0]\tBack to device selection")
    else:
        idx=1
        print("Select Device:")
        for x in MyDevs.devices:
            print("\t[{}]\t{} {}".format(idx,labels[x.__class__], x.devid))
            idx+=1
        if opts.ssid:
            print("")
            print("\t[0]\tProvision new devices")
    print("")
    print("Your choice: ", end='',flush=True)

parser = argparse.ArgumentParser(description="Track and interact with Tuya devices.")
parser.add_argument("-D", "--database", default="~/.aiotuya",
                    help="CSV file used to keep device/key matching.")
parser.add_argument("-d","--debug", action='store_true', default=False,
                    help="Print unexpected messages.")
parser.add_argument("-e", "--email", default="",
                    help="Email address to connect to Tuya cloud")
parser.add_argument("-p", "--password", default="",
                    help="password to connect to Tuya cloud")
parser.add_argument("-s", "--ssid", default="",
                    help="SSID to connect to")
parser.add_argument("-P", "--passphrase", default="",
                    help="Passphrase for SSID")
try:
    opts = parser.parse_args()
except Exception as e:
    parser.error("Error: " + str(e))

if opts.debug:
    logging.basicConfig(
                level=logging.DEBUG,
                format='%(levelname)7s: %(message)s',
                stream=sys.stderr,
            )

opts.database = os.path.abspath(os.path.expanduser(opts.database))
if not os.path.isfile(opts.database):
    with open(opts.database,"w+") as f:
        pass

if opts.ssid:
    if opts.email =="":
        opts.email = "".join(random.choice(string.ascii_lowercase)  for _ in range(6))
        opts.email += "@"
        opts.email += "".join(random.choice(string.ascii_lowercase)  for _ in range(8))
        opts.email += ".net"
    if opts.password =="":
        opts.password = "".join(random.choice(string.ascii_lowercase)  for _ in range(10))

class DevProvision(tuya.TuyaProvision):
    def __init__(self, manager):
        global opts
        self.manager = manager
        tuyac = tuya.TuyaCloud(opts.email, opts.password)
        super().__init__(tuyac, opts.ssid, opts.passphrase)

    def register(self):
        for x in self.devices:
            self.manager.new_key(x["id"], x["localKey"])
            #Also name and gwType

class DevManager(tuya.TuyaManager):

    def persist_keys(self):
        global opts
        with open(opts.database, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(self.known_devices.items())

    def load_keys(self):
        global opts
        with open(opts.database, newline='') as f:
            reader = csv.reader(f)
            for row in reader:
                self.known_devices[row[0]] = row[1]


MyDevs= Devices()
loop = aio.get_event_loop()
manager = DevManager(dev_parent=MyDevs)
scanner = tuya.TuyaScanner(parent=manager)
scanner.start(loop)

try:
    loop.add_reader(sys.stdin,readin)
    print("Hit \"Enter\" to start")
    print("Use Ctrl-C to quit")
    loop.run_forever()
except:
    pass
finally:
    print()
    scanner.close()
    manager.close()
    loop.remove_reader(sys.stdin)
    loop.run_until_complete(aio.sleep(2))
    loop.close()
