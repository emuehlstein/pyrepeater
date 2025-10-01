# pyrepeater

a software controller for radio repeaters on raspberry pi

tested with:
- Raspberry GNU/Linux 12 (bookworm)
- serial interface board from www.gmrstwowayradio.com
- FTDI USB -> Serial cable
- Retevis 97S

## installation
1) Install Raspberry Pi OS 13
2) install sox (audio) `sudo apt install sox
3) blacklist the hdmi drivers `sudo vim /etc/boot/firmware/config.txt` comment the following lines: ```
# Enable DRM VC4 V3D driver
#dtoverlay=vc4-kms-v3d
#max_framebuffers=2
```
4) blacklist the headphone driver `sudo vim /etc/modprobe.d/blacklist-alsa.conf` and add the line `blacklist snd_bcm2835`
5) reboot
1) clone the repository into ~/src/
2) install Python 3.11 & pipenv `sudo apt install pipenv`
3) cd to ~/src/pyrepeater/pyrepeater/
4) run `pipenv install`

## configuration
1) replace the files in the "sounds" directory with wav files crafted for your repeater.
2) copy pyrepeater/.env.example to pyrepeater/.env and edit the settings to
   reflect your preferences. (see settings below)
   
## usage
1) cd to pyrepeater/pyrepeater
2) run `pipenv shell`
3) run `python __init__.py`

## settings

the following ENV variables should be set in the .env file prior to entering
the pipenv virtual environment

 - SERIAL_PORT=/dev/ttyUSB0
    - the location of your serial device

 - PRE_TX_DELAY=1.0
    - the number of seconds (float) to wait between enabling the serial pins and beginning the transmission audio

 - POST_TX_DELAY=1.0
    - the number of seconds (float) to wait between ending the transmission and disabling the serial pins

 - FCC_ID=WRXC682
    - currently unused. (future: cw id generation)

 - SCHEDULE_TOH=False
    - currently unused. (future: timed periods relative to top of hour or start time)

 - ID_MINS=15
    - period of CW ID annoucements in minutes (int)

 - RPT_INFO_MINS=60
    - period of repeater info annoucements in minutes (int)

 - ID_WHEN_ASLEEP=False
    - send CW IDs when repeater is idle for a prolonged period

 - RPT_INFO_WHEN_ASLEEP=False
    - send repeater info messages when repeater is idle for a prolonged period

 - SLEEP_AFTER_MINS=10
    - after this many minutes of inactivity, put the repeater in sleep mode

 - WAKE_AFTER_SEC=2
    - if repeater is asleep and becomes busy, wait this many seconds (int) before transitioning back to active state (prevents short key ups from disrupting sleep)

 - MIN_REC_SEC=2
    - minimum seconds for a valid recording (wav file will be deleted if it does not exceed this length)


## roadmap
- repeater modes (day/night/net)
- ansible
  - systemd service
  - blacklist headphone jack modules
- single command install (ie. homebrew/ohmyzsh curl .....)
