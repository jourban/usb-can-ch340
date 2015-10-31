#!/usr/bin/python3
# v0.6 (c) 2015 urban

import serial
from serial.tools import list_ports
import time
import binascii

class USBCAN:
    mtype={"init":"02","Trans-Rec":"01","init_manbaud":"03","Busstatus":"04","IDFilter":"10"}   #Messagetype: "init" um CH340 Device zu parametrieren,
                                                                                    #"Trans-Rec" für CAN Transmit und Recieve, "Busstatus" für abfragen des Busstatus

    frtype={"Standard":"01","Extended":"02","init":"03"}                        #Frametype
    frfmt={"ata":"01","Remote":"02"}                                            #Frameformat
    mode={"normal":"00","loop":"01","silent":"02","loop+silent":"03"}           #Mode
    mhead="aa55"                                                                #Header für jede Nachricht an CH340 Device
    Baudraten={1000000:"01",800000:"02",500000:"03",400000:"04",250000:"05",
                200000:"06",125000:"07",100000:"08",50000:"09",20000:"0a",
                10000:"0b",5000:"0c"}                                           #Standard Baudraten

    readbuf=bytearray([0]*18)
    Message=[]#{"data":None,"ID":None,"length":0,"Frformat":None,"Frtype":None}]
    Buserrors={"rec-errors":0,"tr-errors":0,"errorflags":""}
    timeout=0

    def __init__(self,canbaud,frtype,mode="normal",devname="USB-SERIAL CH340",baudrate=1228800,stopbits=1,timeout=1,writeTimeout=1,bytesize=8):
        self.timeout=timeout
        self.initdevice(canbaud,frtype,mode,devname,baudrate,stopbits,timeout,writeTimeout,bytesize)

    def initdevice(self,canBaudrate,frtype,mode,devname,baudrate,stopbits,timeout,writeTimeout,bytesize):
        self.canport=None


        for port,devname,VID in list_ports.comports():                          #Nach CH340 Device suchen
            if "USB-SERIAL CH340" in devname or "HL-340 USB-Serial" in devname or "QinHeng Electronics" in devname:
                print ("Found USB-CAN Device on ",port)

                self.canport=serial.Serial(port,baudrate,
                                    parity=serial.PARITY_NONE,
                                    stopbits=stopbits,timeout=timeout,
                                    writeTimeout=writeTimeout,bytesize=bytesize)

                break


        if not self.canport:
            raise("No USB-CAN Device found, exiting!")
        else:
            print ("USB-CAN Device ready, Baud: ",canBaudrate)

        self.setup(canBaudrate,frtype,mode)

        self.set_IDfilter([])                                                    #Disable IDFilter

        time.sleep(0.5)


    def setup(self,canBaudrate,frtype,mode):
        if canBaudrate in self.Baudraten.keys():                                #Init mit Standardbaudrate "00000"+self.mode[mode]+"010000000"
            self.send("00000000","000000"+self.mode[mode]+"01000000",mmtype="init",mftype="init",mfformat=frtype,Baud=canBaudrate)     #Init Nachricht

        else:                                                                   #Init mit individueller Baudrate
                                                                                #Can bps=36000000/(SYNC_SEG+BP1+BP2)/Pre Frequ          MAX 12000000bps
            SYNC_SEG=0x01

            x=int(36000000/(canBaudrate))

            BPlist=[]
            Freqlist=[]

            for BPs in range(3,26):

                PreFreq=min([int(x/BPs),1024])
                rest=x-BPs*PreFreq

                Freqlist.append(PreFreq)
                BPlist.append(rest*rest)

            BPs=BPlist.index(min(BPlist))+3
            PreFreq=Freqlist[BPs-3]

            BPs-=1

            if BPs>16:
                BP1=16
                BP2=BPs-16
            else:
                BP1=BPs-1
                BP2=1

            Baude=36000000/((SYNC_SEG+BP1+BP2)*PreFreq)
            print ("Individual Baud setting: ",Baude)
            PreFreq="{:04X}".format(PreFreq)
            strPreFreq=""
            strPreFreq+=PreFreq[2:4]
            strPreFreq+=PreFreq[0:2]
            self.send("00000000","000000"+"{:02X}".format(SYNC_SEG-1)+"{:02X}".format(BP1-1)+"{:02X}".format(BP2-1)+strPreFreq,mmtype="init_manbaud",mftype="init",mfformat=frtype,Baud=1000000)     #Init Nachricht


        time.sleep(0.01)



    def Busstatus(self):                                                            #Read Busstatus

        message=self.mtype["Busstatus"]+"0"*32+"04"                                  #04 ist die Ckecksumme
        message=self.mhead+message

        self.canport.write(bytearray.fromhex(message))
        self.rec()

        while self.readbuf[2]!=4:
            self.rec()




    def send(self, mfID, data="", mmtype="Trans-Rec",mftype="Standard",mfformat="ata",Baud=None):

        message=""

        if Baud and mmtype=="init":                                             #Wenn Initnachricht Baudrate setzen
            mftype=self.Baudraten[Baud]
        elif mmtype=="init_manbaud":
            mftype=self.Baudraten[1000000]
        else:
            mftype=self.frtype[mftype]

        if mmtype=="init":
            mlength="00"
            mfformat=self.frtype[mfformat]                                           #Frameformat setzen
        else:
            mlength="{:02X}".format(int(len(data)/2))                                         #Nachrichtenlänge setzen
            mfformat=self.frfmt[mfformat]                                           #Frameformat setzen
            data+="0"*(16-len(data))


        mmtype=self.mtype[mmtype]                                               #Nachrichtentyp



        if len(data)>16:
            raise ValueError("Max 8 Databytes")
        if len(mfID)!=8:
            raise ValueError

        ID=""                                       #Endian der ID ändern
        for i in range(0,4):
            ID+=mfID[7-(i*2+1)]
            ID+=mfID[7-i*2]

        mfID=ID

        message=mmtype+mftype+mfformat+mfID+mlength+data+"00"                       #Nachricht zusammensetzen

        mcks=sum(bytearray.fromhex(message))
        mcks="{:02X}".format(mcks)[-2:]

        message=self.mhead+message+mcks

        self.canport.write(bytearray.fromhex(message))


    def rec(self,timeout=None):
        message={"data":None,"ID":None,"length":0,"Frformat":None,"Frtype":None}

        buf=bytearray([0])

        a=""
        acttime=time.time()
        while 1:
            if  self.canport.readable():
                self.canport.readinto(buf)
                a+="{:02X}".format(buf[0])

            while len(a)>4:
                a=a[1:]

            if a=="AA55":
                break

            if self.timeout<(time.time()-acttime):
                return "timeout"

        if self.canport.readinto(self.readbuf)==len(self.readbuf):       #Auf Nachricht warten

            mcks=sum(self.readbuf[:-2])                #Checksum berechnen

            mcks="{:02X}".format(mcks)[-2:]

            if mcks!="{:02X}".format(self.readbuf[-1]):   #Checksum überprüfen
                raise ValueError("Checksum error",mcks,"{:02X}".format(self.readbuf[-1]),binascii.hexlify(self.readbuf))

            if self.readbuf[2]==int(self.mtype["Trans-Rec"]):                                                  #Normale Nachricht empfangen
                message["data"]=self.readbuf[8:-2]

                ID=""                                       #Endian der ID ändern
                for i in range(0,4):
                    ID+="{:02X}".format(self.readbuf[6-i])
                message["ID"]=ID

                message["length"]=self.readbuf[7]      #Datenlänge auslesen

                for key in self.frtype:
                    if self.readbuf[1]==int(self.frtype[key]):
                        message["Frtype"]=key              #Frametype auslesen

                for key in self.frfmt:
                    if self.readbuf[2]==int(self.frfmt[key]):
                        message["Frformat"]=key            #Frameformat auslesen

                self.Message.append(message)

                return self.mtype["Trans-Rec"]

            elif self.readbuf[0]==int(self.mtype["Busstatus"]):                                         # Busstatus empfangen
                self.Buserrors["rec-errors"]=int(self.readbuf[1])               #Anzahl recieve Errors
                self.Buserrors["tr-errors"]=int(self.readbuf[2])                #Anzahl Transmit Errors
                self.Buserrors["errorflags"]=self.readbuf[3:7]                  #Errorflags (genaue Bedeutung noch unbekannt)

                return self.mtype["Busstatus"]

            return "Unidentified Message"


    def close(self):
        self.canport.close()

    def open(self):
        self.canport.open()

    def flush(self):
        self.canport.flushInput()
        self.canport.flushOutput()
        del self.Message[:]
        #self.Message.append({"data":None,"ID":None,"length":0,"Frformat":None,"Frtype":None})
        self.readbuf=bytearray([0]*len(self.readbuf))

    def set_IDfilter(self,ID=[]):

        if len(ID)>52:
            raise ValueError("To much IDs")
        for ids in ID:
            if len(ids)!=8:
                raise ValueError

        IDs=""
        for ids in ID:
                                                   #Endian der ID ändern
            for i in range(0,4):
                IDs+=ids[7-(i*2+1)]
                IDs+=ids[7-i*2]

        message=self.mtype["IDFilter"]+"{:02X}".format(len(ID))+IDs                      #Nachricht zusammensetzen

        mcks=sum(bytearray.fromhex(message))
        mcks="{:02X}".format(mcks)[-2:]

        message=self.mhead+message+mcks

        while 1:
            if  self.canport.writable():
                if self.canport.write(bytearray.fromhex(message))>0:
                    break

            if time.time()-tim>self.timeout:
                return "timeout"

        #if len(ID)<1:
        time.sleep(0.6)


if __name__ == "__main__":

    USBCAN=USBCAN(500000,"Standard","normal")#"Standard","normal")
    try:
        #USBCAN.set_IDfilter(["00000584","00000604"])
        USBCAN.send("11111111","123456")
        #time.sleep(2)
        USBCAN.rec()
        print(USBCAN.Message)
        USBCAN.flush()
        print(USBCAN.Message)
    finally:
        USBCAN.close()

