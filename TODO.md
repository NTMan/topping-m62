# Pending work

Everything agreed on and not yet done, kept here rather than in
anyone's memory. An item leaves the list when it is done.

## Series v9

Sent after review of v8, or about two weeks after v8 if no review
comes, in which case it doubles as the ping.

- Control names, while they can still change -- once merged they are
  ABI:
  - selectors become `... Playback Route` and `... Capture Route`,
    the form `Documentation/sound/designs/control-names.rst` gives;
    alsa-lib's simple mixer takes an enumerated control with that
    suffix as a playback or capture enum;
  - `Mic-1 Analog Capture Volume` and `Mic-2 Analog Capture Volume`
    become `Mic1 ...` and `Mic2 ...`: no control in the tree has a
    hyphen there;
  - on the E2x2 OTG: `Mic1 Digital Capture Volume`, `Mic2 Digital
    Capture Volume`, and `SPDIF ...` instead of `S/PDIF Out ...`.
- The M62's loopbacks, owned like the E2x2 OTG's: a source and a gain
  for each of the four, targets `0x51`..`0x58`, properties `02` and
  `03`. Before any code:
  - read from an M62 capture with a connect what M Control Center
    writes there; that is what the first bind writes;
  - write both from Linux and look at what arrives on the loopback
    columns: which target of a pair takes the source, and what scale
    the gain has.
- The E2x2 OTG as patches 3/4 (HID) and 4/4 (controls), after the
  runs the M62 had for v8: module reload cycles, suspend and resume,
  cable pulls under playback and under writes, `alsactl`, and a
  build with KASAN and lockdep.
- The M62 runs again on the renamed build.
- Undecided: a read-only `Monitor Mix` control for the E2x2 OTG's
  knob. The card reports the knob when it turns and in its answer to
  `11/01`, and `11/01` does not disturb the monitor mix.

## UCM, after v9

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
