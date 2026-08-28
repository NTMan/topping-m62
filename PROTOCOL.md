<!-- The FACTS in this document are placed in the public domain
     (CC0-1.0), deliberately and separately from the GPL on the code
     beside it: the most likely reader is someone carrying a table
     from here into a kernel patch, and the kernel is GPL-2.0-only.
     Copy any of it, with or without attribution. -->

# The Topping M62's vendor control protocol

The M62 is a USB audio interface whose analogue gains, output
volumes, mutes, source selectors, mixer matrix, loopback returns
and EQ are not reachable through the USB Audio Class. They live
behind a vendor channel on the card's HID interface, spoken by
Topping's own M Control Center, which has no Linux build.

This document is what was learned by capturing that channel and
by writing to it. It exists because the knowledge is the durable
part: tools get rewritten, and a protocol read out of the wire
once should not have to be read again.

## How to read the claims here

Every statement is one of three kinds, and they are marked where
it matters:

* **verified** -- reproduced on the card, usually by writing a
  value and hearing or measuring the result;
* **decoded** -- read out of captures and consistent across all
  of them, but not exercised in isolation;
* **guessed** -- a reading that fits, with nothing yet to
  confirm it. Treat these as questions, not facts.

Anything not marked is decoded.

## Cautions before anything else

**Never write to interface 3.** It is Application Specific /
DFU, presenting as "Topping DFU". A stray write there can brick
the card. The control channel is interface 4 and nothing else.

**The card has two memories.** A write changes the LIVE state.
The card's own storage is separate, and M Control Center has an
explicit "Save & download to device" for committing to it; on a
host without MCC the card comes up restored from that saved
state. The firmware also appears to commit the live state after
an idle interval on its own, which is why a value written and
then torn off the bus sometimes comes back and sometimes does
not (**guessed** -- the interval is not measured).

**The M62 has a battery, so unplugging USB is not a power
cycle.** Any persistence experiment that assumes it is will
produce mixed results, and did.

**M Control Center pushes its own cached state on connect.** A
card used from a Mac session holds MCC's settings afterwards, and
a Linux program and MCC on another host will fight over state.

## Transport

Interface 4 is HID class, subclass 0, protocol 0, with an
interrupt IN endpoint `0x83` and an interrupt OUT endpoint
`0x02`, `wMaxPacketSize` 64, `bInterval` 5.

**The control pipe is dead:** GET_REPORT and SET_REPORT stall
with EPIPE for every report type. The interrupt endpoints are the
only route (**verified**).

The report descriptor is a fig leaf: 27 bytes, Generic Desktop,
Usage 0x00, eight unnamed usages, 16 bytes in and out, **no
report ID**. `hid-generic` can build nothing useful from it.

## The frame

Fifteen bytes out, sixteen in:

```
22 33 | 20 01 01 | TT | PP | vvvvvvvv | cccc | 66 77
```

* `22 33` and `66 77` frame it;
* `20 01 01` is constant in everything captured;
* `TT` is the TARGET, `PP` the PROPERTY (the address map below);
* `vvvvvvvv` is an int32, **big endian**;
* `cccc` is **CRC-16/MODBUS over bytes 2..10 only**, stored MSB
  first. In kernel terms `crc16(0xffff, buf, 9)` is exactly this,
  so no private table is needed.

Inbound reports are the same with one `00` pad, making 16 bytes.
An idle poll returns sixteen zeros.

This was **verified** by rebuilding all 2619 frames of a live
capture byte for byte.

**Direction discriminator for reading a capture:** host to device
frames have a BAD checksum, because MCC does not sign its writes
and sends `0000`, and have no pad byte. Device to host frames
have a good checksum and are 16 bytes. The device does not verify
inbound checksums; sign anyway, and validate what is read.

Worked example, the save command:

```
22 33 20 01 01 11 05 00 00 00 01 bc 4c 66 77
```

## Subscription, the announce, and the keepalive

**The card is silent until subscribed.** One write of `11/24 = 1`
starts the whole notification stream, including panel presses
(**verified**).

**`11/24` is a keepalive, not a one-off.** M Control Center
repeats it every two seconds, and a listener that sends it once
gets a less complete stream (**verified**: the driver written
without the repeat lost notifications after minutes; with it,
panel-knob changes still arrive ten minutes after boot).

`11/26 = 1` asks the card to announce its state, so a program
need not cache what it wrote -- with one large exception below.

**The announce arrives in two waves.** Identification and jack
states come at once; gains land about 5 s later. A listener that
subscribes milliseconds after the device node appears sees both;
a subscribe typed by hand seconds later sees neither, because the
first wave is already gone. So: subscribe first, ask second,
expect the gains about five seconds in, and update a cache as
data arrives rather than waiting for a complete picture.

`11/20` brackets a bulk push: MCC writes `11/20 = 1`, then the
whole state within 0.3 s, then `11/20 = 0`, then `11/26` and
`11/24`. `11/01` is written at startup too. Both are **guessed**
to be session and batch markers rather than settings.

## The address map

Blocked by function:

| Block | Meaning |
| --- | --- |
| `0x11` | the device itself |
| `0x12` | identification |
| `0x2x` | inputs |
| `0x3x` | mixer matrix |
| `0x5x` | loopback sources |
| `0x6x` | outputs |
| `0x9x`, `0xax` | EQ |

### Inputs

Targets: `0x21` IN 1, `0x22` IN 2, `0x23` AUX, `0x25` BT, `0x27`
OTG IN.

| Property | Meaning |
| --- | --- |
| `01` | level meter |
| `02` | source select (on IN 1: 1 Mic1, 2 Mic-3.5, 3 Mic-HP) |
| `03` | input power (2.5 V bias or 48 V phantom, by source) |
| `04` | gain |
| `05` | mute (1 = muted) |
| `06` | jack present |
| `0a` | written 0 on every input at connect; meaning unknown, and it is NOT the mute at `05` |

Read `03` as INPUT POWER rather than "48 V": the same property
carries plug-in power for the 3.5 mm and headset sources.

**After a power or source change the card mutes that input for
about 3.7 s and then re-announces** (**verified**). A recording
started inside that window captures silence.

### Outputs

Targets: `0x61` and `0x62` are OTG OUT; `0x63` and `0x64` are HP.

| Property | Meaning |
| --- | --- |
| `02` | source select |
| `03` | volume |
| `04` | mute |
| `06` | jack present |

**Outputs come in PAIRS and the device announces only the second
of each pair.** Volume and mute must be written to BOTH targets
or the channels drift apart (**verified**).

**The source selector is the exception: it is written to ONE
target only** -- `0x64/02` for HP, `0x62/02` for OTG OUT.

### The source selector's values

One numbering serves the output selectors and the loopback
selectors alike:

```
 1 Mix A          9 AUX            13 Playback 3/4
 2 Mix B         10 BT             14 Playback 5/6
 3 Mix C         11 OTG IN         15 Playback 7/8
 6 IN 1          12 Playback 1/2   16 Playback 9/10
 7 IN 2
 8 IN 1+2
```

**4 and 5 are a gap.** Any enumerated control needs an
index-to-value table rather than a cast. Decoded one to one from
a capture of the whole dropdown walked in a stated order, and the
mechanism is **verified**: pointing HP away from the bus being
played silences it, pointing it back restores the sound.

### The selectors cannot be read, and that is now permanent

The device announces jack detection, battery, firmware version,
meters, mutes and the input gains by itself. It never announces
the SOURCE SELECTORS -- which bus each output listens to, which
source each loopback takes -- and no request has been found that
returns them. M Control Center does not appear to ask either: on
connect it pushes its whole workspace to the device rather than
reading anything back, which serves an application whose truth
lives in its own workspace file.

TOPPING were asked directly, on 21 August 2026, whether such a
command exists and whether one could be added. Their answer of
28 August, in their own order: the M62 has no official Linux
support, so they can give no technical support or compatibility
guarantee for a third-party Linux driver; the vendor control
interface -- command definitions, attribute mappings, status
reporting -- is a proprietary internal protocol, which they
cannot disclose and whose content, as derived from USB analysis,
they cannot confirm; for the same reason they cannot provide the
command that reads the current source selection; and they cannot
commit to adding such an interface, or to changing the reporting
mechanism, in a future firmware.

They asked for nothing. No objection to this document, no claim,
no request to stop -- a refusal to participate rather than a
dispute.

What it settles is the design. Unreadable selectors are not a
gap waiting on a firmware release, they are a property of the
device. Anything built on this protocol has to own the state it
writes: set a known selection when it attaches, and treat its
own cache as the truth from that moment. The cost is that a
device arriving from another host loses what that host left,
which is a fair price against a control that can be moved and
never read.

### The mixer matrix

**Target = mix and output channel, property = SOURCE channel,
value = linear gain in Q25.**

Mix A `0x31` / `0x32`, Mix B `0x33` / `0x34`, Mix C `0x35` /
`0x36` (left / right).

Source properties `01`/`02` Playback 1/2, `03`/`04` 3/4,
`05`/`06` 5/6, `07`/`08` 7/8, `11`/`12` (hex, i.e. 17/18)
Playback 9/10. MCC also writes `09`/`0a`, `0b`/`0c`, `0d`/`0e`,
`0f`/`10` -- four more stereo sources, **guessed** to be IN, AUX,
BT and OTG feeding the mixes.

Setting a stereo fader writes the diagonal and ZEROES the
off-diagonal.

### Loopback sources

Targets `0x51`..`0x58`. Property `02` is the source number from
the table above, `03` is a gain. Values seen in captures: 10 BT,
11 OTG IN, 12 Playback 1/2, 13 Playback 3/4.

### Device scope and identification

`11/05` save to the card's own memory (see the two memories
above), `11/18` battery percent, `11/19` a periodic blink flag
that is not ours, `11/24` subscribe / keepalive, `11/26` state
request. Device flags `11/04`, `11/1a`, `11/1b`, `11/1c`, `11/1e`
appear in an announce and are undecoded.

Identification lives at target `0x12`: property `01` = 100 =
hardware V1.00; `02`..`06` = 135, 5, 69, 72, 39 = hex
`87 05 45 48 27` = firmware V87.05.45.48.27. A quirk can
therefore be gated on a real firmware revision.

### EQ

Blocks `0x91`..`0x94` and `0xa1`..`0xaa`, with frequencies in
plain hertz (632, 7000 were seen) among the values. **Not
decoded further.**

`0x9b` tracks IN 1 to the tenth of a decibel including the -140
sentinel during muting, so it is IN 1 at another point in the
chain; the strip's MUTE lands there.

## Value encodings

### Meters

Tenths of a decibel, with **-140.0 dBFS (raw -1400) as the "no
signal" sentinel**.

### The mic preamps

`0x21/04` and `0x22/04` are a plain scale of whole decibels,
0..88.

### The two volume tapers

Everything else with a level uses an index 0..99, where index 0
is always -inf (mute) and index 99 always the maximum. The
unifying rule is **0.5 dB per step above -10 dB, 1 dB per step
below it**, with family A taking 2 dB below -52 dB because 98
steps cannot otherwise span 97 dB.

**Family A** -- AUX `0x23/04`, HP `0x63,0x64/03`; top +9 dB:

```
 1..19   2.0 dB/step   -88 .. -52
20..61   1.0 dB/step   -51 .. -10
62..99   0.5 dB/step   -9.5 .. +9
```

**Family B** -- BT `0x25/04`, OTG IN `0x27/04`, OTG OUT
`0x61,0x62/03`; top 0 dB:

```
 1..79   1.0 dB/step   -88 .. -10
80..99   0.5 dB/step   -9.5 .. 0
```

Both express as an ALSA `SNDRV_CTL_TLVT_DB_RANGE`.

Family A is **verified against the signal**: recording one source
at AUX gain 30 and at gain 60 gave rms -57.8 and -28.1 dBFS on
the left and -58.0 and -28.2 on the right, that is +29.7 and
+29.8 dB measured against the +30.0 dB the table predicts. Family
B is confirmed by a capture of stops at -inf/-80/-60/-40/-20/0,
which landed on indices 0/9/29/49/69/99 exactly.

### The mixer matrix

Linear gain in **Q25**: unity is `2^25` = 33554432 = 0 dB, 0 is
mute, +12 dB is 133582600. Stops taken from MCC reproduce to four
decimal places, and stray drag values decode to exact whole
decibels, which confirms the reading twice over.

## What the card never tells you

**The source selector is never announced.** There is no device to
host frame on property `02` in any capture, on a freshly
enumerated card, with a listener subscribed within milliseconds,
after `11/24` and `11/26`. Gains and volumes are echoed; the
selector is not.

This is a real design constraint, not an oversight to work
around: a program can write the selector and cannot learn where
it points. The honest shape is an extra first item meaning
"unknown, the device does not report this", refused as a change
and accepted as a no-op restore. **Writing a "sensible default"
at probe is the wrong answer** -- it is exactly MCC's habit of
pushing state on connect.

Topping have been asked whether any command returns the current
selection, and whether a future firmware could add one. No answer
yet.

## Still unknown

* the meaning of `11/01` and `11/20` beyond "markers";
* input property `0a`;
* device flags `11/04`, `11/1a`, `11/1b`, `11/1c`, `11/1e`;
* the EQ blocks;
* noise reduction and reverb, which were never captured. Both
  must be OFF for any measurement, alongside AUTO gain and EQ.

The AUTO button sends nothing at all: the auto-gain is entirely
in firmware.

## Where the boundary with the kernel runs

A usb-audio mixer quirk for this card is upstream at the time of
writing. What it covers, and what a userspace program should
therefore leave alone:

* input gains (IN 1, IN 2, AUX, BT, OTG IN),
* output volumes (HP, OTG OUT),
* the two output source selectors.

What remains reachable only through this protocol:

* the mixer matrix (three mixes, sixty cells),
* mutes,
* loopback source routing,
* input power (48 V and plug-in bias),
* the EQ blocks,
* `11/05`, the save-to-device command.

Note that the quirk road claims the HID interface for
snd-usb-audio and adds the card to `hid_ignore_list`, which means
**no `hidraw` node**, which means this protocol is not reachable
from userspace on a kernel carrying that quirk. A program built
on this document therefore either predates the quirk, runs on a
kernel without it, or waits for a kernel-side channel. That
trade-off was known and accepted when the road was chosen; it is
recorded here so nobody rediscovers it as a bug.

### The claim is a keep-out sign, not a key (**verified**)

It is easy to read the paragraph above as "the driver owns the
endpoints, so nobody else can use them". That is not what happens,
and the difference decides where a second program would have to
look for room.

Unbinding the vendor interface from `snd-usb-audio` by hand, while
the driver was loaded and the card was working:

```
# echo 3-1.3:1.4 > /sys/bus/usb/drivers/snd-usb-audio/unbind
# echo 3-1.3:1.4 > /sys/bus/usb/drivers/usbhid/bind
sh: line 1: echo: write error: No such device
```

The `unbind` succeeds and the sound card survives it untouched
(`aplay -l` still lists it). The `bind` fails with `ENODEV`, which
is `hid_add_device()` refusing a device that is in
`hid_ignore_list`. So handing the interface back is not enough:
**the entry in the ignore list is what keeps `usbhid` away, not
the claim.**

And in that state, with the interface owned by nobody, the driver
kept writing to the card. Reads had stopped -- the mixer control
froze on its last announced value, because usbcore kills the URBs
on an interface it is unbinding -- but `cset` still moved the
gain on the hardware. `usb_interrupt_msg()` takes a
`struct usb_device` and an endpoint address; interface ownership
is an agreement between drivers, not a lock on the wire.

Two consequences worth carrying:

* if a way for a driver and a userspace program to coexist is
  ever wanted, it lies on the `hid_ignore_list` side rather than
  the ownership side. `hid.quirks=...:0x40000000`
  (`HID_QUIRK_NO_IGNORE`) removes the entry, but only from the
  kernel command line -- the module parameter is read-only at
  runtime -- and even then the quirk reclaims the interface at
  probe, so the entry alone does not open the road;
* writing to this channel without owning the interface is
  possible and is not therefore right. Two writers on one
  endpoint with no arbitration is how a card ends up in a state
  neither of them believes in.

## A note on capturing

The frames above were read from `hidraw` while M Control Center
drove the card from another host, and from a listener that
subscribes within milliseconds of the device appearing. Two
habits made the difference between a capture that decodes and one
that does not:

**Subscribe before asking**, because the first announce wave is
gone in under a second.

**Write down what the hand did, in order.** Three wrong
conclusions in a row came from reasoning over an assumed
procedure: a shell transcript is not a protocol, and a capture
without the operator's actions beside it is a list of numbers.
