#!/usr/bin/python3
# -*- coding: utf-8 -*-

import Tools.USBCAN.USBCANCH340 as can
import threading
import time
import sys
import select

class candriver(threading.Thread):
    
    USBCAN = None
    
    def __init__(self):
        threading.Thread.__init__(self)
        self.USBCAN = can.USBCAN ( 500000 , "Standard" , "normal" , timeout=0.005)
        self.USBCAN.flush()
        
    def run(self):
        self.starttime=time.time()
        while 1:
            
            if select.select([sys.stdin],[],[],0)[0]:
                line = sys.stdin.readline()
                line = line.strip("\n")
                
                if "send " in line and "#" in line:
                    self.cansend(line.split("send ")[-1])
                
                else:
                    if "#" in line:
                        self.cansend(line)
                    
            if self.USBCAN.rec(1)=="timeout":
                print("timeout")
            else:
                
                while len(self.USBCAN.Message) > 0:
                    acttime = time.time()
                    message = self.USBCAN.Message.pop(0)
                    print( " (" + "{:.6f}".format(acttime) +
                    ") can0  RX - -  " + message["ID"][-3:] +
                    "   ["+ str(message["length"]) + "]  " +
                    ' '.join('{:02X}'.format(x) for x in message["data"]) )
            
            
    def cansend(self, adddata):
        addr = adddata.split( "#" ) [0]
        data = adddata.split( "#" ) [1]
        
        while len( addr ) < 8:
            addr = "0" + addr
        
        self.USBCAN.send( addr , data )
        acttime = time.time()
                   
        print( " (" + "{:.6f}".format(acttime) +
        ") can0  TX - -  " + addr[-3:] +
        "   ["+ str(1) + "]  " +
        str(data) )
        
    def close(self):
        self.USBCAN.close()
    
    def __del__(self):
        self.close()

if __name__ == "__main__":
    
    canthread=candriver()
    #canthread.cansend( "000#8100" )
    canthread.start()
    
    # USBCAN=can.USBCAN(500000,"Standard","normal")
    # try:
    #     #USBCAN.set_IDfilter(["00000584","00000604"])
    #     USBCAN.send("11111111","123456")
    #     #time.sleep(2)
    #     print(USBCAN.rec(10))
    #     print(USBCAN.Message)
    #     USBCAN.flush()
    #     print(USBCAN.Message)
    # finally:
    #     USBCAN.close()