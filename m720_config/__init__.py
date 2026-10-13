"""
logitech-m720-config - A config script for Logitech M720 button mappings
Copyright (C) 2017  Fin Christensen <christensen.fin@gmail.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import glob
import os
import select
import signal
import sys
import time

from evdev import UInput, ecodes

# Device index 0xFF addresses a mouse connected directly (Bluetooth) instead of through a receiver
DEVICE_INDEX = 0xFF
SOFTWARE_ID = 0xE # random number in [0x0;0xF]

FEATURE_ROOT = 0x0000
FEATURE_REPROG_CONTROLS = 0x1B04

# Buttons diverted to the host and the keyboard shortcut each one sends
DIVERTED_BUTTONS = {
    0x53: [ecodes.KEY_LEFTMETA, ecodes.KEY_PAGEUP],    # side button (back): workspace left
    0x56: [ecodes.KEY_LEFTMETA, ecodes.KEY_PAGEDOWN],  # side button (forward): workspace right
    0xD0: [ecodes.KEY_LEFTSHIFT, ecodes.KEY_SYSRQ],    # thumb button: interactive screenshot
}

def find_mouse ():
    for uevent in sorted (glob.glob ("/sys/class/hidraw/hidraw*/device/uevent")):
        with open (uevent) as f:
            if "M720" in f.read ():
                return "/dev/" + uevent.split ("/")[4]
    raise RuntimeError ("Logitech M720 not found, is it connected?")

class HidppMouse:
    # https://lekensteyn.nl/files/logitech/x1b04_specialkeysmsebuttons.html#divertedButtonsEvent
    # https://lekensteyn.nl/files/logitech/logitech_hidpp_2.0_specification_draft_2012-06-04.pdf
    def __init__ (self, path):
        self.fd = os.open (path, os.O_RDWR)
        self.feature_index = self.get_feature_index (FEATURE_REPROG_CONTROLS)

    def send (self, feature_index, function, params = b""):
        packet = bytes ([0x11, DEVICE_INDEX, feature_index, (function << 4) | SOFTWARE_ID]) + params
        os.write (self.fd, packet.ljust (20, b"\0"))

    def request (self, feature_index, function, params = b""):
        expected = (function << 4) | SOFTWARE_ID
        self.send (feature_index, function, params)
        deadline = time.monotonic () + 2
        while True:
            timeout = deadline - time.monotonic ()
            if timeout <= 0:
                raise TimeoutError ("no reply from the mouse")
            ready, _, _ = select.select ([self.fd], [], [], timeout)
            if not ready:
                continue
            data = os.read (self.fd, 20)
            if len (data) < 5 or data[1] != DEVICE_INDEX:
                continue
            if data[2] == 0xFF and data[3] == feature_index and data[4] == expected:
                raise RuntimeError (f"HID++ error 0x{data[5]:02X}")
            if data[2] == feature_index and data[3] == expected:
                return data

    def get_feature_index (self, feature):
        data = self.request (0, 0, bytes ([feature >> 8, feature & 0xFF]))
        return data[4]

    def set_divert (self, cid, divert):
        # flags: divert (bit 0), dvalid (bit 1), persist (bit 2, not set), pvalid (bit 3)
        flags = (1 if divert else 0) | (1 << 1) | (1 << 3)
        self.request (self.feature_index, 3, bytes ([cid >> 8, cid & 0xFF, flags, 0x00, 0x00]))

    def listen (self, on_press):
        # Each diverted-button event lists the CIDs currently held, so a CID not seen before is a new press
        held = set ()
        while True:
            data = os.read (self.fd, 20)
            if len (data) < 4 or data[0] != 0x11 or data[1] != DEVICE_INDEX:
                continue
            if data[2] != self.feature_index or data[3] >> 4 != 0:
                continue
            cids = set ()
            for i in range (4, len (data) - 1, 2):
                cid = int.from_bytes (data[i:i + 2], byteorder = 'big')
                if cid:
                    cids.add (cid)
            for cid in cids - held:
                on_press (cid)
            held = cids

    def close (self):
        os.close (self.fd)

class VirtualKeyboard:
    def __init__ (self):
        keys = {key for combo in DIVERTED_BUTTONS.values () for key in combo}
        self.ui = UInput ({ecodes.EV_KEY: sorted (keys)}, name = "m720-config")

    def tap (self, keys):
        for key in keys:
            self.ui.write (ecodes.EV_KEY, key, 1)
        self.ui.syn ()
        for key in reversed (keys):
            self.ui.write (ecodes.EV_KEY, key, 0)
        self.ui.syn ()

def main ():
    # systemd stops the service with SIGTERM, turn it into a normal exit so the buttons are restored
    signal.signal (signal.SIGTERM, lambda *_: sys.exit (0))

    path = find_mouse ()
    print (f"### MOUSE: {path} ###")
    mouse = HidppMouse (path)
    keyboard = VirtualKeyboard ()

    def on_press (cid):
        keys = DIVERTED_BUTTONS.get (cid)
        if keys:
            print (f"CID 0x{cid:04X} pressed")
            keyboard.tap (keys)

    try:
        for cid in DIVERTED_BUTTONS:
            mouse.set_divert (cid, True)
        print ("### LISTENING ###")
        mouse.listen (on_press)
    finally:
        for cid in DIVERTED_BUTTONS:
            try:
                mouse.set_divert (cid, False)
            except (OSError, RuntimeError, TimeoutError):
                pass
        mouse.close ()

if __name__ == "__main__":
    main ()
