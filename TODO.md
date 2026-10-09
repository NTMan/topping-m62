# Pending work

Everything agreed on and not yet done, kept here rather than in
anyone's memory. An item leaves the list when it is done.

## The next posting of the series

Sent after review of v8, or about two weeks after v8 if no review
comes, in which case it doubles as the ping.

The four patches are written, on `topping-next` over e767a4ea7: the
controls renamed -- `Mic1` and `Mic2` without the hyphen, `SPDIF` for
the E2x2 OTG's `S/PDIF Out` -- and the M62's loopbacks, a source and a
gain for each of the four. The selectors keep `... Source`. Named
`... Route`, a selector joins the volume of the same name in alsa-lib's
simple mixer (`src/mixer/simple_none.c`), which then reads and writes
only the selector: on 5 October that took the M62's headphone volume
away from the desktop. The M62's loopback source and gain were checked
through the controls on 5 October, recorded on the loopback columns.

The runs were done on 5 October on both cards, on the four patches:
KASAN, lockdep and UBSAN on; fifty HID reloads, five
audio-side rebinds per card, `alsactl restore`, suspend and resume,
two cable pulls per card under playback and writes, and the M62's
Loopback 1/2 recorded through the controls; nothing in the kernel log.
Under PipeWire the M62's headphone level follows the desktop and the
knob both ways, and the desktop moves the E2x2 OTG's `Master` (the
card shows no level of its own).

A fifth patch offers the M62's battery level as a power supply of
device scope, registered once the card has reported a level: UPower
decides on first sight whether a device supply is a battery, and never
looks again at one whose capacity it could not read. In Mobile Mode
the card announces nothing to a plain subscription, so the driver
opens a session at bind and at resume as M Control Center does, with
0x11/0x01 before 0x11/0x24 and 0x11/0x26. Checked on 5 October: the
supply, and UPower's device with it, appear about 2 seconds after a
card is plugged in, in either mode.

A sixth patch offers the power settings of the M62's two USB ports as
enumerated controls, `USB-C Port Power` (Charge, Discharge, Off) and
`OTG Port Power` (Discharge, Off): without it a card set elsewhere not
to charge runs its battery down, with nothing on Linux to set it back.
The controls take the card's values from its announce and write only
when changed, as M Control Center does; a setting the card leaves out
of an announce keeps the control's last value. As ALSA controls they
are restored by `alsactl` when a card appears, from a state saved up
to five minutes late, so a switch that takes the card off the bus
would be undone; that has been seen only under macOS, not on Linux
(behind a hub, in a desktop's USB-C port, or in a Mac's own port under
Asahi Linux). Checked on 6 October: written through the controls the
settings reach the card, the controls follow the card's announce, and
change events reach alsamixer.

A seventh patch gives the M62's Mobile Mode its own controls, found on
9 October: in that mode the card's capture is one mix of its inputs and
part of the address map means something else, and the six patches
wrote Pro Audio Mode's values into it -- the first bind's Q25 for
Loopback 1/2 raised the recording by 9 dB. The rows that only one mode
has are tagged, and the mode is taken from bcdDevice. Mobile Mode keeps
the gains, the two output volumes and the port power settings, and
gets `PCM Playback Volume` (the Playback 1/2 knob, the playback's level
in the headphones) and `Recording Capture Volume` (the Recording
fader), both written at 0 dB at the first bind.

An eighth patch, asked for on 10 October, adds the MUTE beside each
level as a switch of the same name: the inputs' at property 05, the
outputs' at 04, and in Mobile Mode the knob's and the fader's at 04.
All are written with the sound on at the first bind, as M Control
Center does at every connect. A capture of every MUTE in Pro Audio Mode
on 10 October confirmed them there, and showed that a loopback return's
MUTE has no property: it writes the gain to off, the bottom step of the
return's volume control, so the returns get no switch. In Mobile Mode
the inputs' MUTEs were never pressed in a capture; that they are 05
there too rests on the application writing 0 to it at every connect.

The cover letter is written for the six patches. Its Tested list still
holds the numbers of the runs on the four, under a line marked XXX.

Left before posting: the cover letter for eight patches; the runs again on the
eight, with checks of the sixth added -- the controls showing the
card's values after a bind, a write reaching the card, and the battery
falling on Off and rising on Charge over a set time -- and a card in
Mobile Mode: its twenty controls after a bind, the two levels at 0 dB
and every MUTE off, and each input's switch, turned off, taking that
input out of the recording; then, in the cover letter, the numbers in
the Tested list checked against them and the XXX line removed.

## #826, the M62's profile

Jaroslav Kysela's review of 9 October asks for three things: the mode
check moved out of `USB-Audio.conf` into `Topping/M62.conf`, an
`Error` that explains a mode the profile does not know, and a profile
for Mobile Mode, so that PipeWire does not fall back to probing the
card. Written on 9 October and run through the parser of alsa-lib's
master: `USB-Audio.conf` gets one line, `M62.conf` picks the verb file
by bcdDevice, and Mobile Mode gets Playback 1/2 on the headphone stage
and the Recording as one stereo capture device on the Recording fader,
the USB trims held at 0 dB and the Playback 1/2 knob at 0 dB and on
where the kernel publishes them. Decided on 10 October: the four
loopback returns take the card's own gain where the kernel publishes
it, as the inputs do, and not the USB trim of their columns, which sits
after that gain and can only lower what it let through. A return that
PipeWire meets for the first time then starts at the top of that
gain, +12 dB, with the control to bring it down. Written the same day
and run through the parser for a kernel with the gains, one without
them and one without the driver; the comments on BT and OTG IN no
longer call their gain a preamp. Left: a check under PipeWire in Pro
Audio Mode and in Mobile Mode on a kernel with the eight patches, the
push, and the answer to the review; and once the posting is out, the
link in the commit message pointed at it, since the Mobile Mode levels
first appear there.

## UCM, once the next posting is out

- The E2x2 OTG's profile is written, one commit on alsa-ucm-conf
  master over #826, in the manner of #826: the four playback buses
  and IN 1, IN 2, Mobile IN and the three loopback returns as devices
  split out of the two PCMs. With the driver the buses conflict and
  each points `Output 1+2 Playback Source` at itself, with `Master` as
  the volume; the inputs and the loopback returns take the card's own
  gains and faders, and the USB trims are set to 0 dB. Checked on
  6 October under PipeWire with the driver: the source follows each of
  the four profiles; the sink volume moves `Master` and a source's
  volume the card's gain or fader behind it; a tone on Playback 3/4,
  5/6 and 7/8 reached only the loopback listening to it. Left: the
  branch without the driver, on a kernel without it; Playback 1/2 and
  the inputs with a real signal; the pull request, once the next
  posting is out.
- In both profiles a source's volume is the card's own gain, not a USB
  trim: the driver exists so that PerDeviceEQ moves the card's gain
  stages. A source PipeWire sees for the first time starts at 100%,
  which is the top of that gain -- +88 dB on the M62's IN 1 and IN 2,
  +9 dB on its AUX, +20 dB on the E2x2 OTG's inputs -- until a level
  is set; that is accepted.
- #803 (the plain E2x2, `152a:8752`): the comment drafted on
  4 October. The 8752 goes into the driver only with its channel
  names and a test by someone who has one.

## snd-usb-audio

- No positional channel-map guess when `bmChannelConfig` is 0, and
  the card's own channel names from `iChannelNames` instead, as
  agreed with Takashi on 28 August; this is also what PipeWire #5423
  needs.
