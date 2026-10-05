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

The runs were done on 5 October on both cards, on the build as it is
to be posted: KASAN, lockdep and UBSAN on; fifty HID reloads, five
audio-side rebinds per card, `alsactl restore`, suspend and resume,
two cable pulls per card under playback and writes, and the M62's
Loopback 1/2 recorded through the controls; nothing in the kernel log.
Under PipeWire the M62's headphone level follows the desktop and the
knob both ways, and the desktop moves the E2x2 OTG's `Master` (the
card shows no level of its own). The cover letter is written; what is
left is sending it.

## UCM, once the next posting is out

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
