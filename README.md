# pyrepeater

a software controller for radio repeaters on raspberry pi

[![Watch the overview video](https://img.youtube.com/vi/eLTZQTEK4t4/hqdefault.jpg)](https://www.youtube.com/watch?v=eLTZQTEK4t4)

tested with:

- Raspberry GNU/Linux 12 (bookworm)
- serial interface board from [gmrstwowayradio.com](https://www.gmrstwowayradio.com)
- FTDI USB -> Serial cable
- Retevis 97S

## installation

1. Install Raspberry Pi OS 12 (Bookworm).
2. Install the system dependencies:

   ```sh
   sudo apt update
   sudo apt install --yes pipenv sox
   ```

3. Blacklist the HDMI drivers by editing `/boot/firmware/config.txt` and commenting the following lines:

   ```ini
   # Enable DRM VC4 V3D driver
   #dtoverlay=vc4-kms-v3d
   #max_framebuffers=2
   ```

4. Blacklist the headphone driver by editing `/etc/modprobe.d/blacklist-alsa.conf` and adding:

   ```text
   blacklist snd_bcm2835
   ```

5. Reboot:

   ```sh
   sudo reboot
   ```

6. Clone the repository and install its Python dependencies:

   ```sh
   mkdir -p ~/src
   git clone https://github.com/emuehlstein/pyrepeater.git ~/src/pyrepeater
   cd ~/src/pyrepeater/pyrepeater
   pipenv install
   ```

## configuration

1. Replace the files in the `sounds` directory with WAV files crafted for your repeater.
2. Copy the example environment file and edit it to reflect your preferences:

   ```sh
   cd ~/src/pyrepeater/pyrepeater
   cp .env.example .env
   $EDITOR .env
   ```
   
## usage

Run the controller from the `pyrepeater` directory:

```sh
cd ~/src/pyrepeater/pyrepeater
pipenv run python __init__.py
```

Press `Ctrl+C` to stop it.

## deployment with ansible

The checked-in Ansible playbook targets `repeaterpi.local` and installs the application as a systemd service. Update `ansible/inventory.yaml` if your Raspberry Pi uses a different hostname or connection settings, then run:

```sh
cd ~/src/pyrepeater
ansible-playbook -i ansible/inventory.yaml ansible/site.yaml
```

After deployment, manage the service on the Raspberry Pi with:

```sh
sudo systemctl status pyrepeater
sudo systemctl restart pyrepeater
sudo journalctl -u pyrepeater -f
```

## settings

the following ENV variables should be set in the .env file prior to entering
the pipenv virtual environment

- `SERIAL_PORT=/dev/ttyUSB0`
   - the location of your serial device

- `PRE_TX_DELAY=1.0`
   - the number of seconds (float) to wait between enabling the serial pins and beginning the transmission audio

- `POST_TX_DELAY=1.0`
   - the number of seconds (float) to wait between ending the transmission and disabling the serial pins

- `FCC_ID=WRXC682`
   - currently unused (future: CW ID generation)

- `SCHEDULE_TOH=False`
   - currently unused (future: timed periods relative to top of hour or start time)

- `ID_MINS=15`
   - period of CW ID announcements in minutes (int)

- `RPT_INFO_MINS=60`
   - period of repeater info announcements in minutes (int)

- `ID_WHEN_ASLEEP=False`
   - send CW IDs when repeater is idle for a prolonged period

- `RPT_INFO_WHEN_ASLEEP=False`
   - send repeater info messages when repeater is idle for a prolonged period

- `SLEEP_AFTER_MINS=10`
   - after this many minutes of inactivity, put the repeater in sleep mode

- `WAKE_AFTER_SEC=2`
   - if repeater is asleep and becomes busy, wait this many seconds (int) before transitioning back to active state (prevents short key ups from disrupting sleep)

- `MIN_REC_SEC=2`
   - minimum seconds for a valid recording (WAV file will be deleted if it does not exceed this length)

- `PARROT_MODE=False`
   - when enabled, the repeater plays back each recorded transmission immediately after it ends, useful for range testing while mobile


## roadmap
- repeater modes (day/night/net)
- ansible
  - systemd service
  - blacklist headphone jack modules
- single command install (ie. homebrew/ohmyzsh curl .....)
