#!/usr/bin/env python3
"""
Live trapezoid heatmap for the 10 x 7 tactile golf-grip sensor
(Seeed Studio XIAO ESP32C3 + 2 muxes + LSM6DSOX IMU).

Upload tactile_stream.ino to the XIAO first, CLOSE the Arduino Serial Monitor,
then run:
    python3 heatmap.py              (finds the XIAO/ESP32 port automatically)
    python3 heatmap.py --port /dev/cu.usbmodemXXXX
    python3 heatmap.py --demo       (fake data, no hardware needed)

Keys (click the heatmap window first):
    c   recalibrate (don't touch the sensor for a second)
    r   switch between pressure % and raw readings
    n   show / hide numbers on each cell
    +/- make the colors more / less sensitive
    q   quit
"""
import argparse
import sys
import threading
import time

import numpy as np

# ---------------- Sensor layout: edit these to match your build ----------------
LONG_LEADS = 10       # Mux A leads (A0-A9), running along the length of the grip
WIDE_LEADS = 7        # Mux B leads (B0-B6), running around the grip
A0_AT_TOP = True      # True if lead A0 is at the wide (butt) end of the grip
B0_ON_RIGHT = True    # True if lead B0 is on the right edge as you look at the sensor
# Physical size of the sensor (any unit, only the proportions matter).
# Measure yours and replace these: top = wide end, bottom = narrow end.
TOP_WIDTH = 80.0
BOTTOM_WIDTH = 62.0
LENGTH = 150.0
# -------------------------------------------------------------------------------

BAUD = 460800              # must match tactile_stream.ino
CALIB_FRAMES = 20
ADC_MAX = 4095
N = LONG_LEADS * WIDE_LEADS


def find_port():
    from serial.tools import list_ports
    ports = list(list_ports.comports())
    # XIAO native USB can report Espressif's or Seeed's vendor ID. This also
    # detects Windows COM ports, where the device name has no USB hint.
    preferred = [p for p in ports if p.vid in (0x303A, 0x2886)]
    candidates = preferred or [
        p for p in ports if any(k in p.device for k in (
            "usbmodem", "ttyACM", "usbserial", "wchusbserial", "SLAB_USBtoUART", "ttyUSB"
        ))
    ]
    if len(candidates) > 1:
        choices = "\n".join(f"  {p.device}: {p.description}" for p in candidates)
        sys.exit(f"Multiple possible XIAO/ESP32 ports found:\n{choices}\n"
                 "Select one with --port PORT.")
    return candidates[0].device if candidates else None


class Reader(threading.Thread):
    """Reads lines from the ESP32 in the background and keeps the latest frame."""

    def __init__(self, port=None, demo=False):
        super().__init__(daemon=True)
        self.port, self.demo = port, demo
        self.lock = threading.Lock()
        self.frame = None          # raw readings, shape (LONG_LEADS, WIDE_LEADS), indexed [a][b]
        self.imu = None            # [ax, ay, az, gx, gy, gz]
        self.count = 0
        self.error = None
        self.warned = False

    def run(self):
        self._run_demo() if self.demo else self._run_serial()

    def _run_serial(self):
        import serial
        try:
            ser = serial.Serial(self.port, BAUD, timeout=1)
        except Exception as e:
            self.error = f"{e}\nIs the Arduino Serial Monitor still open? Close it and try again."
            return
        while True:
            try:
                line = ser.readline().decode("ascii", "ignore").strip()
            except Exception as e:
                self.error = f"Lost connection: {e}"
                return
            if line.startswith("F,"):
                parts = line[2:].split(",")
                if len(parts) != N:
                    if not self.warned and len(parts) > 10:
                        print(f"Got {len(parts)} readings per scan but expected {N}. "
                              f"Check ROWS/COLS in tactile_stream.ino match LONG_LEADS/WIDE_LEADS here.")
                        self.warned = True
                    continue
                try:
                    arr = np.array(parts, dtype=float).reshape(LONG_LEADS, WIDE_LEADS)
                except ValueError:
                    continue
                with self.lock:
                    self.frame, self.count = arr, self.count + 1
            elif line.startswith("I,"):
                try:
                    v = [float(x) for x in line[2:].split(",")]
                except ValueError:
                    continue
                if len(v) == 6:
                    with self.lock:
                        self.imu = v
            elif line.startswith("#"):
                print("ESP32:", line[1:].strip())

    def _run_demo(self):
        rng = np.random.default_rng(0)
        a = np.arange(LONG_LEADS)[:, None]
        b = np.arange(WIDE_LEADS)[None, :]
        base = 1800 + 400 * rng.random((LONG_LEADS, 1)) + 400 * rng.random((1, WIDE_LEADS))
        t0 = time.time()
        while True:
            t = time.time() - t0
            # two "fingers" moving around
            p = np.zeros((LONG_LEADS, WIDE_LEADS))
            for ph, amp in ((0, 2000), (2.0, 1400)):
                ca = 4.5 + 4 * np.sin(t * 0.6 + ph)
                cb = 3 + 2.5 * np.sin(t * 0.9 + ph)
                p += amp * np.exp(-((a - ca) ** 2 + (b - cb) ** 2) / 1.5)
            noise = rng.normal(0, 25, (LONG_LEADS, WIDE_LEADS))
            frame = np.clip(base + p * (t > 1.5) + noise, 0, ADC_MAX)
            with self.lock:
                self.frame, self.count = frame, self.count + 1
                self.imu = [0.1, 0.0, 9.8, 0.0, 0.0, 0.0]
            time.sleep(0.03)


def build_cells():
    """Trapezoid cells: returns list of 4-corner polygons in display order (row r, col c)."""
    def width(y):
        return TOP_WIDTH + (BOTTOM_WIDTH - TOP_WIDTH) * y / LENGTH

    def x(y, c):
        w = width(y)
        return -w / 2 + c * w / WIDE_LEADS

    cells, centers = [], []
    for r in range(LONG_LEADS):
        y0, y1 = r * LENGTH / LONG_LEADS, (r + 1) * LENGTH / LONG_LEADS
        for c in range(WIDE_LEADS):
            poly = [(x(y0, c), y0), (x(y0, c + 1), y0), (x(y1, c + 1), y1), (x(y1, c), y1)]
            cells.append(poly)
            centers.append((np.mean([p[0] for p in poly]), (y0 + y1) / 2))
    return cells, centers, width


def to_display(m):
    """m[a][b] -> d[r][c]: r = 0 at the top (wide end), c = 0 on the left."""
    d = m if A0_AT_TOP else m[::-1, :]
    return d[:, ::-1] if B0_ON_RIGHT else d


def main():
    ap = argparse.ArgumentParser(description="Live tactile grip heatmap")
    ap.add_argument("--port", help="serial port (default: auto-detect)")
    ap.add_argument("--demo", action="store_true", help="use fake data, no hardware")
    ap.add_argument("--smooth", type=float, default=0.4,
                    help="0 = no smoothing, 0.9 = very smooth (default 0.4)")
    ap.add_argument("--snapshot", help=argparse.SUPPRESS)  # save one PNG and exit (testing)
    args = ap.parse_args()

    port = args.port
    if not args.demo and not port:
        port = find_port()
        if not port:
            sys.exit("Couldn't find the XIAO/ESP32. Is it plugged in? "
                     "Use --port PORT (e.g. /dev/cu.usbmodemXXXX, /dev/ttyACM0, or COM3).")
    print("Demo mode" if args.demo else f"Reading from {port} at {BAUD} baud")

    import matplotlib
    if args.snapshot:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation
    from matplotlib.collections import PolyCollection

    for k in list(plt.rcParams):
        if k.startswith("keymap.") and k != "keymap.quit":
            plt.rcParams[k] = []
    plt.rcParams["keymap.quit"] = ["q", "cmd+w", "ctrl+w"]

    reader = Reader(port, args.demo)
    reader.start()

    st = {"base": None, "calib": [], "calibrating": True, "last": 0,
          "smooth": None, "raw": False, "numbers": False, "gain": 100.0}

    # ---- Figure ----
    cells, centers, width = build_cells()
    fig, ax = plt.subplots(figsize=(6.2, 8.4))
    fig.subplots_adjust(left=0.06, right=0.84, top=0.88, bottom=0.13)
    pc = PolyCollection(cells, cmap="inferno", edgecolors="0.3", linewidths=0.8)
    pc.set_array(np.zeros(N))
    pc.set_clim(0, 100)
    ax.add_collection(pc)
    pad = TOP_WIDTH * 0.18
    ax.set_xlim(-TOP_WIDTH / 2 - pad, TOP_WIDTH / 2 + pad * 0.4)
    ax.set_ylim(LENGTH + LENGTH * 0.06, -LENGTH * 0.09)   # y grows downward
    ax.set_aspect("equal")
    ax.axis("off")

    # Lead labels: A along the left edge, B across the top
    a_order = list(range(LONG_LEADS)) if A0_AT_TOP else list(range(LONG_LEADS - 1, -1, -1))
    b_order = list(range(WIDE_LEADS - 1, -1, -1)) if B0_ON_RIGHT else list(range(WIDE_LEADS))
    for r, a in enumerate(a_order):
        y = (r + 0.5) * LENGTH / LONG_LEADS
        ax.text(-width(y) / 2 - 2, y, f"A{a}", ha="right", va="center", fontsize=8, color="0.35")
    for c, b in enumerate(b_order):
        x = -TOP_WIDTH / 2 + (c + 0.5) * TOP_WIDTH / WIDE_LEADS
        ax.text(x, -2, f"B{b}", ha="center", va="bottom", fontsize=8, color="0.35")
    ax.text(0, -LENGTH * 0.065, "butt end (top of grip)", ha="center", va="bottom", fontsize=8, color="0.5")
    ax.text(0, LENGTH + 2, "toward clubhead", ha="center", va="top", fontsize=8, color="0.5")

    cbar = fig.colorbar(pc, ax=ax, fraction=0.05, pad=0.02)
    title = fig.suptitle("Grip pressure", fontsize=13, fontweight="bold")
    texts = [ax.text(cx, cy, "", ha="center", va="center", fontsize=7) for cx, cy in centers]
    status = fig.text(0.04, 0.065, "", fontsize=9, family="monospace")
    fig.text(0.04, 0.02, "c recalibrate · r raw/% · n numbers · +/- sensitivity · q quit",
             fontsize=8, color="0.4")

    def update(_=None):
        if reader.error:
            status.set_text(reader.error)
            return
        with reader.lock:
            frame = None if reader.frame is None else reader.frame.copy()
            imu, count = reader.imu, reader.count
        if frame is None:
            status.set_text("Waiting for data from the ESP32...")
            return
        new = count != st["last"]
        st["last"] = count

        s = st["smooth"]
        st["smooth"] = frame if s is None else args.smooth * s + (1 - args.smooth) * frame
        f = st["smooth"]

        if st["calibrating"]:
            if new:
                st["calib"].append(frame)
            title.set_text(f"Calibrating — don't touch ({len(st['calib'])}/{CALIB_FRAMES})")
            if len(st["calib"]) >= CALIB_FRAMES:
                st["base"] = np.mean(st["calib"], axis=0)
                st["calib"], st["calibrating"] = [], False
            if st["base"] is None:
                return

        if st["raw"]:
            data, vmax, unit = f, ADC_MAX, ""
            cbar.set_label("Raw reading (0–4095)")
        else:
            base = st["base"]
            data = np.clip((f - base) / np.maximum(1, ADC_MAX - base) * 100, 0, 100)
            vmax, unit = st["gain"], "%"
            cbar.set_label("Pressure above baseline (%)")
        if not st["calibrating"]:
            title.set_text("Raw readings" if st["raw"] else "Grip pressure")

        disp = to_display(data).ravel()
        pc.set_array(disp)
        pc.set_clim(0, vmax)
        for t, v in zip(texts, disp):
            if st["numbers"]:
                t.set_text(f"{v:.0f}")
                t.set_color("black" if v > 0.6 * vmax else "white")
            else:
                t.set_text("")

        pa, pb = np.unravel_index(np.argmax(data), data.shape)
        line = f"Peak {data[pa, pb]:.0f}{unit} at A{pa}, B{pb}"
        if imu:
            line += (f"\nAccel m/s²  x{imu[0]:6.2f}  y{imu[1]:6.2f}  z{imu[2]:6.2f}"
                     f"   Gyro rad/s  x{imu[3]:5.2f}  y{imu[4]:5.2f}  z{imu[5]:5.2f}")
        status.set_text(line)

    def on_key(e):
        if e.key == "c":
            st["calibrating"], st["calib"] = True, []
        elif e.key == "r":
            st["raw"] = not st["raw"]
        elif e.key == "n":
            st["numbers"] = not st["numbers"]
        elif e.key in ("+", "="):
            st["gain"] = max(5.0, st["gain"] * 0.7)
        elif e.key in ("-", "_"):
            st["gain"] = min(100.0, st["gain"] / 0.7)

    fig.canvas.mpl_connect("key_press_event", on_key)

    if args.snapshot:
        end = time.time() + 4
        while time.time() < end:
            update()
            time.sleep(0.03)
        st["numbers"] = True
        update()
        fig.savefig(args.snapshot, dpi=90)
        return

    _anim = FuncAnimation(fig, update, interval=40, cache_frame_data=False)
    plt.show()


if __name__ == "__main__":
    main()
