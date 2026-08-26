#!/usr/bin/env python3
"""Subscribe to the M62 the moment it appears, and decode what it says.

The card seems to announce its state ONCE, shortly after enumeration,
and only to whoever has already subscribed. A hand-typed command is
seconds late and misses it; this waits for the hidraw node to appear,
opens it and writes the subscribe and the state request immediately.

Run it, THEN plug the card in:

    sudo m62-listen.py            # wait for the card, then listen 30 s
    sudo m62-listen.py 60         # ... for 60 s
    sudo m62-listen.py --now      # do not wait, use the card already there

Every frame is printed decoded. A frame from the host has a bad
checksum (the vendor application does not sign its writes) and a frame
from the device has a good one, so the direction is printed too.
"""

import glob
import math
import os
import struct
import sys
import time

VENDOR = "152A"
PRODUCT = "875C"

TARGETS = {
    0x11: "device", 0x12: "identity",
    0x21: "IN 1", 0x22: "IN 2", 0x23: "AUX", 0x25: "BT", 0x27: "OTG IN",
    0x31: "Mix A left", 0x32: "Mix A right",
    0x33: "Mix B left", 0x34: "Mix B right",
    0x35: "Mix C left", 0x36: "Mix C right",
    0x51: "Loopback 1", 0x52: "Loopback 2",
    0x53: "Loopback 3", 0x54: "Loopback 4",
    0x55: "Loopback 5", 0x56: "Loopback 6",
    0x57: "Loopback 7", 0x58: "Loopback 8",
    0x61: "OTG OUT left", 0x62: "OTG OUT right",
    0x63: "HP left", 0x64: "HP right",
}

# what a property means depends on which side of the card it is on
IN_PROPS = {0x01: "meter", 0x02: "source", 0x03: "input power",
            0x04: "gain", 0x05: "mute", 0x06: "jack"}
OUT_PROPS = {0x02: "source", 0x03: "volume", 0x04: "mute", 0x06: "jack"}
DEV_PROPS = {0x18: "battery", 0x19: "blink", 0x24: "subscribe",
             0x26: "announce"}

UNITY = float(1 << 25)          # the mixer's 0 dB, in its own units

BUSES = {0x01: "Playback 1", 0x02: "Playback 2", 0x03: "Playback 3",
         0x04: "Playback 4", 0x05: "Playback 5", 0x06: "Playback 6",
         0x07: "Playback 7", 0x08: "Playback 8", 0x11: "Playback 9",
         0x12: "Playback 10"}

SOURCES = {1: "Mix A", 2: "Mix B", 3: "Mix C", 6: "IN 1", 7: "IN 2",
           8: "IN 1+2", 9: "AUX", 10: "BT", 11: "OTG IN",
           12: "Playback 1/2", 13: "Playback 3/4", 14: "Playback 5/6",
           15: "Playback 7/8", 16: "Playback 9/10"}


def crc16(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def frame(target, prop, value):
    body = bytes([0x20, 0x01, 0x01, target, prop])
    body += int(value).to_bytes(4, "big", signed=True)
    return (bytes([0x22, 0x33]) + body
            + crc16(body).to_bytes(2, "big") + bytes([0x66, 0x77]))


def find_node():
    """The hidraw node of the M62, or None."""
    for path in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        try:
            with open(os.path.join(path, "device/uevent")) as fh:
                text = fh.read()
        except OSError:
            continue
        if VENDOR in text.upper() and PRODUCT in text.upper():
            return "/dev/" + os.path.basename(path)
    return None


def describe(f):
    target, prop = f[5], f[6]
    value = struct.unpack(">i", f[7:11])[0]
    signed = struct.unpack(">H", f[11:13])[0] == crc16(f[2:11])
    who = "device" if signed else "host  "

    name = TARGETS.get(target, "%02x" % target)
    extra = ""

    if 0x31 <= target <= 0x36:
        # a mix: the property names the SOURCE channel and the value is
        # a linear gain, unity 2**25, except 0x15 which is the meter
        if prop == 0x15:
            pname = "meter"
            extra = "  (%.1f dBFS)" % (value / 10.0)
        else:
            pname = "from %s" % BUSES.get(prop, "ch %02x" % prop)
            if value > 0:
                extra = "  (%+.2f dB)" % (20 * math.log10(value / UNITY))
            else:
                extra = "  (mute)"
    else:
        if target == 0x11:
            pname = DEV_PROPS.get(prop, "%02x" % prop)
        elif target in (0x61, 0x62, 0x63, 0x64):
            pname = OUT_PROPS.get(prop, "%02x" % prop)
        else:
            pname = IN_PROPS.get(prop, "%02x" % prop)
        if pname == "source":
            extra = "  (%s)" % SOURCES.get(value, "?")
        elif pname == "meter":
            extra = "  (%.1f dBFS)" % (value / 10.0)

    return "%s  %-13s %-15s = %-11d%s" % (who, name, pname, value, extra)


def main():
    seconds = 30
    wait = True
    for arg in sys.argv[1:]:
        if arg == "--now":
            wait = False
        else:
            seconds = int(arg)

    node = find_node()
    if wait:
        print("waiting for the M62 -- plug it in now (Ctrl-C to stop)")
        while True:
            fresh = find_node()
            if fresh and fresh != node:
                node = fresh
                break
            time.sleep(0.01)
    elif not node:
        sys.exit("the M62 is not here, and --now was asked for")

    # the node can appear a moment before it can be opened
    fd = None
    for _ in range(200):
        try:
            fd = os.open(node, os.O_RDWR | os.O_NONBLOCK)
            break
        except OSError:
            time.sleep(0.01)
    if fd is None:
        sys.exit("cannot open %s" % node)

    print("listening on %s" % node)
    born = time.time()
    os.write(fd, frame(0x11, 0x24, 1))      # subscribe
    os.write(fd, frame(0x11, 0x26, 1))      # announce your state
    print("subscribed %.0f ms after the node opened\n"
          % ((time.time() - born) * 1000))

    end = time.time() + seconds
    seen = 0
    while time.time() < end:
        try:
            data = os.read(fd, 64)
        except BlockingIOError:
            time.sleep(0.002)
            continue
        except OSError as exc:
            print("read stopped: %s" % exc)
            break
        for off in range(0, max(0, len(data) - 14)):
            if (data[off] == 0x22 and data[off + 1] == 0x33
                    and data[off + 13] == 0x66
                    and data[off + 14] == 0x77):
                print("%7.3f s  %s" % (time.time() - (end - seconds),
                                       describe(data[off:off + 15])))
                seen += 1
                break
    os.close(fd)
    print("\n%d frames" % seen)


if __name__ == "__main__":
    main()
