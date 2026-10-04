# Pending work

Everything agreed on and not yet done, kept here rather than in
anyone's memory. An item leaves the list when it is done.

## The next posting of the series

Sent after review of v8, or about two weeks after v8 if no review
comes, in which case it doubles as the ping.

The four patches are written, on `topping-next` over e767a4ea7: the
controls renamed -- `... Playback Route` and `... Capture Route` for
the selectors, `Mic1` and `Mic2` without the hyphen, `SPDIF` for the
E2x2 OTG's `S/PDIF Out` -- and the M62's loopbacks, a source and a gain
for each of the four. On the M62 they were checked on 5 October: every
control under its new name with the first-bind values, and the
loopback source and gain written through the controls, recorded on
the loopback columns. Left before posting:

- The E2x2 OTG as patches 3/4 (HID) and 4/4 (controls), after the
  runs the M62 had for v8: module reload cycles, suspend and resume,
  cable pulls under playback and under writes, `alsactl`, and a
  build with KASAN and lockdep.
- The M62 through those runs again, on this build.
- Undecided: a read-only `Monitor Mix` control for the E2x2 OTG's
  knob. The card reports the knob when it turns and in its answer to
  `11/01`, and `11/01` does not disturb the monitor mix.

## UCM, once the next posting is out

- #826: the three renamed controls it checks -- `Headphone Playback
  Route`, `Mic1 Analog Capture Volume`, `Mic2 Analog Capture
  Volume`.
- A profile for the E2x2 OTG in the manner of #826: a stereo device
  per bus, conditions on the driver's controls, the output's source
  following the device, the loopbacks as capture devices, `Master`
  as the volume.
- #803 (the plain E2x2, `152a:8752`): the comment drafted on
  4 October. The 8752 goes into the driver only with its channel
  names and a test by someone who has one.

## snd-usb-audio

- No positional channel-map guess when `bmChannelConfig` is 0, and
  the card's own channel names from `iChannelNames` instead, as
  agreed with Takashi on 28 August; this is also what PipeWire #5423
  needs.
