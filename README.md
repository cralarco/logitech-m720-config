# Logitech M720 Button Configuration for Linux

This script maps the extra buttons of a Logitech M720 mouse to keyboard shortcuts on Linux.

The M720 is connected over **Bluetooth** directly to the computer (no Unifying/Logi Bolt receiver is needed). The buttons are configured via the HID++ protocol described in these documents:

 * [Logitech HID++2.0 Draft Specification](https://lekensteyn.nl/files/logitech/logitech_hidpp_2.0_specification_draft_2012-06-04.pdf)
 * [special keys and mouse buttons](https://lekensteyn.nl/files/logitech/x1b04_specialkeysmsebuttons.html#divertedButtonsEvent)

The script runs in the background as a `systemd` user service. It diverts the chosen buttons from the mouse firmware to the host and emits the matching key combination through a virtual keyboard (`uinput`).

This script is created for personal use only and may or may not work for your device. Use at your own risk.

# Default Button Mapping

| Button               | CID    | Sends                 | Effect                       |
|----------------------|--------|-----------------------|------------------------------|
| Side button (back)   | `0x53` | `Super` + `Page Up`   | Workspace left               |
| Side button (forward)| `0x56` | `Super` + `Page Down` | Workspace right              |
| Thumb button         | `0xD0` | `Shift` + `Print`     | Interactive screenshot       |

The mapping is defined in `DIVERTED_BUTTONS` in [`m720_config/__init__.py`](m720_config/__init__.py). The other buttons keep their default behavior.

# How to Use

## Requirements

 * Python 3
 * [`python-evdev`](https://python-evdev.readthedocs.io/) (`sudo apt install python3-evdev` on Debian/Ubuntu)
 * Write access to `/dev/uinput` and `/dev/hidraw*` for the logged-in user (provided by the udev rules below)

## Installation

1. Clone the repository and install the package:

   ```
   $ pip install --user -e /path/to/logitech-m720-config
   ```

   This installs `m720-config` to `~/.local/bin` and pulls in `evdev`.

   > Make sure `~/.local/bin` is in your `PATH` variable

2. Install the udev rules so the logged-in user can access the mouse and `uinput` without root:

   ```
   $ sudo cp udev/70-m720-config.rules /etc/udev/rules.d/
   $ sudo udevadm control --reload-rules && sudo udevadm trigger
   ```

   The rules match the Bluetooth ID of the M720 (`046D:B015`) and `uinput`.

3. Install the systemd user service so the buttons are configured on login:

   ```
   $ mkdir -p ~/.config/systemd/user
   $ cp systemd/m720-config.service ~/.config/systemd/user/
   $ systemctl --user daemon-reload
   $ systemctl --user enable --now m720-config.service
   ```

   The unit runs `m720_config/__init__.py` from the repository path in `ExecStart`. If you cloned the repository somewhere else, edit that path first.

## Run the script manually

To try it without the service, run in a terminal:

```
$ m720-config
```

The script prints the mouse it found and `LISTENING`, then reports each diverted button press. Stop it with `Ctrl+C`; the buttons are returned to their default behavior on exit.

## Check your configuration

 * View the service log: `journalctl --user -u m720-config.service -f`

## Create your own configuration

Edit `DIVERTED_BUTTONS` in `m720_config/__init__.py` to change which buttons are diverted and which key combination each one sends. Each entry is a list of `ecodes.KEY_*` values pressed together, for example:

```python
DIVERTED_BUTTONS = {
    0x53: [ecodes.KEY_LEFTMETA, ecodes.KEY_PAGEUP],
}
```

Restart the service after changing the file:

```
$ systemctl --user restart m720-config.service
```

### Button CID mapping

| CID    | Button                 |
|--------|------------------------|
| `0x50` | ![](buttons/lmb.png)   |
| `0x51` | ![](buttons/mmb.png)   |
| `0x52` | ![](buttons/rmb.png)   |
| `0x53` | ![](buttons/btn8.png)  |
| `0x56` | ![](buttons/btn9.png)  |
| `0x5B` | ![](buttons/btn6.png)  |
| `0x5D` | ![](buttons/btn7.png)  |
| `0xD0` | ![](buttons/thumb.png) |
| `0xD7` | unknown                |

### How it works

1. The script finds the M720 by looking for `M720` in the `hidraw` device entries.
2. It asks the mouse for the Reprogrammable Controls feature (`0x1B04`) and sets the buttons in `DIVERTED_BUTTONS` to *divert* mode, so the mouse reports presses instead of sending its default action.
3. Each diverted-button report lists the CIDs currently held down. A CID that was not held before is a new press, and the script sends the mapped key combination through a virtual keyboard named `m720-config`.
4. On exit (including `SIGTERM` from systemd) the buttons are set back to normal.

# How to Get Gestures On Linux?

You can use [Easystroke](https://github.com/thjaeger/easystroke/wiki) to add gesture support to your mouse. Use the thumb button as your gesture button and the behavior should be similar to that created by Logitech Options.
