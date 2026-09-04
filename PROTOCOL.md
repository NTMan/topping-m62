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

**The card reports itself in two waves after a subscribe.** The
first arrives about 0.9 s in and carries the jack state of every
input and output. The second follows about 4.3 s later -- roughly
5.2 s after the subscribe -- and repeats the jacks, adds the output
mutes, and adds **the gain of each input whose jack is present**
(**verified**, with every state restorer on the host disabled: a
gain set by hand to 50 on the front panel came back as
`0x21/04 = 50`, and twenty-two outgoing frames in the whole run,
all of them `11/24` or `11/26`).

An input with nothing plugged into it is not reported. Neither is
an output volume, even with headphones connected, and neither is a
selector.

**Everything a hand moves is reported as it moves** (**verified**):
turning the Mic-1 knob from 50 to 53 and back produced seventeen
`0x21/04` frames, one per step; turning the headphone volume
produced five `0x64/03` frames. Note that an output pair reports
only the target this document lists -- `0x64`, not `0x63`.

### What the card is actually telling you

The rule that fits every capture: **the card reports what a hand
does to the hardware, not what its settings are.**

Jack states, mutes, battery and the gain of a connected input are
physical facts it knows by itself, so they arrive unasked. An
output volume is a setting and is not in the connect report -- but
its knob is on the front panel, so turning it is an event and the
event is reported. A source selector has no front-panel control at
all, so no event can exist, and nothing about it ever arrives.

That is why the selectors are unreadable, and it is a stronger
statement than "no command was found": there is nothing to command.
A host that did not set the selector cannot learn it, and only a
query added to the firmware would change that.

**`11/26` is not a state request.** M Control Center sends it
**after** its bulk push, not before, and in a capture of MCC
connecting all 162 outgoing frames are writes with not one read.
In some captures it is followed by an inbound dump of the EQ
blocks (`0x91`..`0x94`, `0xa1`..`0xaa`, ten properties each),
ending with `11/25 = 1` sent three times: ~2.8 s after MCC's,
~3.6 s after this driver's. That dump never contains a gain, a
volume or a selector, and it does not appear every time.
**Guessed:** `11/26` asks for a DSP-block dump and `11/25`
terminates it. Whether the two-wave report above is a response to
it or simply periodic is untested -- the interval between the two
waves is the same 4.27 s in every capture, which argues for
periodic.

### How this was got wrong twice

Kept rather than erased, because the shape of the mistake is
instructive and the same trap is waiting for the next reader.

Until 4 September 2026 this document said the gains land about
five seconds after the announce, and for a few hours that morning
it said the opposite -- that nothing can be read at all. Both
readings came from captures with a blind spot.

The original ones were taken from `hidraw` **while M Control
Center drove the card from another host**, so it was not possible
to tell the card's own report from MCC's writes reaching a second
listener. The correction went too far because it rested on two
captures that each hid the report for a different reason: in four
of them the host's state restorers wrote to the card about 90 ms
after the bind, so the report at 5.2 s described their write; in
the one clean capture nothing was plugged into any input, and an
input with no jack is not reported.

**The lesson for anyone capturing this card: disable
`alsa-restore`, the `90-alsa-restore` udev rule and wireplumber,
and have something plugged into the input you are watching.**
Either omission produces a convincing false negative.

**Guessed, still worth half an hour:** whether the card broadcasts
one subscriber's writes to another. Run a `hidraw` listener
alongside the bound kernel driver, write a gain with `amixer`, and
see whether an inbound `0x21/04` appears.

### The connect sequence

MCC's, timed from its first frame (**decoded**):

```
0.000  OUT  11/01 = 1     session open; device answers 11/01 = 3
0.034  OUT  11/20 = 1     opens a bulk push
 ...        149 writes    gains, mixer, EQ, loopback, selectors
1.070  OUT  11/20 = 0     closes it
1.072  OUT  11/26 = 1
1.074  OUT  11/24 = 1     subscribe, then every ~1.9 s
```

`11/01` is a session handshake with a reply: host writes 1, the
device answers 3. `11/20` brackets a bulk push of exactly 149
frames taking 0.3 s. Both were **guessed** to be markers and are
now **decoded** as such. Whether the bracket is required is
untested -- the kernel driver writes without it and the writes
take effect.

All 162 of MCC's outgoing frames carry `0000` in the checksum
field, which is the same "MCC does not sign its writes" noted
under the frame format, now counted.

Once subscribed the card streams roughly 250 frames per second
across eighteen meter properties, about 14 Hz each, and the
interrupt IN endpoint is polled around 900 times a second.
Anything parsing this stream discards most of it.

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

### The selectors cannot be read, and that is permanent

This section was written about the source selectors, briefly
widened to everything on 4 September 2026, and narrowed back the
same day when the measurement was repeated properly. What holds is
the original claim, now with a reason behind it.

A source selector has no control on the front panel. Since the
card reports events rather than settings (see "What the card is
actually telling you"), there is no event it could report, and
nothing about a selector has ever arrived in any capture. A host
that did not write the selector cannot learn where the output is
pointing.

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

Read against what was measured afterwards, their answer about the
selector was not a refusal to disclose a command. There is no
command, and given how the card reports, there is nothing for a
command to be built on short of new firmware.

What it settles is the design. A program can write a selector and
can never learn it, so the honest shape is an extra first item
meaning "unknown, the device does not report this", refused as a
change and accepted as a no-op restore.

### What a program can and cannot know

                        at connect                  later
  five input gains      yes, if the jack is         at every turn
                        present, ~5.2 s in          of the knob
  two output volumes    no                          at every turn
  two selectors         no                          never

The two output volumes are knowable but not immediately: nothing
reports them until a hand moves the knob. A program that shows one
before then is showing a guess.

And the guess is dangerous in a specific way: the output taper
puts mute at index 0 and full scale at index 99, so a program that
defaults to zero tells the user the headphone output is silent
when it may be at maximum.

**Writing a "sensible default" at connect is the wrong answer for
the gains**, because the card is about to report them: a write at
90 ms destroys a value that would have arrived at 5.2 s. Anything
that wants the truth has to not publish, or not accept writes,
until the second wave lands.

### A device arriving from another host

Mic-1 was set to 70 by hand on the front panel from Linux and
confirmed through the control; the Mac had 50 stored from an
earlier session. Forty milliseconds after connecting to the Mac,
MCC wrote `0x21/04 = 50` and the panel followed. That write is the
only mention of `0x21/04` anywhere in the capture.

So a setting made by hand does not survive being plugged into
another host that has its own stored state -- not because the card
forgets, but because the host imposes. On Linux the same is done
by `alsactl`, the `90-alsa-restore` udev rule and wireplumber,
each independently, within about 90 ms of the card appearing.

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

`11/01` session handshake (host 1, device answers 3), `11/05`
save to the card's own memory (see the two memories above),
`11/18` battery percent, `11/19` a periodic blink flag that is
not ours, `11/20` bulk-push bracket, `11/24` subscribe /
keepalive, `11/25` end of the `11/26` dump, sent three times,
`11/26` a DSP-block dump request and NOT a state request.
Device flags `11/04`, `11/1a`, `11/1b`, `11/1c`, `11/1e` appear
in an announce and are undecoded.

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

Exactly two things, and one class of thing.

**The two source selectors**, for the reason given above: no
front-panel control, so no event, so nothing to report. Permanent
short of new firmware.

**An output volume before anyone has touched it.** It is not in
the connect report and only a hand on the knob produces one. A
program that shows a number before that is showing a guess, and
the guess is dangerous in a particular direction: the taper puts
mute at index 0 and full scale at index 99, so defaulting to zero
tells the user the headphone output is silent when it may be at
maximum.

**The gain of an input with nothing plugged into it.** Reported
only when the jack is present.

Everything else the card volunteers: jacks, mutes, battery,
identity, meters, the gain of a connected input, and any change a
hand makes on the panel.

### Why this looks worse than it is on Linux

At least three mechanisms write stored state back on every plug,
each within about 90 ms of the card appearing:
`alsa-restore.service` -- whose `ExecStop` is `alsactl store`, so
stopping it rewrites the file you were about to move aside -- the
`90-alsa-restore` udev rule on card add, and wireplumber's own
device state.

The card's own report of the input gains arrives at about 5.2 s.
So on an ordinary system the restorers win by a factor of fifty,
and what the card reports at 5.2 s is the restorer's write coming
back rather than the position the panel had. Nothing is wrong with
either party; they are simply racing, and the host always wins.

**Anything that wants the truth has to not enter that race** --
not publish its controls, or not accept writes to them, until the
second wave has landed. Writing a "sensible default" at connect,
as MCC does and as `init_cur_mix_raw()` does for devices with a
broken `GET_CUR`, is the wrong answer here: it destroys a value
that was about to arrive.

The selectors remain outside all of this. Nothing will ever
report them, so the honest shape stays an extra first item meaning
"unknown, the device does not report this".

## Still unknown

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

It may not be permanent. A second road is being tried at the
maintainer's suggestion: a HID driver bound normally, joined to
snd-usb-audio through the component framework
(`include/linux/component.h`). On that road the `hid_ignore_list`
entry has to go and a `hidraw` node can coexist with the driver.
Nothing is settled. The two-writers caution below applies more on
that road, not less.

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
