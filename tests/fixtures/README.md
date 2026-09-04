<!-- The FACTS in this document are placed in the public domain
     (CC0-1.0), on the same footing as PROTOCOL.md beside it. -->

# Captures

Two usbmon captures kept because PROTOCOL.md rests on them. Both were
taken on 4 September 2026, firmware V87.05.45.48.27, with the kernel
driver bound and a `hidraw` listener alongside it.

Between them they establish the one thing about this protocol that is
easiest to get wrong, and that this document got wrong twice before
these captures were taken: **the card does report its state, and the
reason it looks as though it does not is that something else on the
host usually overwrites it first.**

## Conditions

Both runs had every state restorer on the host disabled. This is not
optional, and omitting any one of them produces a convincing false
negative:

```
sudo systemctl mask alsa-restore.service alsa-state.service
sudo ln -s /dev/null /etc/udev/rules.d/90-alsa-restore.rules
sudo udevadm control --reload
sudo mv /var/lib/alsa/asound.state /var/lib/alsa/asound.state.bak
systemctl --user mask wireplumber pipewire pipewire-pulse
systemctl --user stop wireplumber pipewire pipewire-pulse
```

Note that `alsa-restore.service` has `ExecStop=alsactl store`, so
stopping it rewrites the file you were about to move aside. Mask
first, move second, and check:

```
ls -l /var/lib/alsa/asound.state          # must not exist
systemctl --user is-active wireplumber    # inactive
```

The second trap: **the card reports the gain only of an input whose
jack is present.** A capture with nothing plugged in shows no gains
and looks exactly like a card that cannot be read. Both runs had a
coupler in IN 1 and headphones in HP.

## m62-listen-3.txt

An ordinary replug, thirty seconds. Mic-1 was set to 50 by hand on the
front panel beforehand.

What it shows:

* at 5.171 s, inbound `0x21/04 = 50` -- the panel value, from the card;
* twenty-two outgoing frames in the whole run, every one of them
  `0x11/24` or `0x11/26`. Nothing wrote that value;
* the two-wave shape: jacks at about 0.9 s, then at about 5.2 s the
  jacks again plus the output mutes plus the gain of the connected
  input;
* no `0x64/03`, no `0x62/03`, no selector, although `0x64/06 = 1` says
  the headphones were plugged in. Output volumes are not in the
  connect report.

## m62-knob.txt

Forty seconds on a live card, knobs turned by hand.

What it shows:

* Mic-1 taken from 50 up to 53 and back to 50: seventeen inbound
  `0x21/04` frames, one per step;
* the headphone volume turned likewise: five inbound `0x64/03` frames,
  32, 33, 33, 32, 31. So an output volume *is* readable -- just not
  until a hand moves it;
* an output pair reports only `0x64`, never its partner `0x63`;
* twenty-two outgoing frames, all `0x11/24` or `0x11/26` again;
* nothing about a source selector, in either run, ever. The selectors
  have no front-panel control, so no event exists for the card to
  report -- which is why they are unreadable in principle rather than
  for want of a command.

## Reading them

Plain-text usbmon (`/sys/kernel/debug/usb/usbmon/<bus>u`). The M62's
vendor interface is interrupt IN on endpoint 3 and interrupt OUT on
endpoint 2; the device number changes on every replug, so find it by
looking for the endpoint pair rather than by name.

Protocol frames start `22 33 20 01 01`. Data for an OUT transfer is on
the `S` (submit) line, for an IN transfer on the `C` (callback) line --
taking both from `C` silently loses every outgoing frame. Timestamps
are 32-bit microseconds and wrap every 4295 s.

Frame layout, target at byte 5 and property at byte 6:

```
22 33 | 20 01 01 | TT | PP | s32 value BE | CRC16 BE | 66 77
```

A one-liner to see everything that is not a meter:

```python
for line in open("m62-knob.txt", errors="replace"):
    f = line.split()
    if len(f) < 6 or "=" not in line:
        continue
    out = f[3].startswith("Io")
    if (out and f[2] != "S") or (not out and f[2] != "C"):
        continue
    d = "".join(line.split("=")[1].split())
    if not d.startswith("22332001"):
        continue
    b = bytes.fromhex(d[:32])
    if b[6] in (0x01, 0x15, 0x0b, 0x0c) and not out:
        continue                       # meters
    v = int.from_bytes(b[7:11], "big", signed=True)
    print("%s 0x%02x/0x%02x = %d" % ("OUT" if out else "IN ",
                                     b[5], b[6], v))
```
