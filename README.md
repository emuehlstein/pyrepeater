# pyrepeater

a software controller for repeaters and interfaces which work via serial
control and use soundcard audio

tested with an interface board from www.gmrstwowayradio.com and Retevis 97S

presently intended for use on Raspberry Pi OS

## features
- busy detection (receiving currently)
- idle/active detection (used recently)
- periodic id & repeater annoucements
- recording of received transmissions

## configuration
1) replace the files in the "sounds" directory with wav files crafted for your repeater.
2) copy pyrepeater/.env.example to pyrepeater/.env and edit the settings to reflect your preferences.
   
## usage
1) Install Python 3.11 and pipenv
2) In the pyrepeater/pyrepeater directory, run `pipenv install && pipenv shell`
3) run `python __init__.py`

## roadmap
- modes (day/night/net)
- ansible
  - systemd service
  - blacklist headphone jack modules
