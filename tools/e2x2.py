#!/usr/bin/env python3
"""Read and write the vendor HID channel of a Topping E2x2 OTG (152a:8756).

    sudo e2x2.py listen                      # what the card sends, until Ctrl-C
    sudo e2x2.py listen --seconds 30 --meter 31/01 --meter 21/04
    sudo e2x2.py listen --wait --seconds 15  # from the moment it is switched on
    sudo e2x2.py send 21/01=0                # MON off on IN 1
    sudo e2x2.py send @frames.txt            # one TT/PP=VALUE per line

listen opens the card's hidraw node read-only, so it cannot write
anything. With --wait it first waits for the card to go away and come
back, then opens it at once, so that what the card says right after
power-on is not missed. send writes the frames given, in the order given, in the
format Control Center uses -- 22 33 20 01 01 TT PP value, checksum 0000
-- and then prints what the card sends during --wait seconds.

TT and PP are hexadecimal, as in PROTOCOL.md; VALUE is an integer,
decimal or 0x-prefixed, and may be negative. Meters are left out unless
named with --meter; a named meter is printed once a second as the
highest level of that second, or as "below -96" when the card sent
none, which it does only for a level above -96 dB.
"""

import argparse
import glob
import math
import os
import select
import struct
import sys
import time

HID_ID = "HID_ID=0003:0000152A:00008756"

TARGETS = {
    0x11: "device", 0x12: "identification",
    0x21: "IN 1", 0x22: "Mobile IN L", 0x23: "IN 2", 0x24: "Mobile IN R",
    0x31: "Output 1+2 L", 0x32: "Output 1+2 R",
    0x33: "Mobile OUT L", 0x34: "Mobile OUT R",
    0x35: "Output 1+2", 0x36: "Mobile OUT", 0x37: "Output 1+2 jacks",
    0x51: "Loopback 1", 0x52: "Loopback 2", 0x53: "Loopback 3",
    0x54: "Loopback 4", 0x55: "Loopback 5", 0x56: "Loopback 6",
    0x57: "Loopback 1+2", 0x58: "Loopback 3+4", 0x59: "Loopback 5+6",
    0x5a: "S/PDIF OUT L", 0x5b: "S/PDIF OUT R", 0x5c: "S/PDIF OUT",
}
for _n in range(8):
    TARGETS[0x41 + _n] = "Playback %d" % (_n + 1)
for _n, _mix in enumerate("ABCD"):
    TARGETS[0x61 + 2 * _n] = "Mix %s L" % _mix
    TARGETS[0x62 + 2 * _n] = "Mix %s R" % _mix

SOURCES = {1: "IN 1", 2: "Mobile IN", 3: "IN 2", 5: "IN 1+2",
           7: "Playback 1/2", 8: "Playback 3/4", 9: "Playback 5/6",
           10: "Playback 7/8", 11: "Mix A", 12: "Mix B", 13: "Mix C",
           14: "Mix D"}

INPUTS = range(0x21, 0x25)
OUTPUTS = list(range(0x31, 0x35)) + list(range(0x51, 0x57)) + [0x5a, 0x5b]
SELECTORS = {(0x35, 1), (0x36, 1), (0x57, 1), (0x58, 1), (0x59, 1),
             (0x5c, 1)}


def crc16(data):
    """CRC-16/MODBUS, as the card signs its frames over bytes 2..10."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def frame(target, prop, value, sign=False):
    body = bytes([0x20, 0x01, 0x01, target, prop])
    body += int(value).to_bytes(4, "big", signed=True)
    check = crc16(body) if sign else 0
    return bytes([0x22, 0x33]) + body + check.to_bytes(2, "big") + b"\x66\x77"


def is_meter(target, prop):
    return ((target in INPUTS and prop == 4)
            or (target in OUTPUTS and prop in (1, 2))
            or (0x41 <= target <= 0x48 and prop == 1))


def q25(value):
    return "-inf" if value <= 0 else "%+.2f dB" % (20 * math.log10(value / 2**25))


def meaning(target, prop, value):
    """What a frame says, in the words of PROTOCOL.md."""
    if is_meter(target, prop):
        return "meter %.1f dB" % (value / 10)
    if target in INPUTS:
        if prop == 5:
            return "gain %s%s" % (q25(abs(value)), ", phase inverted" if value < 0 else "")
        return "%s %s" % ({1: "MON", 2: "48V", 3: "INST"}.get(prop, "?"),
                          {0: "off", 1: "on"}.get(value, value))
    if (target, prop) in SELECTORS:
        return "source %d %s" % (value, SOURCES.get(value, "(not offered by the program)"))
    if prop == 3 and (target in OUTPUTS):
        return "fader %s" % q25(value)
    if 0x61 <= target <= 0x68:
        return "column %02x: %s" % (prop, q25(value))
    if (target, prop) == (0x35, 2):
        return "headphone amplifier gain switch %d" % value
    if (target, prop) == (0x35, 3):
        return "monitor mix knob %d" % value
    if target == 0x37 and prop in (1, 3, 5):
        return "%s %s" % ({1: "headphone", 3: "TRS", 5: "AUX"}[prop],
                          {0: "off", 1: "on"}.get(value, value))
    if (target, prop) == (0x11, 6):
        return "OTG port: %s" % {0: "nothing", 1: "phone"}.get(value, value)
    if target == 0x12:
        return "%s V%d.%02d" % ({1: "hardware", 2: "firmware"}.get(prop, "?"),
                                (value >> 16) & 0xFFFF, value & 0xFFFF)
    return "%d" % value


def describe(target, prop, value):
    return "%02x/%02x  %-16s %s" % (target, prop, TARGETS.get(target, "?"),
                                     meaning(target, prop, value))


def parse_frame(text):
    try:
        address, value = text.split("=")
        target, prop = (int(part, 16) for part in address.split("/"))
        value = int(value, 0)
    except ValueError:
        raise argparse.ArgumentTypeError("not TT/PP=VALUE: %r" % text)
    if not (0 <= target <= 0xFF and 0 <= prop <= 0xFF
            and -2**31 <= value < 2**31):
        raise argparse.ArgumentTypeError("out of range: %r" % text)
    return target, prop, value


def parse_meter(text):
    try:
        target, prop = (int(part, 16) for part in text.split("/"))
    except ValueError:
        raise argparse.ArgumentTypeError("not TT/PP: %r" % text)
    if not is_meter(target, prop):
        raise argparse.ArgumentTypeError("not a meter: %r" % text)
    return target, prop


def find_node(required=True):
    found = []
    for path in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        try:
            with open(os.path.join(path, "device/uevent")) as fh:
                if HID_ID in fh.read().upper():
                    found.append("/dev/" + os.path.basename(path))
        except OSError:
            continue
    if not found:
        if not required:
            return None
        sys.exit("no E2x2 OTG (152a:8756) found")
    if len(found) > 1:
        sys.exit("more than one E2x2 OTG: %s; name one with --node" % " ".join(found))
    return found[0]


class Printer:
    """Prints the card's frames: every non-meter frame as it comes, the
    named meters once a second."""

    def __init__(self, meters, start):
        self.meters = meters
        self.start = start
        self.second = 0
        self.peak = {}

    def flush_until(self, now):
        while self.meters and now - self.start >= self.second + 1:
            for target, prop in self.meters:
                level = self.peak.get((target, prop))
                print("%8.3f  %02x/%02x  %-16s meter %s" % (
                    self.second + 1, target, prop, TARGETS.get(target, "?"),
                    "below -96" if level is None else "%.1f dB" % (level / 10)))
            self.peak.clear()
            self.second += 1

    def report(self, data, now):
        self.flush_until(now)
        for off in range(0, len(data) - 14):
            if not (data[off] == 0x22 and data[off + 1] == 0x33
                    and data[off + 13] == 0x66 and data[off + 14] == 0x77):
                continue
            f = data[off:off + 15]
            target, prop = f[5], f[6]
            value = struct.unpack(">i", f[7:11])[0]
            signed = struct.unpack(">H", f[11:13])[0] == crc16(f[2:11])
            if is_meter(target, prop):
                if (target, prop) in self.meters:
                    key = (target, prop)
                    self.peak[key] = max(value, self.peak.get(key, value))
                continue
            print("%8.3f  %s%s" % (now - self.start, describe(target, prop, value),
                                   "" if signed else "  [bad checksum]"))
        sys.stdout.flush()


def pump(fd, printer, until):
    """Read the card until the given time; False if the node went away."""
    while True:
        now = time.monotonic()
        if until is not None and now >= until:
            printer.flush_until(now)
            return True
        timeout = 0.2 if until is None else min(0.2, until - now)
        ready, _, _ = select.select([fd], [], [], timeout)
        now = time.monotonic()
        if not ready:
            printer.flush_until(now)
            continue
        try:
            data = os.read(fd, 64)
        except OSError as exc:
            print("read stopped: %s" % exc)
            return False
        if not data:
            return False
        printer.report(data, now)


def main():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--node", help="hidraw node, if not found by itself")
    common.add_argument("--meter", action="append", type=parse_meter,
                        default=[], metavar="TT/PP", help="a meter to print")
    parser = argparse.ArgumentParser(
        description=__doc__, fromfile_prefix_chars="@",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    listen = sub.add_parser("listen", parents=[common],
                            help="print what the card sends")
    listen.add_argument("--seconds", type=float,
                        help="stop after this long (default: Ctrl-C)")
    listen.add_argument("--wait", action="store_true",
                        help="wait for the card to be switched off and on")
    send = sub.add_parser("send", parents=[common],
                          help="write frames, then listen")
    send.add_argument("frames", nargs="+", type=parse_frame,
                      metavar="TT/PP=VALUE")
    send.add_argument("--sign", action="store_true",
                      help="sign the frames instead of writing checksum 0000")
    send.add_argument("--gap", type=float, default=0.002,
                      help="seconds between frames (default 0.002)")
    send.add_argument("--wait", type=float, default=1.0,
                      help="seconds to listen afterwards (default 1)")
    args = parser.parse_args()

    flags = os.O_RDONLY if args.command == "listen" else os.O_RDWR
    if args.command == "listen" and args.wait:
        print("waiting: switch the card off, then on (Ctrl-C to stop)")
        try:
            while find_node(required=False):
                time.sleep(0.01)
            node = None
            while not node:
                time.sleep(0.01)
                node = find_node(required=False)
        except KeyboardInterrupt:
            return
        # the node can appear a moment before it can be opened
        for _ in range(200):
            try:
                fd = os.open(node, flags | os.O_NONBLOCK)
                break
            except OSError:
                time.sleep(0.01)
        else:
            sys.exit("cannot open %s" % node)
    else:
        node = args.node or find_node()
        try:
            fd = os.open(node, flags | os.O_NONBLOCK)
        except OSError as exc:
            sys.exit("cannot open %s: %s" % (node, exc))
    start = time.monotonic()
    printer = Printer(args.meter, start)
    print("%s on %s%s" % (args.command, node,
                          " (read-only)" if args.command == "listen" else ""))
    try:
        if args.command == "listen":
            until = None if args.seconds is None else start + args.seconds
            pump(fd, printer, until)
        else:
            for target, prop, value in args.frames:
                os.write(fd, frame(target, prop, value, args.sign))
                print("%8.3f  %s  <- written" % (time.monotonic() - start,
                                                 describe(target, prop, value)))
                pump(fd, printer, time.monotonic() + args.gap)
            pump(fd, printer, time.monotonic() + args.wait)
    except KeyboardInterrupt:
        pass
    finally:
        os.close(fd)


if __name__ == "__main__":
    main()
