#!/usr/bin/env python3
"""
HyperOrbits Screensaver - Single visualization with random parameter switching
Random parameter reset every 30 minutes - Pure Tkinter
"""

import math
import random
import tkinter as tk
from datetime import datetime
import time

# === CONFIG ===
CONFIG = {
    "fps": 30,
    "switch_interval": 30 * 60 * 1000,  # 30 minutes - randomize parameters
    "num_stars": 35,
    "star_speed": 0.25,
    "star_size": 2,
    "bg_color": "#050508",
    "clock_height": 80,
    "clock_font_size": 48,
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
# HyperOrbits (4D particle swarm with randomizable parameters)
# =============================================================================
class HyperOrbits:
    """4D hyperdimensional particle swarm projected to 2D"""

    name = "HyperOrbits"

    def __init__(self, num_points=350):
        self.num_points = num_points
        self.start_time = time.time()
        self.randomize_parameters()
        self._create_particles()

    def randomize_parameters(self):
        """Randomize all major parameters for variety"""
        self.params = {
            # Speed multipliers
            "global_speed": 0.5 + random.random() * 1.0,
            "rotation_speed": 0.1 + random.random() * 0.3,
            # 4D projection params
            "p1_freq": 0.1 + random.random() * 0.15,
            "p2_freq": 0.08 + random.random() * 0.1,
            "p3_freq": 0.05 + random.random() * 0.08,
            "p4_freq": 0.12 + random.random() * 0.15,
            # Shape params
            "angle_mix": 0.5 + random.random() * 0.5,
            "angle2_mix": 0.4 + random.random() * 0.6,
            "z_influence": 0.3 + random.random() * 0.7,
            # Color params
            "hue_speed": 0.1 + random.random() * 0.2,
            "hue_z_mix": 0.08 + random.random() * 0.15,
            "hue_radius_mix": 0.2 + random.random() * 0.3,
            "saturation_base": 0.5 + random.random() * 0.3,
            "value_base": 0.2 + random.random() * 0.2,
            # Size params
            "size_breath": 0.4 + random.random() * 0.5,
            "base_scale": 0.3 + random.random() * 0.15,
        }
        self.start_time = time.time()  # Reset time on parameter change

    def _create_particles(self):
        """Create particle array"""
        self.particles = []
        for _ in range(self.num_points):
            self.particles.append(
                {
                    "theta": random.random() * 2 * math.pi,
                    "radius": 0.15 + 0.85 * (random.random() ** 1.5),
                    "phase": random.random() * 2 * math.pi,
                    "speed": 0.3 + random.random() * 2.0,
                    "size": 1.0 + 2.5 * (random.random() ** 0.5),
                    "hue_offset": random.random(),
                }
            )

    def update(self):
        pass  # Time-based animation

    def get_points(self, width, height):
        try:
            t = (time.time() - self.start_time) * self.params["global_speed"]
            cx, cy = width / 2, height / 2
            base_scale = min(width, height) * self.params["base_scale"]

            # 4D hyperparameters with randomized frequencies
            p1 = math.sin(t * self.params["p1_freq"])
            p2 = math.sin(t * self.params["p2_freq"] + 1.3)
            p3 = math.sin(t * self.params["p3_freq"] + 2.7)
            p4 = math.sin(t * self.params["p4_freq"] + 0.4)

            points = []
            for p in self.particles:
                local_t = t * p["speed"] * self.params["rotation_speed"] + p["phase"]

                # Angles with parameterized mixing
                angle = (
                    p["theta"]
                    + local_t * (0.3 + self.params["angle_mix"] * p1)
                    + p["radius"] * (0.6 * p2)
                )
                angle2 = p["theta"] * (1.5 + 0.8 * p3) + local_t * (
                    0.8 + self.params["angle2_mix"] * p4
                )

                # Hyperdimensional projection
                x_norm = math.sin(angle) + self.params["angle_mix"] * math.sin(angle2)
                y_norm = math.cos(angle) + self.params["angle_mix"] * math.cos(
                    angle2 + 1.7
                )
                z = math.sin(angle * 0.5 + local_t * self.params["z_influence"])

                scale = base_scale * p["radius"]
                x = cx + x_norm * scale
                y = cy + y_norm * scale

                # Breathing size
                size = p["size"] * (0.8 + self.params["size_breath"] * (0.5 + 0.5 * z))

                # Dynamic color
                hue = (
                    self.params["hue_z_mix"] * z
                    + self.params["hue_radius_mix"] * p["radius"]
                    + self.params["hue_speed"] * math.sin(local_t * 0.3)
                    + p["hue_offset"]
                ) % 1.0
                sat = self.params["saturation_base"] + 0.35 * abs(z)
                val = self.params["value_base"] + 0.7 * abs(math.sin(angle))
                color = hsv_to_hex(hue, min(1, sat), min(1, val))

                points.append((x, y, size, color))
            return points
        except Exception:
            return []


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
                "brightness": random.uniform(0.2, 0.5),
                "hue": random.random(),
            }
            for _ in range(CONFIG["num_stars"])
        ]

    def update(self):
        self.hue_offset += 0.002
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
                hsv_to_hex((s["hue"] + self.hue_offset) % 1.0, 0.3, s["brightness"]),
            )
            for s in self.stars
        ]


# =============================================================================
# MAIN SCREENSAVER
# =============================================================================
class Screensaver:
    """HyperOrbits screensaver with random parameter switching"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("HyperOrbits Screensaver")
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
            text="HyperOrbits",
            font=("Arial", 14),
            fg="#666666",
            bg="#000000",
        )
        self.name_label.place(relx=0.98, rely=0.5, anchor="e")

        # Canvas
        self.canvas = tk.Canvas(self.root, bg=CONFIG["bg_color"], highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Initialize
        self.stars = StarField(self.width, self.height)
        self.viz = HyperOrbits(num_points=350)

        # Pre-create canvas items
        self.point_items = [
            self.canvas.create_oval(0, 0, 1, 1, fill="", outline="")
            for _ in range(self.viz.num_points)
        ]
        self.star_items = [
            self.canvas.create_oval(0, 0, 1, 1, fill="", outline="")
            for _ in range(CONFIG["num_stars"])
        ]

        # Bindings
        self.root.bind("<Escape>", lambda e: self.quit())
        self.root.bind(
            "<space>", lambda e: self._randomize_params()
        )  # Manual randomize
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
            self.root.title(f"HyperOrbits - New Pattern")
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

            # HyperOrbits points
            points = self.viz.get_points(self.width, self.height)
            for i, item in enumerate(self.point_items):
                if i < len(points):
                    x, y, size, color = points[i]
                    self.canvas.coords(item, x - size, y - size, x + size, y + size)
                    self.canvas.itemconfig(item, fill=color)
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
