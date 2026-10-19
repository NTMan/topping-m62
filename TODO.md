# Pending work

Everything agreed on and not yet done, kept here rather than in
anyone's memory. An item leaves the list when it is done.

## The kernel series

v10 goes to 7.5, as Takashi Iwai answered on 19 October (cover letter:
https://lore.kernel.org/all/20261018205711.168291-1-mikhail.v.gavrilov@gmail.com/).

- After 7.4-rc1: whether v10 applies to Takashi's for-next. If it
  does, nothing is sent; if not, v11, rebased.
- If nobody has reviewed it two or three weeks after rc1: one line in
  v10's thread, not the series again.
- 3/8 and 5/8, the HID patches v8 did not have, still need an ack
  from the HID side; 1/8 carries Jiri Kosina's.

## UCM

- #826, the M62's profile, links v10 since 19 October and waits for
  Jaroslav Kysela's word on the update.
- The E2x2 OTG's profile, one commit over #826, goes as a pull
  request of its own. Before it: the profile on a kernel without the
  driver, and the inputs with a real signal; its commit message to
  link v10, as #826's does.
- #803 (the plain E2x2, `152a:8752`): the comment drafted on
  4 October. The 8752 goes into the driver only with its channel
  names and a test by someone who has one.

## snd-usb-audio

- No positional channel-map guess when `bmChannelConfig` is 0, and
  the card's own channel names from `iChannelNames` instead, as
  agreed with Takashi on 28 August; this is also what PipeWire #5423
  needs.
