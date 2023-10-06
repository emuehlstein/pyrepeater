# pyrepeater

a repeater controller for Retevis & Midland GRMS repeaters with the interface
board from www.gmrstwowayradio.com

## objectives
Asyncronously handle the following repeater behaviours: 

1) detect receive status of repeater
2) periodically "broadcast" repeater info (ex. CW ID)
3) log & record audio traffic
4) modes of operation: NORMAL, NET, ?
5) DTMF control?

## configuration
1) replace the files in the "sounds" directory with wav files crafted for your repeater.
2) run `export SERIAL_PORT=/dev/ttyUSB0`, replacing /dev/ttyUSB0 with the name of your serial port.
   
## usage
1) Install Python 3.11 and pipenv
2) In the pyrepeater/pyrepeater directory, run `pipenv install && pipenv shell`
3) run `python __init__.py`

