#!/usr/bin/env python3
"""
Lubuntu-style Screensaver - 4D Hypercube (Tesseract) projection
Lightweight, beautiful, crash-resistant - Pure Tkinter
"""

import math
import random
import tkinter as tk
from datetime import datetime

# === CONFIG ===
CONFIG = {
    "fps": 30,
    "rotation_speed_4d": 0.012,
    "rotation_speed_3d": 0.008,
    "color_cycle_speed": 0.004,
    "num_stars": 40,
    "star_speed": 0.3,
    "star_size": 3,
    "bg_color": "#06080c",
    "line_width": 3,
    "clock_height": 80,  # ~3cm at typical DPI
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


class Tesseract:
    """4D Hypercube - projects from 4D to 2D with rotations"""

    def __init__(self):
        self.angle_xy = 0.0  # 4D rotation in XY plane
        self.angle_zw = 0.0  # 4D rotation in ZW plane
        self.angle_xz = 0.0  # 3D rotation
        self.angle_yz = 0.0  # 3D rotation
        self.hue_offset = 0.0

        # 16 vertices of a tesseract (4D hypercube)
        self.vertices_4d = []
        for x in [-1, 1]:
            for y in [-1, 1]:
                for z in [-1, 1]:
                    for w in [-1, 1]:
                        self.vertices_4d.append([x, y, z, w])

        # 32 edges - connect vertices that differ in exactly one coordinate
        self.edges = []
        for i in range(16):
            for j in range(i + 1, 16):
                diff = sum(
                    1
                    for k in range(4)
                    if self.vertices_4d[i][k] != self.vertices_4d[j][k]
                )
                if diff == 1:
                    self.edges.append((i, j))

    def rotate_4d(self, point):
        """Apply 4D rotations"""
        try:
            x, y, z, w = point

            # XW rotation (4D specific)
            cos_xy, sin_xy = math.cos(self.angle_xy), math.sin(self.angle_xy)
            x, w = x * cos_xy - w * sin_xy, x * sin_xy + w * cos_xy

            # ZW rotation (4D specific)
            cos_zw, sin_zw = math.cos(self.angle_zw), math.sin(self.angle_zw)
            z, w = z * cos_zw - w * sin_zw, z * sin_zw + w * cos_zw

            # XZ rotation (3D)
            cos_xz, sin_xz = math.cos(self.angle_xz), math.sin(self.angle_xz)
            x, z = x * cos_xz - z * sin_xz, x * sin_xz + z * cos_xz

            # YZ rotation (3D)
            cos_yz, sin_yz = math.cos(self.angle_yz), math.sin(self.angle_yz)
            y, z = y * cos_yz - z * sin_yz, y * sin_yz + z * cos_yz

            return [x, y, z, w]
        except Exception:
            return point

    def project(self, point_4d, width, height):
        """Project 4D point to 2D screen"""
        try:
            x, y, z, w = point_4d

            # 4D to 3D perspective projection
            distance_4d = 3.0
            scale_4d = distance_4d / (distance_4d - w)
            x3 = x * scale_4d
            y3 = y * scale_4d
            z3 = z * scale_4d

            # 3D to 2D perspective projection
            distance_3d = 4.0
            scale_3d = distance_3d / (distance_3d - z3)

            # Scale to fit window with padding
            size = min(width, height) * 0.14
            screen_x = width / 2 + x3 * scale_3d * size
            screen_y = height / 2 - y3 * scale_3d * size

            # Depth for coloring
            depth = (w + 1) / 2  # Normalize w to [0, 1]

            return screen_x, screen_y, depth, scale_4d * scale_3d
        except Exception:
            return width / 2, height / 2, 0.5, 1.0

    def update(self):
        try:
            self.angle_xy += CONFIG["rotation_speed_4d"]
            self.angle_zw += CONFIG["rotation_speed_4d"] * 0.7
            self.angle_xz += CONFIG["rotation_speed_3d"]
            self.angle_yz += CONFIG["rotation_speed_3d"] * 0.5
            self.hue_offset += CONFIG["color_cycle_speed"]
        except Exception:
            pass

    def get_edges(self, width, height):
        """Get projected edges with colors"""
        edges_2d = []
        try:
            # Project all vertices
            projected = []
            for v in self.vertices_4d:
                rotated = self.rotate_4d(v)
                projected.append(self.project(rotated, width, height))

            # Create edge data
            for idx, (i, j) in enumerate(self.edges):
                try:
                    x1, y1, d1, s1 = projected[i]
                    x2, y2, d2, s2 = projected[j]

                    # Color based on edge index + hue cycling
                    hue = (idx / len(self.edges) + self.hue_offset) % 1.0
                    avg_depth = (d1 + d2) / 2
                    saturation = 0.7 + avg_depth * 0.3
                    value = 0.6 + avg_depth * 0.4

                    color = hsv_to_hex(hue, saturation, value)

                    # Line width based on depth
                    lw = max(1, int(CONFIG["line_width"] * (s1 + s2) / 2))

                    edges_2d.append((x1, y1, x2, y2, color, lw))
                except Exception:
                    continue
        except Exception:
            pass
        return edges_2d


class StarField:
    """Background stars with color cycling"""

    def __init__(self, width, height):
        self.width = max(1, width)
        self.height = max(1, height)
        self.hue_offset = 0.0
        self.stars = []
        self._init_stars()

    def _init_stars(self):
        try:
            self.stars = [
                {
                    "x": random.randint(0, self.width),
                    "y": random.randint(0, self.height),
                    "z": random.random() * 2 + 0.5,
                    "brightness": random.uniform(0.3, 0.8),
                    "hue": random.random(),
                }
                for _ in range(CONFIG["num_stars"])
            ]
        except Exception:
            self.stars = []

    def update(self):
        try:
            self.hue_offset += CONFIG["color_cycle_speed"] * 0.3
            for star in self.stars:
                try:
                    star["x"] -= CONFIG["star_speed"] * star["z"]
                    if star["x"] < 0:
                        star["x"] = self.width
                        star["y"] = random.randint(0, max(1, self.height))
                        star["hue"] = random.random()
                except Exception:
                    continue
        except Exception:
            pass

    def resize(self, width, height):
        try:
            self.width, self.height = max(1, width), max(1, height)
            self._init_stars()
        except Exception:
            pass

    def get_stars(self):
        try:
            return [
                (
                    s["x"],
                    s["y"],
                    hsv_to_hex(
                        (s["hue"] + self.hue_offset) % 1.0, 0.4, s["brightness"]
                    ),
                )
                for s in self.stars
            ]
        except Exception:
            return []


class Screensaver:
    """Main screensaver - windowed tesseract"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("4D Hypercube - Lubuntu Style")
        self.root.configure(bg=CONFIG["bg_color"])

        # Windowed mode - nice size
        self.width, self.height = 900, 700
        self.root.geometry(f"{self.width}x{self.height}")
        self.root.minsize(400, 300)

        # Clock bar at top
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

        # Canvas below clock
        self.canvas = tk.Canvas(self.root, bg=CONFIG["bg_color"], highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Objects
        self.tesseract = Tesseract()
        self.stars = StarField(self.width, self.height)

        # Pre-create canvas items for reuse (no delete/create flickering)
        self.star_items = [
            self.canvas.create_oval(0, 0, 1, 1, fill="", outline="")
            for _ in range(CONFIG["num_stars"])
        ]
        self.edge_items = [
            self.canvas.create_line(0, 0, 0, 0, fill="", width=1) for _ in range(32)
        ]  # 32 edges in tesseract

        # Bindings
        self.root.bind("<Escape>", lambda e: self.quit())
        self.root.bind("<Configure>", self._on_resize)
        self.root.protocol("WM_DELETE_WINDOW", self.quit)

        self.frame_time = 1000 // CONFIG["fps"]
        self.running = True

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

    def update_clock(self):
        try:
            self.clock_label.config(text=datetime.now().strftime("%H:%M:%S"))
        except Exception:
            pass

    def draw(self):
        try:
            self.update_clock()

            # Update stars (reuse items - no flickering)
            s = CONFIG["star_size"]
            stars_data = self.stars.get_stars()
            for i, item in enumerate(self.star_items):
                try:
                    if i < len(stars_data):
                        x, y, color = stars_data[i]
                        self.canvas.coords(item, x - s, y - s, x + s, y + s)
                        self.canvas.itemconfig(item, fill=color)
                except Exception:
                    continue

            # Update tesseract edges (reuse items - no flickering)
            edges_data = self.tesseract.get_edges(self.width, self.height)
            for i, item in enumerate(self.edge_items):
                try:
                    if i < len(edges_data):
                        x1, y1, x2, y2, color, lw = edges_data[i]
                        self.canvas.coords(item, x1, y1, x2, y2)
                        self.canvas.itemconfig(item, fill=color, width=lw)
                except Exception:
                    continue
        except Exception:
            pass

    def run(self):
        def frame():
            if not self.running:
                return
            try:
                self.tesseract.update()
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
        pass  # Clean exit on Ctrl+C
    except Exception as e:
        print(f"Error: {e}")
