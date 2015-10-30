import sys
import serial
from serial.tools import list_ports
import time

class USBCAN:
    mtype={"init":"02","Trans-Rec":"01","init_manbaud":"03"}                                        #Messagetype: "init" um CH340 Device zu parametrieren, "Trans-Rec" für CAN Transmit und Recieve
    frtype={"Standard":"01","Extended":"02","init":"03"}                        #Frametype
    frfmt={"ata":"01","Remote":"02"}                                            #Frameformat
    mhead="aa55"                                                                #Header für jede Nachricht an CH340 Device
    Baudraten={1000000:"01",800000:"02",500000:"03",400000:"04",250000:"05",
                200000:"06",125000:"07",100000:"08",50000:"09",20000:"0a",
                10000:"0b",5000:"0c"}                                           #Standard Baudraten
    
    readbuf=bytearray([0]*20)
    Message={"data":None,"ID":None,"length":0,"Frformat":None,"Frtype":None}
    
    def __init__(self,canbaud,devname="USB-SERIAL CH340",baudrate=1228800,stopbits=1,timeout=1,bytesize=8):
        
        self.initdevice(canbaud,devname,baudrate,stopbits,timeout,bytesize)
        
        time.sleep(1)
        
    def initdevice(self,canBaudrate,devname="USB-SERIAL CH340",baudrate=1228800,stopbits=1,timeout=1,bytesize=8):
        self.canport=None
        
        
        for port,devname,VID in list_ports.comports():                          #Nach CH340 Device suchen
            if "USB-SERIAL CH340" in devname:
                print ("Found USB-CAN Device on ",port)
                
                self.canport=serial.Serial(port,1228800,
                                    parity=serial.PARITY_NONE,
                                    stopbits=1,timeout=1,
                                    bytesize=8)
                                    
                break
        
        
        if not self.canport:
            raise("No USB-CAN Device found, exiting!")
        else:
            print ("USB-CAN Device ready, Baud: ",canBaudrate)
               
        self.canport.close()
        self.canport.open()
        
        if canBaudrate in self.Baudraten.keys() and None:                                #Init mit Standardbaudrate
            self.send("00000000",0,"0000000010000000",mmtype="init",mftype="init",mfformat="Remote",Baud=canBaudrate)     #Init Nachricht
            
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
            
            self.send("00000000",0,"000000"+"{:02X}".format(SYNC_SEG-1)+"{:02X}".format(BP1-1)+"{:02X}".format(BP2-1)+strPreFreq,mmtype="init_manbaud",mftype="init",mfformat="Remote",Baud=1000000)     #Init Nachricht
            
            
        self.canport.close()
        self.canport.open()
        
        
    def send(self, mfID, mlength, data, mmtype="Trans-Rec",mftype="Standard",mfformat="ata",Baud=None):
        
        message=""
        
        if Baud and mmtype=="init":                                             #Wenn Initnachricht Baudrate setzen
            mftype=self.Baudraten[Baud]
        elif mmtype=="init_manbaud":
            mftype=self.Baudraten[1000000]
        else:
            mftype=self.frtype[mftype]
        
        mmtype=self.mtype[mmtype]                                               #Nachrichtentyp
        mfformat=self.frfmt[mfformat]                                           #Frameformat setzen
        mlength="0"+str(mlength)                                                #Nachrichtenlänge setzen
        
        if len(data)!=16:
            raise ValueError
        if len(mfID)!=8:
            raise ValueError
            
        message=mmtype+mftype+mfformat+mfID+mlength+data+"00"                       #Nachricht zusammensetzen
        
        mcks=sum(bytearray.fromhex(message))
       
        mcks="{:X}".format(mcks)[-2:]
      
        message=self.mhead+message+mcks
        
        self.canport.write(bytearray.fromhex(message))
        
    def rec(self):
        if self.canport.readable():
            
            while self.canport.inWaiting()<20:          #Auf Nachricht warten
                pass
            
            self.canport.readinto(self.readbuf)
            
            mcks=sum(self.readbuf[2:-2])                #Checksum berechnen
            
            mcks="{:X}".format(mcks)[-2:]
            
            if mcks!="{:X}".format(self.readbuf[-1]):   #Checksum überprüfen
                raise("Checksum error")
                
            self.Message["data"]=self.readbuf[10:-2]
           
            ID=""                                       #Endian der ID ändern
            for i in range(0,4):
                ID+="{:X}".format(self.readbuf[8-i])
            self.Message["ID"]=ID
            
            self.Message["length"]=self.readbuf[9]      #Datenlänge auslesen
            
            for key in self.frtype:
                if self.readbuf[3]==int(self.frtype[key]):
                    self.Message["Frtype"]=key              #Frametype auslesen
            
            for key in self.frfmt:
                if self.readbuf[4]==int(self.frfmt[key]):
                    self.Message["Frformat"]=key            #Frameformat auslesen
           
          
    def close(self):
        self.canport.close()
        
    def open(self):
        self.canport.open()

if __name__ == "__main__":
    
    USBCAN=USBCAN(55555)
    USBCAN.close()
   