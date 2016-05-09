#!/usr/bin/python3
# v0.6 (c) 2015 urban

import serial
from serial.tools import list_ports
import time
import binascii

class USBCAN:
    # Message type:
    # "init" for setup CH340 Device
    # "trans-rec" for CAN transmit and recieve
    # "bus-status" for requesting status
    mtype    = {"init":"02", "trans-rec":"01", "init-default-baudrate":"03", "bus-status":"04", "id-filter":"10"}
    frtype   = {"standard":"01", "extended":"02", "init":"03"}                    # frametype
    frfmt    = {"ata":"01", "remote":"02"}                                        # frameformat
    mode     = {"normal":"00", "loop":"01", "silent":"02", "loop+silent":"03"}    # mode
    mhead    = "aa55"                                                             # header for every messange to CH340 Device
    baudrate = {1000000:"01", 800000:"02", 500000:"03", 400000:"04", 250000:"05", # standard baudrate
                200000:"06",  125000:"07", 100000:"08", 50000:"09",  20000:"0a",
                10000:"0b",   5000:"0c"}

    readbuf   = bytearray([0] * 18)
    Message   = []    #{"data":None,"ID":None,"length":0,"Frformat":None,"Frtype":None}]
    Buserrors = {"rec-errors":0,"tr-errors":0,"errorflags":""}
    timeout   = 0

    def __init__(self, canbaud, frtype, mode="normal", devname="USB-SERIAL CH340", baudrate=1228800, stopbits=1, timeout=1, writeTimeout=1, bytesize=8):
        self.timeout = timeout
        self.initdevice(canbaud, frtype, mode, devname, baudrate, stopbits, timeout, writeTimeout, bytesize)

    def initdevice(self, canBaudrate, frtype, mode, devname, baudrate, stopbits, timeout, writeTimeout, bytesize):
        self.canport = None

        # Search for CH340 Device
        for port, devname, VID in list_ports.comports():
            if "USB-SERIAL CH340" in devname or "HL-340 USB-Serial" in devname or "QinHeng Electronics" in devname:
                print ("Found USB-CAN Device on ", port)

                self.canport = serial.Serial(port, baudrate,
                                    parity = serial.PARITY_NONE,
                                    stopbits = stopbits, timeout = timeout,
                                    writeTimeout = writeTimeout, bytesize = bytesize)
                break

        if not self.canport:
            raise("No USB-CAN Device found, exiting!")
        else:
            print ("USB-CAN Device ready, Baud: ", canBaudrate)

        self.setup(canBaudrate, frtype, mode)

        self.set_IDfilter([]) # disable idfilter

        time.sleep(0.5)

    def setup(self, canBaudrate, frtype, mode):
        if canBaudrate in self.baudrate.keys():                            # init with standard baudrate "00000" + self.mode[mode] + "010000000"
            self.send("00000000", "000000" + self.mode[mode] + "01000000", # init message
                      mmtype = "init", mftype = "init", mfformat = frtype, Baud = canBaudrate)
        else:
            # init custom boudrate
            # CAN bps = 36000000 / (SYNC_SEG + BP1 + BP2)/Pre Frequ          MAX 12000000bps
            SYNC_SEG = 0x01

            x = int(36000000 / (canBaudrate))

            BPlist   = []
            Freqlist = []

            for BPs in range(3,26):

                PreFreq = min([int(x/BPs), 1024])
                rest    = x - BPs * PreFreq

                Freqlist.append(PreFreq)
                BPlist.append(rest * rest)

            BPs     = BPlist.index(min(BPlist)) + 3
            PreFreq = Freqlist[BPs - 3]

            BPs -= 1

            if BPs > 16:
                BP1 = 16
                BP2 = BPs - 16
            else:
                BP1 = BPs - 1
                BP2 = 1

            # FIXME: for Baude?
            Baude = 36000000/((SYNC_SEG + BP1 + BP2) * PreFreq)
            print("Individual Baud setting: ", Baude)

            PreFreq     = "{:04X}".format(PreFreq)
            strPreFreq  = ""
            strPreFreq += PreFreq[2:4]
            strPreFreq += PreFreq[0:2]

            # init message
            self.send("00000000",
                      "000000" + "{:02X}".format(SYNC_SEG -  1 ) + "{:02X}".format(BP1 - 1) + "{:02X}".format(BP2 - 1) + strPreFreq,
                      mmtype = "init-default-baudrate", mftype = "init", mfformat = frtype, Baud = 1000000)


        time.sleep(0.01)

    def bus_status(self):

        message = self.mtype["bus-status"] + "0" * 32 + "04"  # 04 is ckecksum
        message = self.mhead + message

        self.canport.write(bytearray.fromhex(message))
        self.rec()

        while self.readbuf[2] != 4:
            self.rec()

    def send(self, mfID, data = "", mmtype = "trans-rec", mftype = "standard", mfformat = "ata", Baud = None):

        message=""

        if Baud and mmtype == "init":             # when we want set baudrate
            mftype = self.baudrate[Baud]
        elif mmtype == "init-default-baudrate":
            mftype = self.baudrate[1000000]
        else:
            mftype = self.frtype[mftype]

        if mmtype == "init":
            mlength  = "00"
            mfformat = self.frtype[mfformat]                 # setup frameformat
        else:
            mlength  = "{:02X}".format(int(len(data) / 2))   #Nachrichtenlänge setzen
            mfformat = self.frfmt[mfformat]                  # setup frameformat
            data+    = "0" * (16 - len(data))


        mmtype = self.mtype[mmtype]  # message type

        if len(data) > 16:
            raise ValueError("Max 8 databytes")
        if len(mfID) != 8:
            raise ValueError

        ID = ""
        # change endian for ID
        for i in range(0,4):
            ID += mfID[7 - (i * 2 + 1)]
            ID += mfID[7 - i * 2]

        mfID = ID

        # build message
        message = mmtype + mftype + mfformat + mfID + mlength + data + "00"

        mcks = sum(bytearray.fromhex(message))
        mcks = "{:02X}".format(mcks)[-2:]

        message = self.mhead + message + mcks

        self.canport.write(bytearray.fromhex(message))


    def rec(self, timeout = None):
        message = {"data":None, "ID":None, "length":0, "Frformat":None, "Frtype":None}

        buf     = bytearray([0])
        a       = ""
        acttime = time.time()

        while 1:
            if  self.canport.readable():
                self.canport.readinto(buf)
                a+="{:02X}".format(buf[0])

            while len(a)>4:
                a=a[1:]

            if a == "AA55":
                break

            if self.timeout < (time.time() - acttime):
                return "timeout"

        if self.canport.readinto(self.readbuf) == len(self.readbuf): # wait for message

            mcks = sum(self.readbuf[:-2])                # calculate checksum
            mcks = "{:02X}".format(mcks)[-2:]

            if mcks != "{:02X}".format(self.readbuf[-1]):   # check checksum
                raise ValueError("Checksum error", mcks, "{:02X}".format(self.readbuf[-1]), binascii.hexlify(self.readbuf))

            if self.readbuf[2] == int(self.mtype["trans-rec"]):
                message["data"] = self.readbuf[8:-2]

                ID=""

                # change endian for ID
                for i in range(0,4):
                    ID += "{:02X}".format(self.readbuf[6 - i])

                message["ID"]     = ID
                message["length"] = self.readbuf[7]      # read data length

                for key in self.frtype:
                    if self.readbuf[1] == int(self.frtype[key]):
                        message["Frtype"] = key              # read frametype

                for key in self.frfmt:
                    if self.readbuf[2] == int(self.frfmt[key]):
                        message["Frformat"] = key            # read frameformat

                self.Message.append(message)

                return self.mtype["trans-rec"]

            elif self.readbuf[0] == int(self.mtype["bus-status"]):
                self.Buserrors["rec-errors"] = int(self.readbuf[1])     # count of recieve errors
                self.Buserrors["tr-errors"]  = int(self.readbuf[2])     # count of transmit errors
                self.Buserrors["errorflags"] = self.readbuf[3:7]        # error flags (meaning not yet clear)

                return self.mtype["bus-status"]

            return "Unidentified Message"


    def close(self):
        self.canport.close()

    def open(self):
        self.canport.open()

    def flush(self):
        self.canport.flushInput()
        self.canport.flushOutput()
        del self.Message[:]
        self.readbuf=bytearray([0]*len(self.readbuf))

    def set_IDfilter(self, ID = []):

        if len(ID) > 52:
            raise ValueError("To much IDs")
        for ids in ID:
            if len(ids) != 8:
                raise ValueError

        IDs=""
        for ids in ID:
            # change endian for ID
            for i in range(0,4):
                IDs += ids[7 - (i * 2 + 1)]
                IDs += ids[7 - i * 2]

        message = self.mtype["id-filter"] + "{:02X}".format(len(ID)) + IDs  # build message

        mcks    = sum(bytearray.fromhex(message))
        mcks    = "{:02X}".format(mcks)[-2:]
        message = self.mhead + message + mcks

        while 1:
            if  self.canport.writable():
                if self.canport.write(bytearray.fromhex(message)) > 0:
                    break

            if time.time() - tim > self.timeout:
                return "timeout"

        #if len(ID)<1:
        time.sleep(0.6)


if __name__ == "__main__":

    USBCAN=USBCAN(500000, "standard", "normal")

    try:
        #USBCAN.set_IDfilter(["00000584","00000604"])
        USBCAN.send("11111111", "123456")
        #time.sleep(2)
        USBCAN.rec()
        print(USBCAN.Message)
        USBCAN.flush()
        print(USBCAN.Message)
    finally:
        USBCAN.close()

