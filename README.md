# Smart golf grip — Seeed Studio XIAO ESP32C3

The firmware scans the existing 10 × 7 tactile sensor through two multiplexers
and reads an LSM6DSOX IMU. USB-C carries the data to `heatmap.py`.

These directions assume **two CD74HC4067 / 74HC4067 16-channel breakout boards**
and a passive resistive tactile matrix, inferred from the original sketch. Check
the markings on your mux chips before wiring. The **74HCT4067** requires a higher
supply voltage and is unsuitable for this 3.3 V wiring. See the
[TI datasheet](https://www.ti.com/lit/ds/symlink/cd74hc4067.pdf).

## Why the connections change

The XIAO has **14 edge pins: 11 GPIO + 5V + 3V3 + GND**. The original sketch
used 12 GPIO: eight mux select lines, one sensor drive, one analog input, and
two I²C lines. A breadboard distributes connections but adds no GPIO.

The new wiring needs **10 GPIO**:

- Mux A's SIG was always driven HIGH; connect it directly to **3V3** instead.
- Mux B only uses channels 0–6; hold its **S3 at GND** and control only S0–S2.
- D0 stays unused. D1 reads the sensor; seven GPIO select mux channels; two run I²C.

The board labels and GPIO mapping below follow
[Seeed's XIAO ESP32C3 pinout](https://wiki.seeedstudio.com/XIAO_ESP32C3_Getting_Started/).

## Wiring

Disconnect USB and any battery before rewiring. For initial testing, power the
XIAO through USB-C and use its **3V3** and **GND** pins as breadboard rails.
Connect every module to these same rails. **Leave the XIAO's 5V pin unused.**
Bridge split breadboard rails where needed; opposite-side rails are usually
separate. Each connected group of five breadboard holes is one electrical node.

### Battery: PKCELL LP801735, 3.7 V, 400 mAh

This build uses the PKCELL battery covered by the user-supplied
[Adafruit-hosted 2016 datasheet](https://cdn-shop.adafruit.com/product-files/3898/3898_specsheet_LP801735_400mAh_3.7V_20161129.pdf).
The XIAO accepts a single-cell 3.7 V lithium battery through its **underside battery +/−
pads**, separate from the 14 edge pins. Use a mating battery connector with
leads soldered to those pads, checking polarity against
[Seeed's battery connection diagram](https://files.seeedstudio.com/wiki/XIAO_WiFi/battery_connect.png).
Do not solder directly to the pouch cell. The power path is:

```text
Battery + ── XIAO battery + pad
Battery − ── XIAO battery − pad

XIAO 3V3 ── shared 3.3 V rail / wire branches ── muxes, IMU, Mux A SIG
XIAO GND ── shared ground rail / wire branches
```

The XIAO regulates the battery voltage for the circuit. **Do not connect the
battery directly to the 3V3 rail, the muxes, or a GPIO.** A full cell reaches
4.2 V. A breadboard or prototyping board is not needed electrically; soldered,
insulated wire branches can provide the shared power connections.

**The published charging ratings are compatible.** Page 2 of the supplied
datasheet lists a 4.2 V charge cutoff, 200 mA standard charging current (0.5C),
and **400 mA maximum charging current (1C)**. Seeed specifies approximately
**380 mA** charging current for the XIAO ESP32C3: faster than the cell's standard
charge rate, but below its stated maximum. An additional charging board is not
required for this battery/board combination on these published specifications.

Connect the battery through a matching connector/pigtail to the underside
battery pads, observing the marked +/− polarity. USB-C powers the XIAO's
built-in charger; Seeed permits USB and a battery to be connected together.
The cell's specified charging temperature is **0–45°C**. These directions apply
to the supplied datasheet, not every battery sharing the LP801735 model name.

Sources: [Seeed specifications and battery usage](https://wiki.seeedstudio.com/XIAO_ESP32C3_Getting_Started/),
[supplied PKCELL specification, page 2](https://cdn-shop.adafruit.com/product-files/3898/3898_specsheet_LP801735_400mAh_3.7V_20161129.pdf).

The current firmware sends data over **USB only**. A battery can power the grip,
but battery-only operation will not deliver heatmap data to the computer;
untethered streaming needs a future BLE or Wi-Fi transport change.

### Board orientation

Component side facing you, USB-C at the top. This shows the XIAO edge pins;
use the labels on each mux breakout rather than assuming a matching pin order.

```text
                          USB-C
                    ┌───────────────┐
 unused       D0/2  │               │ 5V       unused
 sensor ADC   D1/3  │     XIAO      │ GND      ground rail
 Mux A S0     D2/4  │   ESP32C3     │ 3V3      3.3 V rail
 Mux A S1     D3/5  │               │ D10/10   Mux B S2
 IMU SDA      D4/6  │               │ D9/9     Mux B S1
 IMU SCL      D5/7  │               │ D8/8     Mux B S0
 Mux A S2     D6/21 │               │ D7/20    Mux A S3
                    └───────────────┘
                    label/GPIO number
```

### Move the old ESP32 wires

“Old” numbers are GPIO numbers from the original `tactile_stream.ino`.
**D labels and GPIO numbers differ**: for example, XIAO D1 is GPIO3.

| Connection | Old ESP32 GPIO | New XIAO connection | New GPIO |
| --- | --- | --- | --- |
| Mux A S0 | 18 | D2 | 4 |
| Mux A S1 | 19 | D3 | 5 |
| Mux A S2 | 21 | D6 | 21 |
| Mux A S3 | 22 | D7 | 20 |
| Mux A SIG / COM | 13 | **3V3 rail** | — |
| Mux B S0 | 23 | D8 | 8 |
| Mux B S1 | 25 | D9 | 9 |
| Mux B S2 | 26 | D10 | 10 |
| Mux B S3 | 27 | **GND rail** | — |
| Mux B SIG / COM | 34 | **4.7 kΩ resistor → D1**, as below | 3 |
| IMU SDA | 33 | D4 | 6 |
| IMU SCL | 32 | D5 | 7 |

Keep the two mux select buses separate. Do not connect their S0–S2 pins together:
the firmware selects the row and column independently.

### Power, enable, and sensor leads

| Module connection | Connect to |
| --- | --- |
| Both mux VCC pins | 3V3 rail |
| Both mux GND pins | GND rail |
| Both mux EN / E pins | GND rail; LOW enables the switches |
| Mux A SIG / COM | 3V3 rail |
| Mux B S3 | GND rail |
| Sensor A0–A9, the ten-lead side | Mux A channels C0–C9, respectively |
| Sensor B0–B6, the seven-lead side | Mux B channels C0–C6, respectively |
| Unused mux channels | Leave unconnected |
| Adafruit LSM6DSOX VIN | 3V3 rail |
| LSM6DSOX GND | GND rail |
| LSM6DSOX SDA / SCL | XIAO D4 / D5 |

Channel labels may read `C0`, `CH0`, or `I0`. “Sensor A0” means a sensor lead,
not the XIAO's analog A0 pin. The mux enable and select behavior is documented in
the [TI truth table](https://www.ti.com/lit/ds/symlink/cd74hc4067.pdf).

For the Adafruit IMU breakout, use **VIN**, not the regulator output `3Vo`.
Its standard I²C setup can leave CS and the address pin at their default levels;
the firmware tries both 0x6A and 0x6B. If using a different LSM6DSOX module,
follow its power labels, hold CS HIGH for I²C, and ensure SDA/SCL pull-ups go to
3.3 V. INT1/INT2 are unused. See
[Adafruit's pinout guide](https://learn.adafruit.com/lsm6dsox-and-ism330dhc-6-dof-imu/pinouts).

### Analog readout: two resistors

Use this exact network for the documented build. If the old setup has a
pull-down resistor, remove or relocate it so the final circuit matches this
diagram; do not leave an extra resistor from Mux B SIG directly to ground.

```text
 3V3 ── Mux A SIG
           │ selected row channel
       sensor A lead
           │
     pressure-sensitive resistance
           │
       sensor B lead
           │ selected column channel
       Mux B SIG ──[ 4.7 kΩ ]──┬── XIAO D1 / GPIO3
                              │
                           [ 10 kΩ ]
                              │
                             GND
```

The 10 kΩ resistor provides a defined LOW reading with no conductive sensor
path. Pressure should lower the sensor resistance and raise the reading. The
4.7 kΩ resistor also limits the maximum ADC voltage to about
`3.3 × 10 / (4.7 + 10) = 2.24 V`, ignoring mux and sensor resistance.

This matters because the ESP32-C3 ADC's documented range at 11 dB attenuation
is about **0–2.5 V**, even though the board uses 3.3 V logic. The firmware sets
that attenuation and retains 12-bit readings (0–4095). See
[Espressif's ADC reference](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/adc.html).
With this resistor network, even a strong press need not reach 4095.

D8/GPIO8 and D9/GPIO9 are boot strapping pins. Connect them only to the mux
select inputs shown; do not add pull-downs or other loads. Release the BOOT
button during normal operation. If attached hardware prevents startup,
disconnect those two select wires and check the mux power and connections.
D0/GPIO2 is another strapping pin and is deliberately unused. See
[Seeed's strapping pin notes](https://wiki.seeedstudio.com/XIAO_ESP32C3_Getting_Started/#strapping-pins).

## Upload the firmware

1. In Arduino IDE's Boards Manager, install **esp32 by Espressif Systems**.
   This project targets the **XIAO_ESP32C3** board definition; the local core
   inspected during this migration was 3.3.12.
2. Install **Adafruit LSM6DS** in Library Manager, including its dependencies:
   **Adafruit BusIO** and **Adafruit Unified Sensor**.
3. Open `tactile_stream.ino`. Arduino expects it in a folder named
   `tactile_stream`; accept its offer to create/move it into that folder if
   prompted. `heatmap.py` stays in this project directory.
4. Select **Tools → Board → esp32 → XIAO_ESP32C3** and
   **USB CDC On Boot → Enabled**. Select its USB port and upload.
5. If it will not upload, hold **BOOT**, press and release **RESET**, then
   release BOOT. Select the USB port again if it changed, and retry.
6. Open Serial Monitor at **460800**. Expect `F,` lines with 70 numbers,
   `I,` lines with six IMU values, and `#` status messages. If the IMU is absent,
   tactile scanning still runs. Reset after opening the monitor to see startup
   messages if needed, then **close Serial Monitor** before running Python.

The board selection and USB setup are described in
[Seeed's getting started guide](https://wiki.seeedstudio.com/XIAO_ESP32C3_Getting_Started/).
The code uses native USB `Serial`; D6 and D7 are mux control pins, so do not
attach a UART adapter to them.

## Run the heatmap

From this project directory:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python heatmap.py
```

Auto-detection supports the XIAO's native USB port on macOS (`cu.usbmodem*`),
Linux (`ttyACM*`), and Windows (Espressif/Seeed USB vendor ID). Legacy ESP32
USB-to-UART names still work. If several possible boards are connected, specify
one explicitly. List ports with `python -m serial.tools.list_ports -v`.

```sh
python heatmap.py --port /dev/cu.usbmodemXXXX  # macOS: replace with actual port
python heatmap.py --port /dev/ttyACM0         # Linux example
python heatmap.py --port COM3                # Windows example
python heatmap.py --demo                     # exercise UI without hardware
```

On Windows, activate the environment with `.venv\Scripts\activate` instead.
Leave the grip untouched during initial calibration. Press **c** to recalibrate,
**r** to inspect raw values, **n** for cell numbers, and **+ / -** for sensitivity.
The displayed percentage is a relative signal above baseline, not calibrated
force or physical pressure.

## First hardware check

1. Check both breadboard power rails and all grounds. Confirm both EN pins
   and **only Mux B's S3** are grounded; Mux A's S3 goes to D7.
2. With a multimeter, check approximately 3.3 V between the rails and confirm
   the ADC readout is wired through the two resistors above.
3. Run the heatmap, let it calibrate, then press different sensor locations.
   Raw readings should rise under pressure. Constant/noisy readings suggest
   a missing pull-down, disabled mux, or incorrect SIG/select wiring.
4. If rows A8/A9 fail, check Mux A S3 → D7. If columns fail, check Mux B
   S3 → GND and the order S0 → D8, S1 → D9, S2 → D10.
5. Tilt the IMU and look for changing acceleration values. An IMU warning
   calls for checking VIN, GND, SDA/D4, SCL/D5, and its I²C mode.
6. If the map is mirrored or upside down, change `B0_ON_RIGHT` or `A0_AT_TOP`
   in `heatmap.py` to match the physical lead orientation.

The scan format is unchanged: `F,` followed by 70 row-major readings, then
optional `I,ax,ay,az,gx,gy,gz` in m/s² and rad/s. This migration preserves the
existing passive-matrix scan method; it does not correct matrix ghosting when
multiple points conduct at once. Final noise, settling time, resistor tuning,
and IMU behavior need verification on the assembled grip.

## Validation performed

The updated port detection passed eight scenarios covering native USB on
macOS/Linux/Windows, legacy serial adapters, and ambiguous or missing boards.
A pseudo-terminal stream verified the 70-cell order, IMU parsing, and malformed
frame handling. The demo heatmap also rendered successfully.

The GPIO, mux scan, ADC, USB serial, and I²C setup compiled against the installed
XIAO ESP32C3 core 3.3.12 in a temporary copy with IMU calls removed. **The complete
firmware build remains unverified**: Adafruit LSM6DS, BusIO, and Unified Sensor
are missing locally, and library downloads were unavailable. Install those
libraries and Verify the complete sketch before uploading. No physical hardware
was tested or flashed during this migration.
