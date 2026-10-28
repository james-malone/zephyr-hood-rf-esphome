title: Zephyr Hood Remote
subtitle: 315 MHz RF Protocol / Reference and Implementation Notes
eyebrow: Technical Reference
series: Kitchen Ventilation
company: James Malone
division: Home Automation
doc_number: ZH-RF-01
edition: First Edition
date: October 2026
classification: Restricted
runhead: Zephyr Hood Remote / RF Protocol
cover_motif: waveform
abstract: The four-button remote supplied with the Zephyr Lux Glo Island hood (model DLG-E36AWX) transmits a 24-bit fixed code by on-off keying at 315 MHz. Each word is a 16-bit address, 0x0514, followed by an 8-bit command, sent with a pulse-width code whose unit is 270 microseconds and closed by a sync pulse 31 units long. The remote repeats the word seven or eight times per press. There is no checksum, counter, rolling code or return channel, so the hood can be operated by replaying the four codes, and its state cannot be read over this link. An ESP32 with a CC1101 transceiver running ESPHome both decodes the remote and transmits the codes; on the ESP32 the shared data pin must be driven open-drain for transmission to work.

## Summary

The remote is a one-way, fixed-code transmitter of the PT2262 and EV1527 family. Every press of a given button produces the same 24-bit word, and the hood keeps all of its own state. The protocol was established on 27 October 2026 by receiving the remote with a CC1101 and decoding 709 bits from four presses; the transmit path was then confirmed by operating the hood from Home Assistant.[^setup]

[^setup]: ESP32 DevKit V1 with an Ebyte E07-M1101D CC1101 module, ESPHome 2026.10.0.

```spec
{"title":"Protocol at a glance",
 "groups":[
  {"heading":"Radio","items":[["Carrier","315 MHz"],["Modulation","OOK"],["Direction","One way, remote to hood"]]},
  {"heading":"Line code","items":[["Unit T","270 us (measured 269.6)"],["Bit 0","1T on, 3T off"],["Bit 1","3T on, 1T off"],["Sync","1T on, 31T off"]]},
  {"heading":"Framing","items":[["Word","24 bits, MSB first, then sync"],["Word length","128T = 34.6 ms"],["Repeats per press","7 to 8"],["Address","0x0514"],["Integrity","None"]]}]}
```

```callout
{"kind":"warning","title":"Fixed code.","text":"Anyone within radio range who knows a code can operate the hood. Treat the codes in this document like a garage-door code."}
```

## Command Set

Four buttons each send one code. The light and the fan step through their levels inside the hood, so a press means "next level", never "set level".

Table: Command codes for remote address 0x0514.

| Button | Code | Command byte | Hood action |
| --- | --- | --- | --- |
| Light | 0x051430 | 0011 0000 | Light: off, low, medium, high, off |
| Fan | 0x051403 | 0000 0011 | Fan: off, low, medium, high, off |
| Power | 0x05140C | 0000 1100 | Fan and light off |
| Delay off | 0x0514C0 | 1100 0000 | Starts the delay-off timer |

Pressing Fan and Delay off together puts the hood into Wi-Fi pairing mode, according to Zephyr's Connect guide for DLG models. If the two digits combine as on other PT2262 remotes, that code is 0x0514C3. It has not been captured.

## Physical Layer

The remote runs from a 23A 12-volt cell and carries the FCC grantee code VVP, which belongs to Leyant Industry, Zephyr's manufacturer. A 433.92 MHz filing exists for Zephyr part 14000010 (FCC ID VVP-14000010), but it describes a different remote: nothing from this one was received at 433.92 MHz in any modulation tried.

At 315 MHz the band was silent except for the remote. Four presses, one second apart, produced four isolated bursts of 110 to 150 pulses each, read on an edge counter at one-second resolution.[^decoys]

[^decoys]: Two unrelated 433.92 MHz sensors nearby transmit every 30 and 50 seconds, with 425 and 2150 microsecond pulses. They were briefly mistaken for the remote.

Table: Receiver settings used for capture.

| Setting | Value |
| --- | --- |
| Frequency | 315.000 MHz |
| Modulation | ASK/OOK |
| Filter bandwidth | 812 kHz |
| Receiver glitch filter | 150 us |
| End-of-frame idle | 25 ms |

## Line Code

Every bit occupies four units. A zero is a short mark and a long space; a one is a long mark and a short space. Each word ends with a sync: one unit of carrier, then thirty-one units of silence.

{{FIG:line-code}}

Table: Measured element durations over 709 bits and 27 sync pulses, in microseconds.

| Element | Nominal | Mean | Std. dev. | Min | Max |
| --- | --- | --- | --- | --- | --- |
| Short mark | 270 | 270 | 14 | 220 | 300 |
| Long mark | 810 | 815 | 10 | 790 | 840 |
| Short space | 270 | 265 | 10 | 240 | 290 |
| Long space | 810 | 806 | 17 | 750 | 940 |
| Sync mark | 270 | 271 | 12 | 260 | 290 |
| Sync gap | 8370 | 8383 | 8 | 8370 | 8400 |

```chart
{"type":"bar","mode":"grouped","title":"Nominal and measured element durations","unit":"microseconds",
 "caption":"Measured values sit within 2 percent of the 270 microsecond unit.",
 "labels":["Short mark","Short space","Long mark","Long space"],
 "series":[{"name":"Nominal","values":[270,270,810,810]},
           {"name":"Measured","values":[270,265,815,806],"highlight":true}]}
```

The decoder in this repository accepts a short element of 120 to 480 microseconds, a long element of 560 to 1100, and a sync gap of five milliseconds or more. It decodes words with timing errors of plus or minus 20 percent.

## Word Format

{{FIG:word-format}}

The layout is that of the PT2262 encoder, in which each tri-state digit is sent as two bits: 00 for zero, 11 for one, and 01 for floating.

Table: The codes read as PT2262 tri-state digits.

| Field | Bits | Tri-state digits |
| --- | --- | --- |
| Address 0x0514 | 00 00 01 01 00 01 01 00 | 0 0 F F 0 F F 0 |
| Light 0x30 | 00 11 00 00 | 0 1 0 0 |
| Power 0x0C | 00 00 11 00 | 0 0 1 0 |
| Fan 0x03 | 00 00 00 11 | 0 0 0 1 |
| Delay off 0xC0 | 11 00 00 00 | 1 0 0 0 |

Each button sets exactly one data digit. Eight tri-state address digits allow 6,561 addresses; the hood stores the one it accepts when a remote is paired to it.

## Press Timing

{{FIG:press-burst}}

A tap sends seven or eight identical words, about a quarter of a second of transmission. The hood needs one clean word. The ESPHome transmitter sends ten, which the hood treats as a single press.

## State and Feedback

The protocol has no status request and no reply. The hood has a receiver and no transmitter on this band, and the remote has no receiver. Hood state exists only inside the hood and, for hoods joined to the Zephyr Connect app, in Zephyr's cloud service, which keeps it in an AWS IoT device shadow reached over TLS with a per-device certificate. No local network interface to that state is documented.

The Home Assistant integration in this repository therefore behaves as a second remote: each button sends one press, and nothing is tracked.

## Implementation

```spec
{"title":"Transceiver configuration",
 "groups":[
  {"heading":"Hardware","items":[["Controller","ESP32 DevKit V1 (WROOM-32)"],["Radio","Ebyte E07-M1101D, CC1101"],["Antenna","SMA whip, 433 MHz"]]},
  {"heading":"Radio","items":[["Frequency","315 MHz"],["Modulation","ASK/OOK"],["Output power","+10 dBm"],["RX bandwidth","812 kHz"]]},
  {"heading":"Data path","items":[["Pin","GDO0 to GPIO4, shared TX and RX"],["Pin mode","Open drain, pull-up"],["Words per press","10"]]}]}
```

```callout
{"kind":"important","title":"Open drain on the ESP32.","text":"With the cc1101 gdo0_pin option sharing GPIO4 (automatic mode switching), reception worked but the hood ignored every transmission. Configuring the shared pin as open drain with a pull-up, as the ESPHome CC1101 documentation requires on the ESP32, made the first transmission work."}
```

The 433 MHz module and antenna operated the hood at 315 MHz from directly beneath it. If range from the final mounting position is marginal, a 315 MHz module and antenna is a direct replacement with no change to the configuration.

## Method

The protocol was found by elimination. A published project for an older Zephyr remote pointed to 433.92 MHz, which proved wrong; a frequency sweep driven from Home Assistant located the remote at 315 MHz, and raw captures relayed through a Home Assistant sensor were decoded off-line.

```flow
{"title":"Path to a working transmitter","caption":"Each step was confirmed against Home Assistant history before the next.",
 "rank":[["lead"],["decoys"],["sweep"],["decode"],["txfail"],["fix"]],
 "nodes":[{"id":"lead","label":"433.92 MHz, older protocol: no reception"},
          {"id":"decoys","label":"Raw capture: two 433 MHz sensors"},
          {"id":"sweep","label":"Frequency sweep: bursts at 315 MHz"},
          {"id":"decode","label":"Decode: 24-bit fixed codes","emphasis":true},
          {"id":"txfail","label":"Transmit: hood ignores"},
          {"id":"fix","label":"Open-drain pin: hood responds","emphasis":true}],
 "edges":[{"from":"lead","to":"decoys"},{"from":"decoys","to":"sweep"},{"from":"sweep","to":"decode"},
          {"from":"decode","to":"txfail"},{"from":"txfail","to":"fix"}]}
```

Table: Sources.

| Source | Use |
| --- | --- |
| ESPHome CC1101 component documentation | Radio driver and ESP32 wiring method |
| HomeSpan ZephyrVentHood project | Older 433 MHz Zephyr protocol, ruled out |
| Zephyr Connect quick start, 2025 | Pairing combination for DLG models |
| FCC ID VVP-14000010 | 433.92 MHz Zephyr remote, a different model |
