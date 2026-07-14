#!/usr/bin/env python3
"""
Modular Resonance Screensaver
Hypnotic visualization of modular arithmetic with evolving multipliers
Cardioids (×2), Nephroids (×3), Stars (primes)!
Random parameter reset every 30 minutes - Pure Tkinter
"""

import math
import random
import tkinter as tk
from datetime import datetime

# === CONFIG ===
CONFIG = {
    "fps": 30,
    "switch_interval": 30 * 60 * 1000,  # 30 minutes - randomize parameters
    "num_stars": 30,
    "star_speed": 0.2,
    "star_size": 2,
    "bg_color": "#030306",
    "clock_height": 80,
    "clock_font_size": 48,
    "n_points": 80,  # Points on circle (sparse, easy to follow individual lines)
}


def hsv_to_hex(h: float, s: float, v: float) -> str:
    """Convert HSV to hex color"""
    try:
        h = h % 1.0
        i = int(h * 6)
        f = (h * 6) - i
        p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
        rgb = [(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)][i]
        return f"#{int(rgb[0] * 255):02x}{int(rgb[1] * 255):02x}{int(rgb[2] * 255):02x}"
    except Exception:
        return "#8080ff"


# =============================================================================
# Modular Resonance Visualization
# =============================================================================
class ModularResonance:
    """Modular arithmetic visualization - cardioids, nephroids, stars"""

    name = "Modular Resonance"

    def __init__(self):
        self.n_points = CONFIG["n_points"]
        self.t = 0.0
        self.randomize_parameters()

        # Precompute circle points
        self.angles = [2 * math.pi * i / self.n_points for i in range(self.n_points)]
        self.cos_a = [math.cos(a) for a in self.angles]
        self.sin_a = [math.sin(a) for a in self.angles]

    def randomize_parameters(self):
        """Randomize evolution parameters"""
        self.phi = (1 + math.sqrt(5)) / 2  # Golden ratio
        self.psi = self.phi - 1

        self.params = {
            "base_mult": 2 + random.random() * 3,  # 2-5
            "wave_amp": 25 + random.random() * 20,  # 25-45
            "wave_speed": 0.06 + random.random() * 0.08,  # 0.06-0.14 (slower)
            "phi_amp": 10 + random.random() * 15,  # 10-25
            "psi_amp": 5 + random.random() * 10,  # 5-15
            "sqrt2_amp": 3 + random.random() * 7,  # 3-10
            "breath_amp": 0.01 + random.random() * 0.02,  # 0.01-0.03
            "breath_speed": 1.0 + random.random() * 1.0,  # 1-2
            "hue_speed": 0.02 + random.random() * 0.04,  # 0.02-0.06
            "time_speed": 0.002 + random.random() * 0.002,  # 0.002-0.004 (slower)
        }
        self.t = random.random() * 100  # Random start phase

    def update(self):
        self.t += self.params["time_speed"]

    def get_pattern_name(self, mult):
        """Get pattern name for special multipliers"""
        m = round(mult)
        if abs(mult - m) < 0.15:
            names = {
                2: "Cardioid",
                3: "Nephroid",
                4: "Trefoil",
                5: "Quatrefoil",
                6: "Cinquefoil",
                7: "Sexfoil",
            }
            return names.get(m, "")
        return ""

    def get_lines(self, width, height):
        """Get all lines with colors"""
        try:
            cx, cy = width / 2, height / 2
            base_radius = min(width, height) * 0.38

            # Evolving multiplier with multiple irrational frequencies
            p = self.params
            multiplier = (
                p["base_mult"]
                + p["wave_amp"] * (1 + math.sin(self.t * p["wave_speed"]))
                + p["phi_amp"] * math.sin(self.t * p["wave_speed"] * self.phi)
                + p["psi_amp"] * math.sin(self.t * p["wave_speed"] * self.psi)
                + p["sqrt2_amp"] * math.sin(self.t * p["wave_speed"] * math.sqrt(2))
            )

            # Breathing effect
            breath = 1 + p["breath_amp"] * math.sin(self.t * p["breath_speed"])
            r = base_radius * breath

            # Calculate point positions
            px = [cx + r * c for c in self.cos_a]
            py = [cy + r * s for s in self.sin_a]

            lines = []
            for i in range(self.n_points):
                dest = int(i * multiplier) % self.n_points
                if i == dest:
                    continue

                x1, y1 = px[i], py[i]
                x2, y2 = px[dest], py[dest]

                # Color based on position and jump distance
                hue = (i / self.n_points + self.t * p["hue_speed"]) % 1.0
                jump = abs(dest - i) / self.n_points
                sat = 0.5 + 0.5 * jump

                # Brightness from line length
                dist = math.hypot(x2 - x1, y2 - y1)
                val = 0.25 + 0.65 * min(1, dist / r)

                color = hsv_to_hex(hue, sat, val)
                lines.append((x1, y1, x2, y2, color, 1))

            return lines, multiplier
        except Exception:
            return [], 2.0


# =============================================================================
# STAR FIELD (Background)
# =============================================================================
class StarField:
    """Background stars"""

    def __init__(self, width, height):
        self.width, self.height = max(1, width), max(1, height)
        self.hue_offset = 0.0
        self.stars = [
            {
                "x": random.randint(0, self.width),
                "y": random.randint(0, self.height),
                "z": random.random() * 2 + 0.5,
                "brightness": random.uniform(0.15, 0.4),
                "hue": random.random(),
            }
            for _ in range(CONFIG["num_stars"])
        ]

    def update(self):
        self.hue_offset += 0.001
        for star in self.stars:
            star["x"] -= CONFIG["star_speed"] * star["z"]
            if star["x"] < 0:
                star["x"] = self.width
                star["y"] = random.randint(0, max(1, self.height))
                star["hue"] = random.random()

    def resize(self, w, h):
        self.width, self.height = max(1, w), max(1, h)

    def get_stars(self):
        return [
            (
                s["x"],
                s["y"],
                hsv_to_hex((s["hue"] + self.hue_offset) % 1.0, 0.25, s["brightness"]),
            )
            for s in self.stars
        ]


# =============================================================================
# MAIN SCREENSAVER
# =============================================================================
class Screensaver:
    """Modular Resonance screensaver with random parameter switching"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Modular Resonance")
        self.root.configure(bg=CONFIG["bg_color"])

        self.width, self.height = 900, 700
        self.root.geometry(f"{self.width}x{self.height}")
        self.root.minsize(400, 300)

        # Clock bar
        self.clock_frame = tk.Frame(
            self.root, bg="#000000", height=CONFIG["clock_height"]
        )
        self.clock_frame.pack(fill=tk.X, side=tk.TOP)
        self.clock_frame.pack_propagate(False)

        self.clock_label = tk.Label(
            self.clock_frame,
            text="",
            font=("Arial", CONFIG["clock_font_size"], "bold"),
            fg="#ffffff",
            bg="#000000",
        )
        self.clock_label.pack(expand=True)

        self.name_label = tk.Label(
            self.clock_frame,
            text="Modular Resonance",
            font=("Arial", 14),
            fg="#666666",
            bg="#000000",
        )
        self.name_label.place(relx=0.98, rely=0.5, anchor="e")

        # Multiplier display
        self.mult_label = tk.Label(
            self.clock_frame, text="", font=("Consolas", 12), fg="#444444", bg="#000000"
        )
        self.mult_label.place(relx=0.02, rely=0.5, anchor="w")

        # Canvas
        self.canvas = tk.Canvas(self.root, bg=CONFIG["bg_color"], highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Initialize
        self.stars = StarField(self.width, self.height)
        self.viz = ModularResonance()

        # Pre-create canvas items
        self.line_items = [
            self.canvas.create_line(0, 0, 0, 0, fill="", width=1)
            for _ in range(CONFIG["n_points"])
        ]
        self.star_items = [
            self.canvas.create_oval(0, 0, 1, 1, fill="", outline="")
            for _ in range(CONFIG["num_stars"])
        ]

        # Bindings
        self.root.bind("<Escape>", lambda e: self.quit())
        self.root.bind("<space>", lambda e: self._randomize_params())
        self.root.bind("<Configure>", self._on_resize)
        self.root.protocol("WM_DELETE_WINDOW", self.quit)

        self.frame_time = 1000 // CONFIG["fps"]
        self.running = True

        # Schedule auto parameter randomization
        self.root.after(CONFIG["switch_interval"], self._auto_randomize)

    def _randomize_params(self):
        """Randomize visualization parameters"""
        try:
            self.viz.randomize_parameters()
        except Exception:
            pass

    def _auto_randomize(self):
        """Auto-randomize every 30 minutes"""
        if self.running:
            self._randomize_params()
            self.root.after(CONFIG["switch_interval"], self._auto_randomize)

    def _on_resize(self, event):
        try:
            if event.widget == self.canvas:
                self.width, self.height = event.width, event.height
                self.stars.resize(self.width, self.height)
        except Exception:
            pass

    def quit(self):
        self.running = False
        try:
            self.root.destroy()
        except Exception:
            pass

    def draw(self):
        try:
            self.clock_label.config(text=datetime.now().strftime("%H:%M:%S"))

            # Stars
            s = CONFIG["star_size"]
            for i, (x, y, color) in enumerate(self.stars.get_stars()):
                if i < len(self.star_items):
                    self.canvas.coords(self.star_items[i], x - s, y - s, x + s, y + s)
                    self.canvas.itemconfig(self.star_items[i], fill=color)

            # Modular resonance lines
            lines, mult = self.viz.get_lines(self.width, self.height)

            # Update multiplier display
            pattern = self.viz.get_pattern_name(mult)
            mult_text = f"×{mult:.2f}"
            if pattern:
                mult_text += f"  {pattern}"
            self.mult_label.config(text=mult_text)

            for i, item in enumerate(self.line_items):
                if i < len(lines):
                    x1, y1, x2, y2, color, lw = lines[i]
                    self.canvas.coords(item, x1, y1, x2, y2)
                    self.canvas.itemconfig(item, fill=color, width=lw)
                else:
                    self.canvas.coords(item, 0, 0, 0, 0)
        except Exception:
            pass

    def run(self):
        def frame():
            if not self.running:
                return
            try:
                self.viz.update()
                self.stars.update()
                self.draw()
            except Exception:
                pass
            self.root.after(self.frame_time, frame)

        frame()
        try:
            self.root.mainloop()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        Screensaver().run()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error: {e}")
