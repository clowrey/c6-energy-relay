# C6 Energy Relay

A Wi-Fi energy meter with two relays, for Home Assistant through ESPHome. It measures the line
voltage and two CT-clamp currents, reports power and energy for each, and switches two loads (or two
contactor coils). It is designed for JLCPCB to build fully assembled. It sits on a DIN rail in a
3D-printed case, inside a plastic junction box.

<p align="center">
  <img src="docs/img/board_iso.png" width="56%" alt="The assembled board, 3D render">
  <img src="docs/img/case_front.png" width="34%" alt="The board in its DIN-rail case">
</p>

> **Status:** the design is finished and checked by its own tests (KiCad ERC and DRC with creepage
> rules, schematic parity, JLC files, case fit, ESPHome config). No boards have been made or tested
> yet. Treat it as an untested design: check it yourself before you build one and connect it to
> mains.

| | |
|---|---|
| MCU | ESP32-C5 (DOIT ESPC5-32-H4, 4 MB flash): dual-band 2.4 + 5 GHz Wi-Fi 6, BLE, 802.15.4 (Thread/Zigbee capable), PCB antenna |
| Metering | BL0939 on UART: voltage, 2 × current, 2 × active power, 2 × energy |
| Voltage sense | ZMPT107-1 current-type transformer, fed through 4 × 100 kΩ from the line |
| Current sense | 2 CT clamps with bare leads (100 A : 50 mA type, e.g. SCT-013-000), 0.6 Ω burden each |
| Relays | 2 × Hongfa HF32FV-16 (16 A SPST-NO), dry contacts, for loads up to 10 A |
| Supply | 100–240 V AC: 120 V line–neutral or 240 V leg–leg, chosen at install. HLK-PM01 isolated 5 V, or USB-C on the bench |
| Terminals | all pluggable: 3 × 5.08 mm 15 A (mains in, relay 1, relay 2), 1 × 3.81 mm 4-pole (CTs) |
| GPIO | every unused GPIO on a 2 × 8 header footprint (holes only, nothing fitted) |
| Qwiic | one Qwiic / STEMMA QT port (JST SH, 3.3 V I2C on GPIO2 / GPIO3, 4.7 kΩ pull-ups) |
| Board | 76.4 × 80 mm, 2 layers, every part on the top side, cut away under the antenna |
| Cost | about $14.70 a board for 30, $11.90 for 100, assembled with plugs (estimate, see [below](#ordering-at-jlcpcb)) |

**Contents:** [How it works](#how-it-works) · [Schematic](#schematic) · [Circuit board](#circuit-board) ·
[Case](#case) · [Safety](#safety) · [Wiring](#wiring) · [Firmware](#firmware) ·
[Ordering](#ordering-at-jlcpcb) · [Building from source](#building-it-from-source) · [Licence](#licence)

## How it works

<p align="center"><img src="docs/img/block-diagram.svg" width="100%" alt="Block diagram"></p>

Everything that touches mains is on the left, and everything you can touch (USB-C, the CT terminal,
the GPIO header) is on the right. Three parts bridge the two sides, and each is rated for it: the
HLK-PM01 power module, the ZMPT107-1 voltage transformer and the relays (coil to contact). On the
board the two sides are kept 6.5 mm apart.

- **Power:** the mains input goes through a 1 A slow SMD fuse in **each** line, so a 240 V leg–leg install
  is fused on both legs. The fuses are Hongda 40T ceramic types rated to break 1000 A at 250 V AC (the
  varistor can fail as a short across the line); Littelfuse's 443 fits the same pads but breaks only
  50 A. No copper runs under them. A 10D561K varistor (MOV) clamps surges after the fuses. The potted
  HLK-PM01 makes an isolated 5 V, 600 mA, with a 220 µF solid polymer capacitor on it. On the bench, USB-C powers the board through an SS14 diode
  instead. An AMS1117-3.3 LDO (a JLC Basic part) makes 3.3 V for the ESP32 and the BL0939. Its dropout
  is 1.1 V at 800 mA, and from USB the diode leaves about 4.5 V, so it still regulates through the
  module's 5 GHz transmit peaks (about 400 mA), with little to spare. Its tab sits on a 3.3 V copper area
  that spreads its heat.
- **Voltage:** four 100 kΩ 1206 resistors in series feed about 0.6 mA at 240 V (0.3 mA at 120 V) from the line into
  the ZMPT107-1, a 2 mA : 2 mA current transformer. Its secondary drives a 51 Ω load, and the BL0939 reads
  that voltage on VP (31 mV at 240 V, 34 mV at 264 V). At 120 V the signal is half the 240 V one;
  calibration covers both. The four resistors turn 0.14 W into heat at 240 V (0.04 W at 120 V).
- **Current:** each CT clamp (50 mA at 100 A) works into a 0.6 Ω burden (two 0.3 Ω 1 % resistors,
  centre to ground) right at the terminal, then ferrite beads and a 1 kΩ / 47 nF filter into the
  BL0939. The beads carry only the BL0939's input current, so a failed bead can't open the CT.
- **Metering:** the BL0939 measures continuously and sends readings over a UART (GPIO1 TX, GPIO0 RX, 4800 baud)
  to the ESP32-C5, which runs ESPHome and reports to Home Assistant.
- **Relays:** each relay coil runs from 5 V through an MMBT3904 transistor (470 Ω base resistor,
  about 5 mA, so it saturates fully at the coil's 80–93 mA; 10 kΩ pull-down so it stays off while
  the ESP32 boots) with a 1N4148W flyback diode. GPIO6 and
  GPIO12 drive them. The firmware gives a coil full voltage for 0.3 s, then holds it with PWM at 60 %
  (the relay's datasheet allows a hold at half the rated voltage), so a held coil makes about a third of
  the heat: roughly 0.15 W instead of 0.4 W. The contacts are dry: COM and NO go to their own terminal and switch whatever
  you wire through them.
- **USB-C** goes straight to the ESP32-C5's native USB (GPIO13/14, through 22 Ω series resistors; there is no ESD protection chip),
  for flashing and logs without a USB-serial chip or buttons.

## Schematic

The full schematic is in [`hw/out/schematic.pdf`](hw/out/schematic.pdf) (KiCad 10:
[`hw/c6-energy-relay.kicad_sch`](hw/c6-energy-relay.kicad_sch)). It is generated from
[`hw/design.py`](hw/design.py), one functional block per section, and every pin connects by a net
label.

[![Schematic overview](docs/img/schematic.png)](hw/out/schematic.pdf)

<details>
<summary><b>Each section, larger</b></summary>

**Mains input, fuses, MOV and the isolated 5 V supply**

![Mains input](docs/img/sch_mains.png)

**Voltage sense:** the divider into the ZMPT107-1, and its 51 Ω load

![Voltage sense](docs/img/sch_vsense.png)

**BL0939 metering and the CT inputs**

![Metering](docs/img/sch_metering.png)

**5 V and 3.3 V**

![Power](docs/img/sch_power.png)

**USB-C** (native USB, series resistors, the SS14 power diode)

![USB-C](docs/img/sch_usb.png)

**ESP32-C5 module, EN and BOOT buttons, status LED, the Qwiic port and the GPIO header**

![MCU](docs/img/sch_mcu.png)

**Relays and their drivers**

![Relays](docs/img/sch_relays.png)

</details>

## Circuit board

76.4 × 80 mm, 2 layers, 1.6 mm, every part on the top side. All the terminals are on the bottom edge,
from left to right: the CTs, the mains input, relay 1 and relay 2. That keeps every wire in one place,
and the low-voltage CT terminal at the far end from the relay contacts. USB-C and the Qwiic port are on
the top edge.
The plug headers stick out 3 mm past the bottom edge, flush with the outside of the case wall, and USB-C
1.25 mm past the top edge, so plugs go in easily with the case on.

The layout is three bands. Along the top: the Qwiic port, USB-C (2.5 mm apart, so both plugs fit side by
side), the LDO and the ESP32-C5 module in the top-right corner. The board is cut away under the module's
antenna (a 26.5 × 6.3 mm notch in the corner), and the copper keep-out around it reaches 3.8 mm past the
module's left side, so there is no board, copper or ground under or beside the antenna. The relays and the
power module are as far from it as the board allows. In the middle: the BL0939 and its input filters in
the left column, the HLK-PM01 beside them, and the GPIO header under the module with the EN and BOOT
buttons and the status LED next to it. Along the bottom: the CT terminal and burdens, the ZMPT107-1, the
fuses with the voltage divider between them, the varistor, and the two relays over their terminals. Every
part has its reference next to it, and the buttons, the LED and every connector pin are named on the
silkscreen.

Small parts keep at least 0.3 mm between their courtyards (the IPC-7351 outline, which already adds
0.25 mm around each part), so there is at least 0.8 mm between any two parts' bodies and pads:
more than JLC's 0.3 mm assembly minimum, with room for a soldering iron.

| Top | Bottom |
|---|---|
| ![Board top](docs/img/board_top.png) | ![Board bottom](docs/img/board_bottom.png) |

| From the front left | Terminals along the bottom edge |
|---|---|
| ![Board, front left](docs/img/board_iso2.png) | ![Board, terminal edge](docs/img/board_front.png) |

**Mains spacing.** The mains parts are in the bottom half, from the input up to the HLK-PM01 (the
unpoured area on the bottom view), and the low-voltage parts around them. The rules are checked by KiCad's DRC, including its
creepage check, on every build:

| Between | Clearance and creepage |
|---|---|
| any mains net and low voltage (ground, 5 V, 3.3 V, signals) | 6.5 mm |
| L and N/L2, the input and each relay, relay 1 and relay 2 | 4 mm |
| a relay's COM and NO (the open contact sees line voltage) | 4 mm creepage, 3 mm clearance |
| L and N/L2 inside the 5.08 mm terminal and the HLK-PM01's pins | 2 mm (the parts' own pitch); a 1 mm slot between the terminal pins lengthens the surface path |
| the voltage divider's nodes, to each other and to L or N/L2 | 1.5 mm clearance (two resistors apart they see about 120 V) |

The relay contacts carry up to 10 A on 5 mm wide copper areas on both layers, with the solder mask
opened so they can be tinned thicker. The case screws pass through the four mounting holes and can be
touched from the back of the case, so every hole keeps 6.5 mm from mains copper, the same as the
low-voltage side.

**Layers.** The board is routed by hand, with no sharp bend anywhere. The tracks are listed in
[`hw/routes.py`](hw/routes.py) as waypoints, and every straight run is at 0°, 45° or 90°:
[`hw/route.py`](hw/route.py) splits any other leg into a straight run and a 45° run, cuts every right-angle
corner into two 45° bends, and rounds each bend with a small arc (0.5 mm radius for signals, 1.5 × the width
for power and mains). Where tracks run together they cross open board on long 45° runs side by side: the GPIOs
leave the module's pins at 45° and fan down to the header in two 45° bundles, the UART pair runs 45° from the
bus down to the BL0939, and the bus cuts its corners long at 45°. Lanes in a bundle keep their spacing through
every bend. Corners where another branch joins stay
sharp, so the joint stays connected. Signal tracks are 0.2 mm, and ground is poured on both layers and
stitched with vias. The LDO's tab (its 3.3 V output, and how it sheds heat) sits on a solid 3.3 V copper
area of about 46 mm².

<p align="center"><img src="docs/img/layer_detail.png" width="60%" alt="Close-up: tracks from the ESP32-C5 module to the GPIO header"></p>

| All copper and top silkscreen | Top copper | Bottom copper |
|---|---|---|
| ![All layers](docs/img/layer_top.png) | ![F.Cu](docs/img/layer_f_cu.png) | ![B.Cu](docs/img/layer_b_cu.png) |

| Top silkscreen | Top solder mask (openings) |
|---|---|
| ![F.Silkscreen](docs/img/layer_f_silk.png) | ![F.Mask](docs/img/layer_f_mask.png) |

The GPIO header (J6) carries 3V3, 5V, GND and GPIO 4, 7, 8, 9, 10, 11, 15, 23, 24, 25, 26 and 27. Power
comes first, then ground, then the GPIOs in the order they leave the module (one row reads 3V3, GND, 7, 9,
27, 23, 11, 26; the other 5V, GND, 8, 10, 4, 15, 24, 25), so a sensor's supply, ground and signal wires sit
side by side. GPIO27 has a 10 kΩ pull-up (R19): the ESP32-C5 needs it high at reset for USB flashing.
The Qwiic port (J7, at the left end of the top edge) is a 4-pin JST SH socket for 3.3 V I2C sensors and
displays: pin 1 GND, 2 3V3, 3 SDA (GPIO2), 4 SCL (GPIO3), with 4.7 kΩ pull-ups to 3V3. GPIO2 and GPIO3 are
strapping pins (MTMS and MTDI), but the pull-ups hold them high at reset, which is what they need there.
The silkscreen marks the strapping pins on the header (7, 25, 26, 27) with `*`: keep them free of pull-downs at reset. The top side names each plug: the CT pins
behind their terminal, `RELAY 1` / `RELAY 2` beside theirs with `COM` and `NO` each over its own contact's copper, `MAINS`, `USB` and `QWIIC`. The Qwiic pins are named in pin order below the socket (`SCL SDA 3V3 GND`)
and again on the bottom side, in the order you see them from there.
The bottom side names every terminal pin.

## Case

Three printed parts, built in build123d from the board's own dimensions ([`case/case.py`](case/case.py)):

- **Cover:** the front shell, with a pillar at each of the board's four mounting holes. The plugs
  stick out through openings in the bottom wall, USB-C and the Qwiic port through the top; the wall is solid below the
  board, so nothing slips in under it to the mains solder joints. There are vents in the top wall
  beside the USB-C and in the right wall above the relays (none beside mains parts). The front face is closed; a short tube carries the status LED's light
  to a 0.6 mm thin window. The front face names every opening and its pins (MAINS L N, RELAY 1 and 2
  COM NO, CT1 and CT2 + −, USB, QWIIC), cut 0.4 mm deep. The Qwiic opening is 13 × 8 mm: the small plug ends
  inside the wall, so the opening leaves 3 mm each side to grip it, and it is too low for a finger.
- **Base:** the sealed back plate. Its only openings are the four screw holes, so nothing pushed in
  from the back (a screwdriver, the metal DIN rail) can reach the mains parts behind the board. A
  standoff rises from it to each mounting hole, and a rim locates it inside the cover's walls. A
  0.4 mm deep pocket in its back gives the clip's moving parts room to slide.
- **DIN clip:** screwed under the base, it clips the case onto a TS35 rail.
  - **Hook (top):** 65 mm long, with a 3.5 mm thick wall and a 2.2 mm thick lip that reaches 2 mm
    over the rail's flange. Five ribs behind the wall stop it bending back off the rail.
  - **Latch (bottom):** a 20 mm wide block with the same wall and lip. It rides on four 1.2 mm spring
    beams cut into the clip plate, which bend in the plate's own plane, so the block slides down
    2.4 mm to clear the flange while the beams stay under half of PETG's yield strain. The beams are
    anchored clear of the screw at the left (it sits in their band), so the latch is a little right
    of centre. The
    lip's underside is a 45° ramp: rock the case onto the rail and it snaps on. Two straps printed
    over the pull tab's channel stop the latch twisting away from the case.
  - **To take it off the rail,** pull the tab at the clip's bottom edge down: put a screwdriver in
    its slot and lever.

**Four screws hold everything:** M3 × 16 countersunk, from the back through the clip, the base, its
standoff and the board, self-tapping into 2.8 mm pilot holes in the cover's pillars (no inserts). The
board is clamped between the standoffs and the pillars, and the heads sit flush in the clip. To
assemble, lay the cover face down, drop the board in (components down) onto the pillars, put the
base and then the clip on, and fit the four screws. Nothing inside the walls stands between the
board and the open back, and a test checks that.

| Exploded | Board in the cover, from the back |
|---|---|
| ![Exploded](docs/img/case_exploded.png) | ![Board in the cover](docs/img/case_inside.png) |

| On a DIN rail, from the back | The DIN clip: ribbed hook (top), latch on its spring beams and pull tab (bottom) |
|---|---|
| ![On a DIN rail](docs/img/case_din.png) | ![DIN clip](docs/img/case_clip.png) |

Print in PETG (the latch has to flex): 0.2 mm layers, 3 walls. Print the cover on its front face and
the base on its back face (standoffs up), both without supports. Print the clip on its flat face (hook
and latch up), so the spring beams bend along the layers, with supports under the hook's and latch's
2 mm lips only: not under the two straps over the pull tab, which bridge. STEP files and print-oriented STL files are in
[`case/out`](case/out).

## Safety

**This board connects to mains voltage.** Build, wire and install it only if you are competent to do
mains work, and power it only inside its case, inside a closed plastic enclosure.

- The HLK-PM01, the ZMPT107-1 and the relays are the isolation barrier. Everywhere else, mains is
  kept 6.5 mm from the low-voltage side.
- USB-C, the CT terminal and the GPIO header are on the isolated side. Even so, **don't connect USB
  to a board that is wired to mains**: flash it on the bench first, then update it over Wi-Fi.
- There is no protective earth. The board and case are for a plastic enclosure only.
- The relays are rated 16 A. Keep loads at or below 10 A, and use an external contactor above that.
- No metal near the board: the warning on the bottom silkscreen says so too.

## Wiring

All the terminals unplug: wire each plug first, then plug it in. Looking at the component side, left
to right:

| Terminal | Pins | Use |
|---|---|---|
| J4 (3.81 mm) | CT1+, CT1−, CT2+, CT2− | the two CT clamps (low voltage) |
| J1 (5.08 mm) | L, N/L2 | supply and voltage reference |
| J2 (5.08 mm) | COM, NO | relay 1, dry contact |
| J3 (5.08 mm) | COM, NO | relay 2, dry contact |

- **120 V line–neutral:** line to `L`, neutral to `N/L2`.
- **240 V leg–leg (US split phase):** L1 to `L`, L2 to `N/L2`. Both inputs are fused, so either
  way works. The voltage reading is then the leg–leg voltage.
- **Relays:** dry contacts, so they switch whatever you wire through them, for example `L` → COM and
  NO → load. A contactor coil is wired the same way.
- **CTs:** clamp each CT around one conductor. If a channel reads negative power, turn the clamp
  around or swap its two wires.

## Firmware

[`firmware/c6-energy-relay.yaml`](firmware/c6-energy-relay.yaml) is a starter ESPHome config. It has:

- the BL0939 sensors: voltage, current, power and energy;
- `Relay 1` and `Relay 2` switches, always off after a reboot or power cut, with the coil hold above
  (`coil_hold: "100%"` turns it off);
- the status LED;
- an I2C bus on the Qwiic port (GPIO2 / GPIO3), which scans for devices at boot; add your sensor to it;
- the BOOT button, which toggles relay 1. It's on the board, inside the closed case, so it's for the
  bench.

Add a `secrets.yaml` with `wifi_ssid`, `wifi_password`, `api_key`, `ota_password` and
`ap_password`. Flash it over USB-C (native USB, no buttons needed), then update over Wi-Fi from then
on. Logs go to the USB port, which leaves the ESP32's UART to the BL0939.

| GPIO | Use | GPIO | Use |
|---|---|---|---|
| 1 | UART TX to BL0939 RX | 6 | relay 1 |
| 0 | UART RX from BL0939 TX | 12 | relay 2 |
| 13 / 14 | USB D− / D+ | 5 | status LED |
| 28 | BOOT button (strapping) | 27 | 10 kΩ pull-up (strapping, on the header) |
| 2 / 3 | Qwiic SDA / SCL (strapping, held high by the pull-ups) | | |

**Calibration:** with a known resistive load and a meter, set each `*_cal` substitution to
(its starting value × meter reading ÷ reported value). The energy sensors use the power factors.
The starting values convert ESPHome's BL0939 scaling (a 1 mΩ shunt and a 0.51 kΩ / 1.95 MΩ divider) to
this board: current × 3.33 (CTs give 0.3 mV/A), voltage × 2.05 (0.1275 mV/V) and power × 6.84.

## Ordering at JLCPCB

The order files are in [`hw/out/jlc`](hw/out/jlc):

1. **PCB:** upload `gerbers.zip`: 2 layers, 1.6 mm, 1 oz, HASL (with lead or lead-free), any colour. JLC's
   default finish is now OSP, which rules out Economic PCBA.
2. **Assembly:** choose **Economic PCBA**, top side, and upload `bom.csv` and `cpl.csv`. The ESP32-C5
   module has castellated edge pads, so it needs no X-ray inspection; JLC hand-solders the through-hole
   parts.
3. **Check the placement preview before paying.** Every part should sit on its footprint and point
   the right way. Pay most attention to:
   - the ESP32-C5 module (its antenna end at the top board edge) and USB-C;
   - the Qwiic socket (J7): its opening must face the top board edge;
   - the BL0939;
   - the LDO (U3): its wide tab is pin 2, on the 3.3 V copper area;
   - the diodes and transistors, and the polymer capacitor (C14): its + side faces the HLK-PM01;
   - both buttons. A button turned 90° holds EN or BOOT low.

   All 33 parts were checked this way in JLC's preview on 2026-11-24, against the pad positions in the
   board file. The board has been laid out again since (same parts and footprints), and JLC changes its
   part drawings now and then, so look again before paying.
4. **Plugs:** add the loose plugs from `plugs.csv` to the same order as parts: 3 × DB2EK-5.08-2P and
   1 × WJ15EDGK-3.81-4P per board.

Cost estimate from [`cost.md`](hw/out/jlc/cost.md). Part prices are live JLC prices from 2026-11-24;
the fees, PCB and shipping figures are estimates, so check the real quote.

| Boards | Total | Per board |
|---|---|---|
| 10 | $200 | $20.04 |
| 20 | $332 | $16.62 |
| 30 | $441 | $14.70 |
| 50 | $657 | $13.14 |
| 100 | $1191 | $11.91 |

JLC's own quote on 2026-11-23 for 10 boards with this module (Economic PCBA, top side) was **$163.49**
before shipping, duties and the loose plugs: $5.00 for the boards and $158.49 for assembly, of which
$108.19 is parts, $27.81 Extended-part fees and $9.79 setup and stencil. That quote still had the
earlier LDO, an Extended part; the AMS1117 is a Basic part. With Standard PCBA, 30 boards with the
earlier ESP32-C6-MINI-1 came to $469.65, including a $24.90 X-ray inspection for that module's
hidden pads.

The most expensive parts per board, at 30 boards:

| Part | Cost per board |
|---|---|
| ESPC5-32-H4 (ESP32-C5) | $2.80 |
| HLK-PM01 | $2.17 |
| two relays | $1.88 |
| BL0939 | $0.68 |
| ZMPT107-1 | $0.41 |

The estimate counts $3 per order for each of the 13 Extended parts. The passives are JLC Basic parts
wherever one fits (the 100 kΩ divider, the 51 Ω load, the 47 nF filter capacitors, the 10 µF capacitors);
the 0.3 Ω burdens and the 220 µF polymer capacitor have no Basic equivalent.

## Building it from source

Everything is generated by scripts; edit the scripts, not the KiCad files. `KPY` is KiCad 10's own
Python (`"C:\Program Files\KiCad\10.0\bin\python.exe"` on Windows); the other steps use a normal
Python 3.11+ with `pip install -r requirements-dev.txt` (build123d, pytest) plus PyMuPDF, Pillow and
VTK for the images.

| Step | Command |
|---|---|
| symbols, footprints, 3D bodies | `KPY hw/gen_lib.py`, then `python -m hw.gen_3d` |
| schematic and project | `python -m hw.gen_sch` |
| board: placement, rules, zones, silkscreen | `KPY hw/gen_pcb.py` |
| tracks and zone fill | `KPY hw/route.py` |
| board STEP | `kicad-cli pcb export step --drill-origin --subst-models -o hw/out/board.step hw/c6-energy-relay.kicad_pcb` |
| schematic PDF | `kicad-cli sch export pdf -o hw/out/schematic.pdf hw/c6-energy-relay.kicad_sch` |
| JLC files and cost sheet | `KPY hw/export_jlc.py` |
| case | `python case/case.py` |
| README images | `python docs/make_images.py` and `python docs/block_diagram.py` |
| tests | `python -m pytest` |

The tests run:

- KiCad's ERC, and its DRC with the creepage rules and schematic parity;
- the antenna keep-out and the mounting-hole spacing;
- a silkscreen check;
- the JLC files against the board;
- live JLC stock for 30 boards;
- the case fit: the board's path in, board, plugs, screws, openings, the sealed back, flat
  printing and the DIN clip (including the latch's travel and spring strain);
- the ESP32 pins in the firmware against the design;
- ESPHome validating the config, through `esphome` on the PATH, `$ESPHOME_CMD` or `esphome-wsl`
  inside WSL.

The circuit lives in [`hw/design.py`](hw/design.py) and the parts, with their LCSC numbers, in
[`hw/parts.py`](hw/parts.py). The schematic, board, BOM and firmware pin check all read from those
two files.

| Folder | Contents |
|---|---|
| `hw/` | the generators, KiCad project, local symbol and footprint library (`lib/`) |
| `hw/out/` | schematic PDF, board STEP, JLC files |
| `case/` | the case script and its STEP/STL output |
| `firmware/` | ESPHome config |
| `docs/` | the scripts that make the README images, and the images |
| `tests/` | pytest checks for all of the above |

## Licence

- **Hardware** (the circuit board and the case: everything in `hw/` and `case/`, including the scripts
  that generate them, and the images): [CERN-OHL-P-2.0](LICENSES/CERN-OHL-P-2.0.txt), the permissive
  CERN Open Hardware Licence.
- **Software** (the ESPHome config, the tests and the image scripts): [MIT](LICENSES/MIT.txt).

See [`LICENSE`](LICENSE). Both come with no warranty. This board connects to mains, so building,
installing and using it is at your own risk.
