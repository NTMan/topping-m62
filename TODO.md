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

The M62's Mobile Mode, found on 9 October, gets its own controls: in
that mode the card's capture is one mix of its inputs and part of the
address map means something else, and the six patches wrote Pro Audio
Mode's values into it -- the first bind's Q25 for Loopback 1/2 raised
the recording by 9 dB. The rows that only one mode has are tagged, and
the mode is taken from bcdDevice; Live Streaming goes with Pro Audio,
since its connect push, captured on 10 October, writes the inputs, the
loopback returns and the outputs at the same targets and on the same
scales. Mobile Mode keeps the gains, the two output volumes and the
port power settings, and gets `PCM Playback Volume` (the Playback 1/2
knob, the playback's level in the headphones) and `Recording Capture
Volume` (the Recording fader), both written at 0 dB at the first bind.
Written first as a seventh patch, it was folded on 11 October into the
second, so that Mobile Mode gets its controls in the patch that gives
Pro Audio and Live Streaming Mode theirs; the series has been seven
patches since, the MUTEs the seventh. Each of the seven compiles with
W=1 and sparse without a warning in the files it touches, and the last
one's tree is the eight patches' but for two comments:
topping_index_of()'s is back above it, and the header's first
paragraph is rewrapped, which the sixth patch had left with
a 91-column line. The sixth patch's message now says that both port
power settings are in every mode, the card announcing them in Mobile
Mode as well.

A seventh patch, asked for on 10 October, adds the MUTE beside each
level as a switch of the same name: the inputs' at property 05, the
outputs' at 04, and in Mobile Mode the knob's and the fader's at 04.
All are written with the sound on at the first bind, as M Control
Center does at every connect. A capture of every MUTE in Pro Audio Mode
on 10 October confirmed them there, and showed that a loopback return's
MUTE has no property: it writes the gain to off, the bottom step of the
return's volume control, so the returns get no switch. A capture of
every MUTE in Mobile Mode the same day found the inputs' at 05 there
as well.

A test on Linux the same day wrote each level of Pro Audio Mode alone
while its MUTE was on: the inputs, IN 1 included in a second run, kept
their MUTE, but HP's volume released HP's, and the card reported that
at `64/04`, which the switch follows. In the second run HP's MUTE
written right after its volume, as the bind, the resume and alsactl
write them, did not hold: the card released it later and reported the
release, so a mute those write back after HP's volume would not stay.
How the seventh patch is to treat HP's switch is to be decided. A
third run found OTG OUT keeping its MUTE, so HP's is the only one
released in Pro Audio Mode; Mobile Mode is still to be run.

Decided the same evening: before anything is decided for HP's switch,
every port is checked by its own sound, not by a meter, in Pro Audio
and in Live Streaming Mode, with repeats (`m62-mutecheck.sh`): the
inputs in their columns, HP through a cable from HP to AUX, OTG OUT
through the phone on the OTG port sending it back on OTG IN. On HP
that includes the level written as it is, a repeated MUTE, a long wait
under the MUTE, and the MUTE written after the card's release and 300
ms and 1 s after the level. Mobile Mode, where a cable from HP to AUX
would feed back, comes after that.

The check ran in Pro Audio Mode the same evening. The inputs and OTG
OUT kept their MUTE in every probe, OTG OUT in the phone's own
recording as well. HP's sound did not reach AUX's columns that time,
the cable from HP to AUX not being in place, and HP was run twice more
with it. By HP's sound, a MUTE written after a level written with HP
sounding held all eighteen times, back to back as the driver writes
them included; a level written under HP's MUTE released it in eighteen
writes of thirty-six, the value HP had included; with the MUTE written
back to back behind the volume, as the bind, the resume and alsactl
write a mute back, HP was left sounding in four probes of six; and
with no level written HP's MUTE was never released. On 11 October,
just after midnight, Live Streaming Mode gave the same: the inputs and
OTG OUT kept their MUTE, and a level written under HP's MUTE released
it in eleven writes of eighteen; with the MUTE written back to back
behind the volume HP was left sounding all three times. A run after it
found that neither the order in which Control Center writes a pair,
0x63 first, nor its checksum 00 00 decides the release: a level write
to 0x64 brings it, and one to 0x63 alone did not once.

Two captures from M Control Center later that night had a MUTE pressed
and then its level turned on the card. The card reported HP's MUTE
released by HP's knob all 22 times. IN 1's gain knob released IN 1's
MUTE all 44 times by IN 1's meters, but the card reported 39 of the
releases, and its announce carries the outputs' MUTEs, not the
inputs', so a switch that follows `21/05` would have stayed off after
the other five while IN 1 was not muted. The card reported every step
of both knobs. Left: the decision on HP's switch, and whether a switch
is to be turned on when the card reports its port's level turned by
hand.

Decided the same night: no. A switch follows the card's report of its
MUTE alone, as Control Center's MUTE does, which stayed lit through
the knob's reports where the card left a release unreported. A release
the card does not report is the card's fault, and the driver does not
cover it. Left: the decision on HP's switch; and every knob checked by
its port's sound on Linux, IN 1's included, which Control Center's
captures could not do (`m62-knobcheck.sh`).

The check ran the same night in Live Streaming Mode on IN 1, IN 2, AUX
and HP, twenty turns each. By sound the first step of 79 turns in 80
released the MUTE; the card reported every release of HP, IN 2 and AUX
and 17 of IN 1's 20, and on IN 2 and AUX it left the gain of the
releasing step unreported in 33 turns of 39, so the gain controls,
which follow the card's reports, would show the gain before that step
until the next one. IN 2 and AUX stood at the tops of their ranges, IN
1 and HP did not. Left: the decision on HP's switch; and the check
again with those levels swapped, and on OTG OUT with the phone on the
OTG port, the script now taking a report of the MUTE released, or the
port's sound, for the step as well.

It ran again the same night with those levels swapped and the phone on
the OTG port. The gains left unreported go with IN 2, AUX and OTG OUT,
not with the tops of the ranges: IN 1 and HP, near their tops,
reported all forty. OTG OUT's knob released its MUTE all twenty times,
and the card reported each release. The gain controls follow the
card's reports, so after a release by the knob they fall behind AUX's
and OTG OUT's levels until a step is reported, and match IN 2's, which
stays at the gain last reported. Between the first two runs PipeWire
had written back the levels the knob had turned while its profile was
off, so the script now sets a run's levels itself. Left: the decision
on HP's switch; and whether PipeWire follows a level turned on the
panel while its profile is on.

Decided on 11 October: HP's switch follows the card's report at
`64/04`, and HP's volume is written as it is. Where the card releases
HP's MUTE after a write of the volume, the bind's and a resume's
included, the switch shows it, as it shows a release by a knob; the
driver neither holds the volume back nor writes the MUTE again. The
seventh patch's comment and message now say that the card releases
MUTEs by itself and that the switches follow its reports. Left of the
MUTE work: whether PipeWire follows a level turned on the panel while
its profile is on.

Asked on 11 October whether the E2x2 OTG wants MUTE switches as well.
A capture the same day (`E2x2 OTG - Mutes and Faders.pcapng`, see
PROTOCOL.md) found no MUTE of its own on that card: the program writes
the level to 0, an input's gain or a fader's pair, and writes 0 again
at every step of that level while the MUTE is lit. Output 1+2 has no
MUTE, only its three output buttons, which the driver has. A second
capture, every MUTE released in the same order, found the release
writing the level the program had kept, and nothing else, and each
input coming on within 62 ms: the card holds no MUTE of its own, only
the level. The first bind writes every level of the E2x2 OTG, so a
MUTE another host left does not outlive it, and a fader's bottom step
is already off, which is what the program writes for its MUTE; an
input's gain has no off step. Left: whether the E2x2's input gains get
one, and a sentence in the seventh patch's message on why the E2x2 OTG
gets no switches.

Decided the same day: the seventh patch's message says why the E2x2
OTG gets no switches, since without that the card's controls look
unlike the M62's for no stated reason. It also says that an input's
gain starts at +0 dB and that an input's recording is muted with the
switch the USB side has on each capture channel, so an off step for
the E2x2's input gains would change that paragraph as well. Left:
whether they get one.

Decided the same evening: the E2x2 OTG's inputs get MUTE switches
after all, in an eighth patch, and the paragraph on that card moves
there from the seventh. An off step at the bottom of each gain was
rejected: the step above it is +0 dB, so the input would go from
silence to its full level in one step, and a sound server following
the scale in decibels would find nothing between the two. The card
keeps the MUTE as its gain's 0, which the gain never takes by itself,
so each switch shares that property with its gain: 0 while the switch
is off, the gain otherwise, and a gain set while it is off only kept,
as Control Center keeps it. The faders get no switch: their bottom
step is that 0 already, and the steps above it start at -80 dB. Each
of the eight patches compiles with W=1 and sparse without a warning in
the files it touches.

The cover letter is written for the six patches. Its Tested list still
holds the numbers of the runs on the four, under a line marked XXX.

Left before posting: the cover letter for eight patches; the runs
again on the eight, with checks of the sixth added -- the controls
showing the card's values after a bind, a write reaching the card, and
the battery falling on Off and rising on Charge over a set time -- and
a card in Mobile Mode: its twenty controls after a bind, the two
levels at 0 dB and every MUTE off, and each input's switch, turned
off, taking that input out of the recording; and the E2x2 OTG's input
switches, off silencing the input's meter, a gain set while off kept,
and on bringing that gain back; then, in the cover letter, the numbers
in the Tested list checked against them and the XXX line removed.

The runs on the eight patches began on 13 October with `m62-runs.sh`,
written anew from the logs of 5 October, whose script was not kept.
The E2x2 OTG gets a pass of its own: one phone cannot feed the inputs
of both cards. The M62's pass, on 7.3-rc7 with the series' four new
files as posted and the loaded modules matched by build ID: a suspend
that reached S3, after which the driver's controls read as before and
the headphone knob was reported, the RTC alarm at 120 s, since at 20 s
it fired before the devices had suspended and so aborted the suspend;
two cable pulls under playback and a loop of writes, each followed by
a bind, the loop's writes taken and no error from the drivers, and the
battery shown 2.3 s and in UPower 2.4 s after the card came on USB;
Mobile Mode's twenty controls, its first bind writing every MUTE 0 and
both levels at 0 dB, and the battery shown 3.3 s after the card;
fifty reloads and fifty binds, amixer's contents unchanged; five
audio-side rebinds, every control back; alsactl's store and restore
through a file exiting 0; both port power settings written Off through
the controls and read back from the card's announce at three first
binds; Loopback 1/2 at digital zero on Playback 3/4 and moved by
-20.00 and +12.00 dB by its gain; in Pro Audio Mode every input's
switch taking its columns to digital zero; nothing in the kernel log.
The tone reached Loopback 1/2 at -61.01 dBFS, not at the -23.01 of
5 October: the USB trims of Playback 1/2 stood at -38 dB, set by
something other than the driver, and the record step now holds the
trims at their top while it measures. Not yet usable: the inputs'
switches in Mobile Mode, read inside the tail of the card's reverb
(see PROTOCOL.md), to be read again past it; and the battery, which in
15 minutes a half moved by no more than its readings swing -- Off 92
to 93 %, Charge 93 to 88 % with steps back and forth of up to 4 % -- so
the time for each half is still to be decided. Left: those two, the
E2x2 OTG's pass, and the cover letter.

The second runs, the same night. Mobile Mode's switches read past the
reverb's tail: IN 1's recording reached digital zero 4.5 s after its
switch went off and IN 2's 6.5 s after, AUX's and BT's at once; OTG IN
recorded digital zero even switched on, the change of mode having
stopped the phone playing into it (see PROTOCOL.md), so for it the
first pass stands, where off took it from -35.35 dBFS to digital zero.
The record step with the trims held at their top: Loopback 1/2 at
-23.01 dBFS, as on 5 October, the rest as in the first pass. The first
pass's -38 dB came from the runs, not from the driver. The port step
creates the card three times with hid-topping out, and PipeWire reads
the card's UCM file only when the card arrives: without the driver's
controls the M62's HiFi verb has no outputs in conflict -- one
profile, which PipeWire names just "HiFi" -- and takes their volumes
from the USB trims, which that verb leaves unpinned. The reading
lasted until the card arrived again, and the sinks' volumes stood on
the trims, -38 dB on Playback 1/2 and -23 dB on the rest. The script
now ends the port step by creating the card once more with hid-topping
in place and putting the input gains back, and sets PipeWire's
profiles through `pw-cli` with `save: false`: a profile set through
`pactl` WirePlumber keeps for the card's name, "off" too, and the
card's quick returns had WirePlumber name it `...-00.2` now and then.
At the second pass's switch to Mobile Mode alsactl's restore wrote 0
to BT's and OTG IN's gains (`25/04`, `27/04`), which at the first it
had written as 99; a second later the card reported BT's gain as 99,
and nothing for OTG IN's. Neither gain is in the card's announce (see
PROTOCOL.md), and after the port step's first binds nothing in the run
set them again. `/var/lib/alsa/asound.state`, stored at 01:48 after
the runs, holds 99 for both, as the controls read now, so when the
zeros were stored no longer shows; nor does what a 0 written to either
gain does to its input, OTG IN's phone having stopped. The record step
now reads that: each of the two gains written 0 and put back, the
input in its own columns; and after each change of mode the script
waits for the card's meters of BT and OTG IN before it reads them.
GNOME's Power settings list the card's battery, at 87 % after the
runs. Left: that reading, and with it whether the driver should show 0
for a gain nobody has reported or set; the battery's time; the E2x2
OTG's pass; and the cover letter.

The third run, 03:34, the port step and the record step with the
script so changed. After the port step PipeWire had the card's full
profile, `HiFi (Bluetooth, Line1, ...)`, the trims stood at their top
before the record step pinned them, Loopback 1/2 read -23.01 dBFS, and
at the end the profile and the five input gains were as at the start,
the profiles having gone through `pw-cli`. BT's and OTG IN's gains,
each written 0 from 99, took their columns to digital zero, and 99
written again brought the level back (see PROTOCOL.md). So a 0 that
alsactl has stored for either, as it had before the second runs,
silences that input when it is restored, where the card keeps it:
after the restore's 0 at the switch to Mobile Mode the card reported
BT's gain as 99, and BT was heard in that step's recording. To
decide: whether the first bind should write those two gains at 0 dB,
as it writes the other values the card does not report. Left: that,
the battery's time, the E2x2 OTG's pass, and the cover letter.

Decided on 13 October: the battery step leaves the runs. Whether the
card charges depends on the current its port can give, which a hub
may not have -- on Charge in these runs the battery fell, 93 to 88 %
in 15 minutes, and GNOME showed 87 % after them -- so an hour of
waiting would show the hub, not the driver. What is the driver's the
other steps show: the setting reaching the card and coming back in its
announce at a first bind (the port step), the capacity the card
reports reaching the power supply 2.3 s and UPower 2.4 s after each
plug (the cable pulls), and GNOME's Power settings listing it. The
question of the gains is not BT's and OTG IN's alone: the card leaves
out of its connect report the gain of an analogue input with nothing
plugged into it (see PROTOCOL.md), whose control then shows the same 0
-- 0 dB for IN 1 and IN 2, -inf for AUX -- for alsactl to store; the
runs never had an analogue input empty. The inputs differ only in when
the card reports a gain. To decide: whether the driver writes, once
the card's connect report is over, every gain nobody has reported or
set, and at what -- 0 dB for all five, or the quiet end as for the
headphones; a write at the first bind would destroy the gain the card
is about to report for an input with a jack in it. Left: that, the
E2x2 OTG's pass, and the cover letter.

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
longer call their gain a preamp. The same day the card's USB playback
switches read on for channels 1 and 2 and off for 3 to 10, set so by
nobody known. With the kernel the playback devices take the headphone
stage and nothing would turn those switches back on, so the verb now
turns a trim's switch on wherever it pins the trim open, and Direct
unmutes the ten playback channels as it does the sixteen capture
columns.

Decided on 12 October: the profile needs no change for the eight
patches. The MUTEs they add are switches named after the levels the
devices already take -- Headphone, Mic1 Analog, Mic2 Analog, Aux,
Bluetooth, OTG, Recording -- so alsa-lib's simple mixer joins each
switch to its level's element and PipeWire mutes through it; the
Playback 1/2 knob's switch is the one the Mobile Mode verb already
turns on. The commit message is rewrapped where earlier edits had left
short lines, with no word changed. Exported with the E2x2 OTG's
profile, an installer and a check: the check plays a tone through each
playback device in turn, printing the output selector, and moves each
sink's and source's volume and mute, printing the control behind it.
Left: that check in Pro Audio Mode and in Mobile Mode on a kernel with
the eight patches, and its results in the Tested paragraph, whose
Mobile Mode part still reads XXX; the push, and the answer to the
review; and once the posting is out, the link in the commit message
pointed at it, since the Mobile Mode levels and the mutes first appear
there.

Checked the same night on 7.3-rc6 with the eight patches, from the
alsa-ucm-conf checkout PipeWire reads -- its `ucm2/USB-Audio/Topping`
tree 56d38769, the two exported commits -- in all three modes and on
the E2x2 OTG. A tone through each playback device, set to 30% and
unmuted for its tone, was heard in the headphones, the output selector
following the device; each sink's and source's volume moved the card's
control behind it, and its mute the switch beside that control, or the
lowest step where there is none; the trims stayed at 0 dB and on, and
the Playback 1/2 knob too in Mobile Mode. The Tested paragraphs of
both commits now say so. One step did not hold once: in Pro Audio
Mode, 0.5 s after the sink was muted, HP's switch read on again with
the level unchanged, where the five other runs read it off. The check
writes the sink's volume back and then its mute, and a MUTE written
after a level held in all 27 probes of 10 and 11 October, so what
released it is not known. Left: what released HP's MUTE there; the
push, and the answer to the review; and once the posting is out, the
link in the commit message pointed at it.

The same night: the run on HP's MUTE concerns the driver and the card,
not the profile, so #826 does not depend on it. Its commit message
linked v8, whose controls the profile would not find: v8 names IN 1's
and IN 2's gains Mic-1 and Mic-2 and has no loopback gains, Mobile
Mode levels or switches. The paragraph now says that the names are
those of the series' next version, to be linked once it is posted, and
keeps v8's link; the Tested paragraph says the runs were on that next
version. `m62-hpmute.sh` repeats the check's step that did not hold,
the sink's volume put back and the sink muted at once, twenty times in
Pro Audio Mode, with usbmon recording every vendor frame to and from
the card, so that each cycle shows whether the host wrote HP's level
after the MUTE and whether the card reported a release.

It ran the same night (`m62-hpmute.txt`, Pro Audio Mode, twenty
cycles, PipeWire's profile unchanged throughout): HP's MUTE held in
all twenty. In each cycle the level went out 15 ms after the volume
was put back and the MUTE 25 to 29 ms after the level; nothing else
reached HP until the unmute, the card reported no release, and usbmon
dropped nothing. Nothing but the loop's frames and the driver's
keepalive went to the card. So the check's step does not release HP's
MUTE; in the run where it was released, the check had switched
profiles and begun its step on the sink a second after the switch. At
a switch, WirePlumber puts each selected route back with one Route
param carrying its mute and its volumes (`apply-routes.lua`), and ACP
applies a mute in such a param at once and the volumes after it
(`apply_device_props` in `alsa-acp-device.c`): a route saved muted
gets HP's MUTE written first and, where the level changes, the level
after it, under the MUTE. `m62-hpmute2.sh` takes that next, ten cycles
of each kind: the sink muted, the profile switched to Playback 3/4's
and back; and the profile switched away and back before the check's
step.

The second run (`m62-hpmute2.txt`, see PROTOCOL.md) found HP's MUTE
lost under PipeWire in two ways. Switched back to Playback 1/2's
profile with the sink muted, the host wrote HP's MUTE and then its
level 4 ms later, ten times in ten. In the three of those cycles where
nothing more was written to HP for half a second after the level, the
card released the MUTE in two; the other seven do not tell, the
script's own unmute having reached HP 27 to 52 ms after the level. So
with the eight patches as they stand the card can release a muted HP
at a switch back to its device. That run's reads came as the switch
back reached the card; where the card released the check's own MUTE
and reported it, HP's switch read on within 0.4 s and PipeWire's sink
unmuted. And in one of the 29 cycles of the two runs that wrote
nothing to HP after the MUTE, the card released a MUTE written 26 ms
after the level, as in the check. The switch back, asked for 1 s after
the switch away, reached the card 2.8 to 2.9 s after it was asked for,
so a script that reads after a switch has to wait for it.

The third run (`m62-hpmute3.txt`) took that switch back alone, twenty
times, waiting 4 s after each switch and writing nothing in between.
The switch back then reached the card 30 to 36 ms after it was asked
for, and wrote HP's MUTE and then its level 4 ms later every time. The
card released the MUTE after eleven of the twenty, and in each of the
eleven PipeWire wrote the MUTE again 1.95 to 1.97 s after the switch
back; the card sent nothing after it, and 4 s after the switch HP's
switch was off and PipeWire's sink muted in all twenty. With the eight
patches as they stand, then, a switch back to a muted HP releases it
in about half the switches, for 1.8 to 1.9 s.

Decided on 12 October, after that run: for every MUTE of the M62, a
level set while its switch is off is only kept, and written when the
switch is turned on, just before the MUTE is released, as M Control
Center writes a level turned under a MUTE before its MUTE 0. That
takes back the part of the decision of 11 October on HP's volume: the
driver is to hold it back under the MUTE, as the eighth patch holds
the E2x2 OTG's input gains, and as PipeWire holds the volume of a
control it mutes by the bottom step. HP's switch still follows the
card's reports, of a release by a knob among them.

The same day the seventh patch got that: a level set while its switch
is off is only kept, the switch writes it on its way on, before the
MUTE 0, a bind and a resume write a muted level's MUTE alone, and a
level or a release the card reports drops a level kept under that
MUTE. The eighth patch's zero_mute switches stand beside it unchanged.
Each step builds with W=1 and sparse, checkpatch finds nothing new,
the eight apply to af32da4 and give the branch's files, and a test of
the write, report and put paths cut out of the driver and run in
userspace against a recorder passes on them and fails on the eight
before in the cases the change covers.

Run on the M62 that afternoon, on 7.3-rc7 with the change
(`m62-hpkeep.txt` and `m62-hpmute3.txt`, see PROTOCOL.md): the volume
set five times under HP's MUTE reached the card only at the unmute,
just before the MUTE 0, the control showing it meanwhile; and of
twenty switches back to the muted Playback 1/2 none wrote HP's level,
none brought a release, and HP's switch and PipeWire's sink read muted
4 s after each. Left: the other runs before posting, listed under the
next posting; the push, and the answer to the review; and once the
posting is out, the link.

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
  5/6 and 7/8 reached only the loopback listening to it. Moved on
  12 October onto the reworked #826: a Macro line beside the M62's in
  `USB-Audio.conf`, without the comment on its bcdDevice, since that
  file no longer reads any; and, as in #826, the verb turns the trims'
  switches on where it pins the trims open. The eighth patch's input
  MUTEs join the gains' elements with no line in the profile. Checked
  the same night with the eight patches, with the check exported with
  #826: a tone through each of the four buses was heard, Output 1+2
  following the device; each sink's and source's volume moved the
  card's control behind it, and its mute the input's switch, or the
  lowest step of `Master` and the loopback faders; the Tested
  paragraph says so. Left: the branch without the driver, on a kernel
  without it; the inputs with a real signal; the pull request, once
  the next posting is out, with the link to it in the commit message.
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
