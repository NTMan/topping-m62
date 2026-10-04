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
can never learn it, so a program that takes charge of the card has
to decide the selector rather than ask about it. Since v8 the driver
does exactly that: it writes both selectors when it first binds --
Playback 1/2, the host's main stream, with the mixer out of the path
-- and from then on its own cache is the truth, which the restorers
then overwrite with whatever the system remembers.

An earlier design showed an extra first item instead, meaning
"unknown, the device does not report this". It was honest about the
card and wrong about the system: a sound settings panel always shows
something selected, and what it shows has to be true. The vendor's
application takes the same view from the other side, writing its
whole workspace to the card at connect without reading anything
back.

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

For the other two rows nothing will arrive, so there the default is
the right answer, and since v8 the driver gives it: at its first
bind it writes both selectors and both output volumes, which makes
what it shows what the card holds.

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

Targets `0x51`..`0x58`, a pair per loopback: Loopback 1/2 is
`0x51`/`0x52`, 3/4 is `0x53`/`0x54`, 5/6 is `0x55`/`0x56`, 7/8 is
`0x57`/`0x58`.

| Property | Meaning |
| --- | --- |
| `02` | source select, numbered as in "The source selector's values" |
| `03` | gain, Q25, 0 dB = 2^25 |

**The source is written to the FIRST target of the pair only** --
`0x51/02`, `0x53/02`, `0x55/02`, `0x57/02`. The outputs are the
other way round: their selector goes to the second target.

The gain is written to both targets, in whole decibels from +12 dB
down to -89 dB, and 0 for off. M Control Center's fader shows +12 at
its top.

The source menu offers the output selector's fourteen items, grouped
as Mixer (Mix A, B, C), Input (IN 1, IN 2, IN 1+2, AUX, BT, OTG IN)
and Playback (Playback 1/2 to 9/10). On a loopback only 6, 7 and 9
to 13 have been seen written; the other values are taken from the
outputs' numbering.

M Control Center's connect push writes 12, 13, 10 and 11 to `0x51/02`,
`0x53/02`, `0x55/02` and `0x57/02` -- the first target again -- and
0 dB to all eight `03`s.

The card reports neither property: no frame from the card carries
a target in `0x51`..`0x58`.

Decoded from two captures on macOS, 5 October 2026.
`M62-loopbacks.pcapng` starts with M Control Center already
connected, so it holds no connect push; in it each loopback's source
was changed once and back -- 6 IN 1, 7 IN 2, 9 AUX and 10 BT out,
12, 13, 10 and 11 back -- and each fader was taken to the bottom and
back. `M62-loopbacks-2.pcapng` starts with the connect push, then
Loopback 1/2's fader goes to the top and back. The menu's items and
the +12 are read off the program's screen.

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
maximum. The driver turns the guess into a fact by writing it: at
its first bind the analogue headphone stage goes to its quiet end,
as `init_cur_mix_raw()` in snd-usb-audio does for a volume whose
`GET_CUR` fails, and the digital stream to a phone to unity, where
it changes nothing.

**The gain of an input with nothing plugged into it.** Reported
only when the jack is present.

Everything else the card volunteers: jacks, mutes, battery,
identity, meters, the gain of a connected input, and any change a
hand makes on the panel.

### Why this looks worse than it is on Linux

Stored state is written back on every plug, within about 90 ms of
the card appearing, by `alsactl` and by wireplumber's own device
state. On the machine these notes come from, `alsactl` runs as the
daemon of `alsa-state.service` (`alsactl ... rdaemon`): it restores
when a card appears and, while it runs, saves what changed every
300 s. `alsa-restore.service`, the variant whose `ExecStop` is
`alsactl store`, is inactive there. Either way the file is
rewritten behind your back, so a copy moved aside to experiment
with is overwritten within minutes.

The card's own report of the input gains arrives at about 5.2 s.
So on an ordinary system the restorers win by a factor of fifty,
and what the card reports at 5.2 s is the restorer's write coming
back rather than the position the panel had. Nothing is wrong with
either party; they are simply racing, and the host always wins.

**Anything that wants the truth about the gains has to not enter
that race** -- not publish its controls, or not accept writes to
them, until the second wave has landed. Writing a "sensible
default" for them at connect, as MCC does, destroys a value that
was about to arrive.

For everything the card does not report, the race is the point: the
host owns those values, the driver writes its defaults at its first
bind, and the restorers then write what the system remembers on top.
The selectors are the plainest case -- nothing will ever report
them, so the last host to write one is right by definition.

## Still unknown

* input property `0a`;
* device flags `11/04`, `11/1a`, `11/1b`, `11/1c`, `11/1e`;
* the EQ blocks;
* noise reduction and reverb, which were never captured. Both
  must be OFF for any measurement, alongside AUTO gain and EQ.

The AUTO button sends nothing at all: the auto-gain is entirely
in firmware.

## Where the boundary with the kernel runs

The kernel series for this card -- v8 at the time of writing --
makes these ordinary ALSA controls on the card snd-usb-audio
creates, and a userspace program should therefore leave them alone:

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

Two roads were tried, and they differ in exactly the thing a
userspace program cares about.

**The mixer-quirk road**, posted in August 2026, claimed the HID
interface for snd-usb-audio and added the card to
`hid_ignore_list`, which meant **no `hidraw` node**: on a kernel
carrying it this protocol was not reachable from userspace at all.
It was dropped.

**The component road**, posted since 4 September 2026 at the
maintainer's suggestion, splits the work in two: a HID driver bound
the ordinary way (`drivers/hid/hid-topping.c`) and the M62's
mixer quirk in snd-usb-audio (`sound/usb/mixer_topping.c`), joined
through the component framework (`include/linux/component.h`) with
the quirk as the master. The `hid_ignore_list` entry is gone and
**a `hidraw` node coexists with the driver**, so this protocol stays
reachable. Since v8 the controls themselves are snd-usb-audio's and
the HID driver is the transport: at bind it fills in the
`struct topping_component` the master owns
(`include/sound/topping.h`) with an operation that sends a
frame, and it passes on every valid frame the card reports.

That road has been built and run rather than merely proposed:

* the controls appear 54 to 57 ms after the HID probe, and because
  the master is added from inside `snd_usb_create_mixer()` the
  bind is synchronous and they exist before the card is
  registered;
* two M62s on one host bind to their own cards, the match being by
  descent from the shared USB device;
* nothing is claimed, so unbinding the audio interface stops the
  keepalive, which under the quirk road it did not.

The two-writers caution below applies more on the component road,
not less: there the driver and a `hidraw` program really can reach
the same endpoint at the same time, with nothing arbitrating
between them.

### Why the controls outlive the HID driver (**verified**)

Up to v7 the controls were created when the HID driver bound and
removed when it unbound, so reloading that module took them off a
card that stayed registered throughout and put them back with
fresh numids -- the kernel only ever counts numids up. Each of the
following was seen on 3 October 2026:

* the desktop's volume showed zero after a reload while the card
  went on playing at its own level: WirePlumber enumerates a
  device's elements once and does not follow them being removed
  and added again;
* a volume the card was still holding read as zero: the driver's
  cache came back empty, and nothing reports an output volume
  until its knob turns;
* the stored `alsactl` state stopped matching: `alsactl` looks a
  control up by its numid, treats a different one as a mismatch
  and falls back to its generic init, which writes -20 dB into any
  control named `Headphone Playback Volume` -- here the analogue
  headphone stage. The state daemon then saved the new numids
  within five minutes, numids that would not exist after the next
  boot.

Since v8 the controls are created once, at the first bind, and stay
until the card goes. Unbinding the HID driver keeps them; a value
written meanwhile goes to the cache; the next bind writes every
known value back to the card. They are not marked inactive either:
a first cut of v8 did that, and the desktop volume dropped to zero
exactly as before, because alsa-lib's simple mixer handles an
`SNDRV_CTL_EVENT_MASK_INFO` by removing the element and adding it
again (`simple_event()` in `src/mixer/simple_none.c`).

Verified the same day, with PipeWire running: across four reloads
of the HID driver, then still named `hid-topping-m62`, the controls
kept numids 11 to 19,
`amixer -c M62 contents` was identical before and after, and
`wpctl get-volume @DEFAULT_AUDIO_SINK@` read 0.25 before and after.
`Headphone Playback Volume` set to 30 while the module was unloaded
read 30 after it was loaded again, and one step of the front-panel
knob then brought the card's own report of 31 -- the card had been
set to 30 by the new bind. The runs were repeated after the rename
to `hid-topping`, with a second M62 connected, and gave the same
results; that time the volume was set to 20 before the unload, so
the knob step also showed that the 30 had reached the card.


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

## The same channel on the E2x2 OTG

The TOPPING Professional E2x2 OTG, `152a:8756`, is driven by a
different program, TOPPING Professional Control Center, and speaks
the same channel: the same interface layout, the same transport and
the same frame. The connect sequence and the whole address map are
its own.

Everything in this section comes from captures made with Wireshark
on macOS (`XHC1`, `LINKTYPE_USB_DARWIN`) of Control Center driving
a card that reports hardware V1.01 and firmware V1.10: four on
2 October 2026 (UTC) with Control Center V1.09, a fifth on
3 October and three on 4 October. Writing to the card from Linux
began on 4 October, with `tools/e2x2.py`; what those writes showed
is marked **verified** (see Writing from Linux below), and as in
the rest of this document anything unmarked is **decoded**.

### The captures

* `E2x2-1.pcapng`, 109.6 s, started in the middle of a session.
  The gain knobs of IN 1, IN 2 and the Mobile strip were turned
  +0 -> +20 -> +10 -> +0, in that order; then IN 1's MON, 48V,
  INST, SOLO, MUTE and ø (phase) were pressed once each, in that
  order.
* `E2x2-2.pcapng`, 300.8 s. The Output 1+2 fader taken to -inf
  (it writes `0x31`/`0x32`); 48V on IN 1 switched off; the card
  switched off and on, Control Center reconnecting 42 s later;
  then, on IN 1, MUTE off, ø off, ø on; the Output 1+2 selector
  walked through its whole menu in menu order and back to
  Playback 1/2; the Mobile OUT and S/PDIF OUT selectors each set to
  Mix A and back, which sent nothing (see the end of this
  section); MON on IN 1 pressed twice on the front panel; Gain
  under Phone Out switched and switched back.
* `E2x2-3.pcapng`, 74.4 s. Mobile OUT set to Mix A and S/PDIF OUT
  to Mix B; then the card switched off and on, Control Center
  reconnecting 0.45 s later.
* `E2x2-4.pcapng`, 29.1 s, with music playing through the card.
  The headphone, TRS and AUX buttons of the Output 1+2 strip
  switched off in that order, then on in the same order.
* `E2x2-5.pcapng`, 179.0 s. Control Center connected 1.0 s in and
  pushed its state; then the faders of Mobile OUT, S/PDIF OUT,
  Loopback 1+2, Loopback 3+4 and Loopback 5+6 were each taken down
  to about -20 dB and back to 0 dB, one at a time and in that
  order.
* `E2x2-6_1.pcapng`, 115.3 s, with Control Center already connected.
  Music played from the Mac while the Output 1+2 fader and then
  the S/PDIF OUT fader were each taken to about -20 dB and back. A
  phone on the OTG port played a 440 Hz tone on its right channel
  from the start, moved to its left channel 79 s in; with the tone
  on the left, the Mobile gain was turned +0 -> +10 -> +0 dB.
* `E2x2-7.pcapng`, 124.3 s. The phone played the tone on its right
  channel; the Mobile gain was turned +0 -> +10 dB; Control Center
  was quit and started again with the gain left at +10 dB,
  reconnecting 45.7 s in; the gain was turned back to +0; then
  music played from the Mac, and the monitor mix knob on the front
  panel was turned away from its leftmost position three times,
  back to it after the first two.
* `E2x2-8.pcapng`, 115.3 s, with Control Center connected and the
  phone on the OTG port. The monitor mix knob was turned to its
  rightmost position and back to its leftmost; the phone was pulled
  out of the OTG port; Control Center was quit and started again,
  reconnecting 73.5 s in; the phone was plugged back in; the knob
  was touched once more.

Across the eight, all 2240 frames the program wrote carry `0000`
in the checksum field, and all 50920 non-empty frames the card sent
carry a valid CRC-16/MODBUS: the frame and the direction
discriminator described above apply unchanged. An idle poll
returns sixteen zeros, as on the M62.

### The USB side

From the enumeration in `E2x2-2.pcapng`:

| Interface | Class | What it is |
| --- | --- | --- |
| 0 | `01/01/20` | AudioControl, UAC2 |
| 1 | `01/02/20` | AudioStreaming, playback: 8 channels, 24 bits in 4-byte subslots, alternate settings 1 and 2 |
| 2 | `01/02/20` | AudioStreaming, capture: 10 channels, 24 bits in 4-byte subslots |
| 3 | `fe/01/01` | "Topping DFU" -- **never write to it**, as on the M62 |
| 4 | `03/00/00` | HID: interrupt IN `0x83`, OUT `0x02`, `wMaxPacketSize` 64, `bInterval` 5 |

The report descriptor is 27 bytes and matches the M62's, as
described under Transport, in every field:

```
05 01 09 00 a1 01 15 00 25 ff 19 01 29 08 95 10
75 08 81 02 19 01 29 08 91 02 c0
```

`bcdDevice` is `0x0110`, the same V1.10 that the program shows as
the firmware version and that `12/02` reports. There are two
configurations, byte-identical.

Every terminal and both streaming interfaces declare
`bmChannelConfig` 0, and the channels are named through
`iChannelNames`, 11 for playback and 19 for capture:

```
11 Playback 1/SPDIF 1      19 Analogue 1
12 Playback 2/SPDIF 2      20 Analogue 2
13..18 Playback 3..8       21 Mobile 1
                           22 Mobile 2
                           23..28 Loopback 1..6
```

The clock is "Topping Internal Clock" (clock source 41 behind
clock selector 40). Feature units 10 (playback) and 11 (capture)
offer mute and volume on the master and on every channel.

### The connect sequence

**There is no subscription and no keepalive.** After the power-on
in `E2x2-2.pcapng` the card sent its first frame 24 ms after
`SET_CONFIGURATION`, 42 s before the program wrote anything, and
no `11/24` appears in any of the three captures.

Unasked, after power-on, the card:

* sends every meter at -96.0 (`-960`), each every 68 ms, for about
  7.5 s; after that a meter is sent only while its level is above
  -96.0;
* announces `21/03` and `23/03` (INST on IN 1 and IN 2), `11/03`
  and `35/03` (the monitor mix knob).

INST survives a power cycle: in both reconnects the card announced
IN 1's INST as it was last set, before the program had written
anything. It is the card saving its state by itself; see The card
keeps its own state.

Control Center's push after the reconnect in `E2x2-2.pcapng`,
timed from its first frame:

```
0.000  OUT  11/01 = 1     card answers 11/01 = 1, then sends
                          12/01, 12/02, 11/02, 11/04, 11/06
0.004  OUT  37/01..37/06 = 1
 ...        132 more      selectors, faders, matrix, input
                          switches, input gains
0.284  OUT  24/05         the last write
```

No `11/20` bracket, no `11/26`, no `11/24`. In `E2x2-3.pcapng` the
same push came 0.45 s after the card appeared, **without `11/01`**
-- the other 138 frames identical and in the same order -- and the
card sent none of `12/01`, `12/02`, `11/02`, `11/04`, `11/06`.
**Guessed:** `11/01` asks for identification rather than opening a
session. Whether the card takes writes from a host that never sent
it is untested.

### The address map

Blocked by function, but not as on the M62, where `0x3x` is the
matrix and `0x6x` the outputs:

| Block | Meaning |
| --- | --- |
| `0x11` | the device itself |
| `0x12` | identification |
| `0x2x` | inputs |
| `0x3x` | Output 1+2 and Mobile OUT |
| `0x4x` | meters only, `0x41`..`0x48` property `01`: the eight playback channels, `0x43`..`0x48` **guessed** (see Output meters) |
| `0x5x` | loopbacks and S/PDIF OUT |
| `0x6x` | mixer matrix |

#### Inputs

Targets: `0x21` IN 1, `0x23` IN 2, and the two channels of the
Mobile input, `0x22` left and `0x24` right; the program has one
strip for the Mobile input, at `0x22`. In `E2x2-6_1.pcapng` a tone
on the phone's right channel lit `24/04` alone, at -43.2 dB, and
moved to the left channel it lit `22/04` alone, at the same level.

This is not the M62's order, so the evidence. In `E2x2-1.pcapng`
the knobs were turned in the order IN 1, IN 2, Mobile and wrote
`0x21`, `0x23`, `0x22`; at +16 to +20 dB `0x21` and `0x23`
reported noise between -90.3 and -80.7 dB, while `0x22` sent no
level at all. After the power-on in `E2x2-2.pcapng` only `0x21`
and `0x23` showed a transient, and only they had INST announced.
`0x24` is written like the others in the push and by SOLO and
MUTE, and before `E2x2-6_1.pcapng` its level stayed silent.

| Property | Meaning |
| --- | --- |
| `01` | MON (1 = on) |
| `02` | 48V (1 = on) |
| `03` | INST (1 = on) |
| `04` | level meter, tenths of a decibel |
| `05` | digital gain, **signed** Q25 |

`01`, `02` and `03` are confirmed by the card 26 to 200 ms after a
write, and a MON press on the front panel arrives by itself: pressed
twice, it came as `21/01 = 0`, then `21/01 = 1`, with nothing
written. Only a write that changes the value is confirmed: a write
of the current value gets no answer, though the card still acts on
it (see Writing from Linux). Confirmations and panel presses usually
arrive twice, a few milliseconds apart (**verified**).

`05` is never reported. Control Center offers +0 to +20 dB in
1 dB steps (+1 dB = 37648680, +20 dB = 335544320). The published
specification gives 58 dB of analogue gain on the front-panel
knob plus 20 dB of digital gain: the 20 dB is this property, and
the analogue part has none.

The Mobile strip's gain is `22/05` alone, and it acts on both
channels. In `E2x2-7.pcapng`, with the tone on the right channel,
raising `22/05` from +0 to +10 dB raised `24/04` by 10.0 dB, from
-43.2 to -33.2 dB; the push that followed wrote `22/05` = +10 dB and
`24/05` = +0 dB, and the right channel stayed at -33.2 dB. Nor does
`24/05` act on it: written from Linux as +10 dB, with a tone on the
right channel at -31.1 dB, `24/05` left `24/04` where it was, and so
did writing it back to +0 dB (**verified**, 4 October).

SOLO, MUTE and ø have no properties of their own; the program
folds all three into `05`:

* MUTE writes 0;
* ø negates the value: with ø lit, switching MUTE off wrote
  `21/05 = -2^25`, ø off wrote `+2^25`, ø on again `-2^25`;
* SOLO writes 0 to the other three inputs, `0x24` included. MUTE
  pressed while soloed wrote 0 to IN 1 and the others back to
  their gains.

#### Outputs and selectors

| Target | Property | Meaning |
| --- | --- | --- |
| `0x35` | `01` | Output 1+2 source |
| `0x35` | `02` | Gain under Phone Out, the headphone amplifier's gain switch (1 = on); confirmed by the card |
| `0x35` | `03` | the front-panel monitor mix knob, 0..100, reported by the card |
| `0x36` | `01` | Mobile OUT source |
| `0x36` | `02` | written 0 in the push; meaning unknown |
| `0x5c` | `01` | S/PDIF OUT source |
| `0x57`, `0x58`, `0x59` | `01` | Loopback 1+2, 3+4, 5+6 source |
| `0x37` | `01`, `03`, `05` | Output 1+2's headphone, TRS and AUX outputs (1 = on) |
| `0x37` | `02`, `04`, `06` | written 1 in the push; meaning unknown |

A press on any of the three output buttons writes all three --
`37/01`, `37/03`, `37/05`, the whole current state -- and then the
Output 1+2 fader pair `31/03`, `32/03` at its current value.
Decoded from `E2x2-4.pcapng`, where each of the six presses
changed exactly one of the three, in the stated order. The card
confirms none of it, and with music playing no meter reacted to an
output being switched off.

**No selector is ever reported**, and neither is an input gain:
nothing on these selector properties or on `0x21`..`0x24/05` came
from the card in any of the eight captures.

Faders are Q25 on property `03` of the pairs `0x31`/`0x32`,
`0x33`/`0x34` and `0x5a`/`0x5b` and of `0x51`..`0x56`; 0 is -inf.
`0x31`/`0x32` is Output 1+2: it is the fader taken to -inf at the
start of `E2x2-2.pcapng`, and on the way down it wrote whole
decibels from -1 dB to about -80 dB, then a few values a fraction
of a decibel off, then 0. The others were moved one at a time in
`E2x2-5.pcapng`, in a stated order: `0x33`/`0x34` is Mobile OUT,
`0x5a`/`0x5b` S/PDIF OUT, and `0x51`/`0x52`, `0x53`/`0x54` and
`0x55`/`0x56` Loopback 1+2, 3+4 and 5+6. A fader writes the same
value to both targets of its pair, in whole decibels, and the card
confirms none of it. By the published
specification the headphone and line volumes are analogue
potentiometers on the front panel, and no property for them
appears in any capture.

#### Output meters

All meters, the inputs' `04` included, read like the peak of a
16-bit sample in tenths of a decibel, cut toward zero rather than
rounded: the low levels seen are -90.3, -84.2, -80.7, -78.2, -76.3,
-74.7, -73.4, -72.2, that is 20 log10(n/32768) for n = 1 to 8, and
-96.0 stands for nothing at all. A meter cannot show a level between
-96.0 and -90.3.

Output 1+2, Mobile OUT and the three loopbacks report two level
meters each, properties `01` and `02`, in tenths of a decibel like
the inputs' `04`; S/PDIF OUT reports only `02`. The meters of
Output 1+2 and S/PDIF OUT do not move with their faders: in
`E2x2-6_1.pcapng` both faders went to -20 dB with music playing and
the meters unchanged.

On Output 1+2, `02` is the selected source and `01` the output of
the monitor mix, both before the fader. With MON on IN 1 and the
monitor mix knob at its leftmost position, `01` carried the
microphone on IN 1 and `02` the music (`E2x2-6_1.pcapng`); with the
knob at 15, `01` carried the music about 16 dB below `02`
(`E2x2-7.pcapng`); with MON off, both carried the music
(`E2x2-4.pcapng`). On Mobile OUT and the loopbacks both followed the
source in every capture. Written from Linux, each source value of
`35/01` put exactly its source on `02` (**verified**; see The source
selector's values).

Mobile OUT reports its right channel's `01` under the left target:
`33/01` arrives twice per cycle, the second 2 ms after the first,
and `34/01` never. In `E2x2-4.pcapng` the first of the two follows
Output 1+2's left meter and the second its right one: of 427
pairs, 187 equal `31/01` and `32/01` exactly, against 5 crossed.

`0x41`..`0x48` property `01` are the playback channels: in
`E2x2-4.pcapng` the music lit `0x41` and `0x42` and none of the
other six. That `0x43`..`0x48` are Playback 3..8 in order is
**guessed**.

#### The source selector's values

```
 1 IN 1           7 Playback 1/2    11 Mix A
 2 Mobile IN      8 Playback 3/4    12 Mix B
 3 IN 2           9 Playback 5/6    13 Mix C
 5 IN 1+2        10 Playback 7/8    14 Mix D
```

4 and 6 are not offered by the program. The input values follow the
input targets -- `0x21` is 1, `0x22` is 2, `0x23` is 3 -- but the
pattern stops there: 4 is not `0x24`.

Written from Linux to `35/01`, with Output 1+2's `02` showing the
selected source (**verified**, 4 October): 1 puts IN 1 on both
sides, 2 the Mobile input as it comes, 3 IN 2 on both sides, and 5
IN 1 on the left and IN 2 on the right. 4 and 6 both put IN 1 and IN
2 together on both sides, each at about the level it has alone: with
IN 2 at +0 dB they showed IN 1's noise on both sides, and with IN 1
muted and IN 2 raised by 20 dB they showed IN 2's on both sides.
Neither carried a tone on the Mobile input's right channel that 2
showed at -0.1 dB. What tells 4 from 6 apart was not found.

Written to Loopback 1+2's source, `57/01`, the same values put the
same sources on the loopback's meters `51/02` and `52/02`: 1 IN 1 on
both, 2 the Mobile input with a tone on its right channel on `52/02`
only, and 8 Playback 3/4, with nothing playing there, silence on
both (**verified**, 4 October).

Decoded from the Output 1+2 menu walked in a stated order in
`E2x2-2.pcapng`. The push after the reconnect agrees with the
screen (the loopbacks at 8, 9, 10, that is Playback 3/4, 5/6,
7/8), and in `E2x2-3.pcapng` Mix A and Mix B came out as 11 and 12
on `0x36` and `0x5c`. One numbering serves all six selectors, and
no item in it has the value it has on the M62.

#### The mixer matrix

Targets `0x61`..`0x68`, properties `01`..`0c`, Q25: the M62's
model with four mixes and twelve sources. **Guessed** from the
default values in the push: `0x61`/`0x62` are Mix A left and
right, and so on to `0x67`/`0x68` for Mix D; the sources are `01`
IN 1, `02` IN 2, `03`/`04` Mobile, `05`..`0c` Playback 1..8. The
two mono sources sit at -6.02 dB on both sides (`0x00fffff0`);
each stereo source is at unity on its own side and at zero on the
other. For unity the program writes `0x01ffffe0` here rather than
`2^25`.

#### The monitor mix knob

`35/03` is the monitor mix knob on the front panel, which sets how
much of the inputs and of the playback reaches the headphones. The
card reports it whenever it is turned, with nothing written, as an
integer from 0 at the leftmost position to 100 at the rightmost
(`E2x2-8.pcapng`). At 0 the inputs reach the headphones: Mikhail
heard only them there, and Output 1+2's `01` carried the microphone
on IN 1. At 100 they do not: with the microphone at up to -57.6 dB
and nothing playing, `01` stayed at -96. The card also announces the
knob after power-on and after `11/01`; the program never writes it.

Control Center's connect silences the monitor mix until the knob is
turned. After the push, Output 1+2's `01` drops to -96 and stays
there -- no microphone, and no music once the music plays -- until
the knob moves: in `E2x2-7.pcapng` from the push at 45.7 s until the
knob moved at 102.6 s, which Mikhail also heard; in `E2x2-5.pcapng`
from its push at 1.0 s to the end of the capture; and in
`E2x2-8.pcapng` from its push at 73.5 s until the knob moved at
102.9 s, with the microphone on IN 1 at up to -53 dB throughout. The
write that does it is `23/01 = 0`, MON off on IN 2 (see Writing from
Linux).

#### After power-on

After every power-on the card mixes as though monitoring were on,
whatever its MON buttons show. The monitor mix knob stays in the
playback path: at its rightmost position playback passes in full, at
its leftmost none of it does. It stays so until MON on IN 1 and on
IN 2 have each been switched off since the power-on -- from the
panel or by a write, one at a time or together, in either order.
Found by Mikhail by hand on 4 October, on Linux and on the Mac; on
the Mac the knob keeps acting on playback until Control Center
connects, and stops as soon as it does, because its push writes MON
on both.

Written from Linux (**verified**, 4 October): after a power-on, with
the knob at its leftmost position, both MON off and music playing,
Output 1+2's `01` showed nothing; `21/01 = 0` and `23/01 = 0` --
both already off, so the card confirmed neither -- brought the music
to -22 dB within a second.

So a host that wants the card to play the same after every power-on
writes MON on both inputs at every connect, as Control Center does.
Writing MON off on IN 2 while IN 1 still monitors has the side
effect described under Writing from Linux, and a MON on written
afterwards undoes it.

#### Writing from Linux

All of it **verified** on 4 October with `tools/e2x2.py`, the card
on Linux and powered only from USB, MON on IN 1 and the monitor mix
knob at or near its leftmost position. With nothing plugged into
IN 1, its own noise through MON gave Output 1+2's `01` -72 to
-81 dB, enough to see the monitor mix work or stop.

The card takes writes in Control Center's own format, checksum
`0000`, and needs no `11/01` first: after the cable was moved from
the Mac, `21/01 = 0` and `21/01 = 1` were each confirmed about 100
ms later, and `01` went to -96 and came back. Signed with a valid
checksum they are taken the same way -- `21/01 = 0` and `21/01 = 1`
confirmed within 107 ms -- so, as on the M62, the card does not
check what it is sent, and the driver's signed frames need nothing
different.

Replaying Control Center's push in seven groups -- `11/01`, the
output jacks, `35/02` and `36/02`, the sources, the faders, the
matrix, the inputs -- left the monitor mix alone until the inputs;
split further, the inputs' group silenced it through one write,
`23/01 = 0`. That write silences the monitor mix whether or not it
changes anything: IN 2's MON already off, or switched from on to
off, `01` went to -96 within a second, every one of eight times.
Pressed on the front panel, the same MON off on IN 2 does not:
twice, with `01` unchanged. MON off on the Mobile input, written as
`22/01 = 0` or `24/01 = 0` with its MON already off, does not
either.

What brings the monitor mix back is turning the knob, or a MON on
written from the host, changed or not: so far `21/01 = 1` with IN
1's MON already on, and `23/01 = 1` switching IN 2's on. Writing the
knob does not: `35/03 = 0`, `= 1` and `= 0` again left `01` at -96,
and the card answered none of them.

#### The card keeps its own state

The card saves a change by itself once about five seconds have
passed without another one, whether the change was written from the
host or made on the front panel; switched off sooner, it comes back
in the state it had saved before. Mikhail found this by hand on 4
October with MON on IN 1 and IN 2, both ways, on Linux and with
nothing else talking to the card. What Download to Device adds to
this has not been captured.

On Linux, a listener that opens the card's node as soon as it
appears after power-on gets the meters from the first second, but
none of what the card announces after power-on on the Mac: no INST,
no monitor mix knob, no `11/03`, in 15 s (**verified**, 4 October).
Whether the card says it before the node is open, or not at all
here, is not known.

#### Device scope and identification

`11/06` is the OTG port: 1 with a phone connected, 0 without. The
card announces it whenever it changes -- in `E2x2-8.pcapng`, 0 when
the phone was pulled out and 1 when it was plugged back in -- and
after `11/01`.

`11/02 = 1` and `11/04 = 1` follow `11/01`; `11/03 = 0` is announced
after power-on and repeated after the push. None of the three is
decoded. No `11/05`, `11/20`, `11/24`, `11/25` or `11/26` was ever
written.

Identification lives at `0x12` as two 16-bit halves rather than
the M62's five bytes: `12/01 = 0x00010001`, hardware V1.01;
`12/02 = 0x0001000a`, firmware V1.10.

### Still unknown on the E2x2

* `0x36/02`, and `37/02`, `37/04`, `37/06`;
* `11/02`, `11/03`, `11/04`;
* what tells selector values 4 and 6 apart;
* whether MON off on IN 1, written from the host, also silences
  what IN 2 or the Mobile input still monitor;
* what `01` and `02` measure on Mobile OUT and the loopbacks, and
  why S/PDIF OUT has no `01`.

### A capture with no frame proves nothing

In `E2x2-2.pcapng` the Mobile OUT and S/PDIF OUT selectors were
each set to Mix A and back, and the program sent nothing at all:
in that window the interrupt polling has no gap longer than 5 ms,
and the card's own frames are present. In `E2x2-3.pcapng` the same
kind of change went out at once, to `0x36` and `0x5c`. What
differed between the two sessions is not known. A capture with no
frame for an action does not show that the action has no address;
repeat it before concluding anything.
