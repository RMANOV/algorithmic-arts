#!/usr/bin/env python3
"""
Lubuntu-style Multi-Screensaver
7 Visualizations with random rotation every 30 minutes
Pure Tkinter - zero dependencies
"""

import math
import random
import tkinter as tk
from datetime import datetime

# === CONFIG ===
CONFIG = {
    "fps": 30,
    "switch_interval": 30 * 60 * 1000,  # 30 minutes in ms
    "rotation_speed": 0.008,
    "color_cycle_speed": 0.004,
    "num_stars": 40,
    "star_speed": 0.3,
    "star_size": 3,
    "bg_color": "#06080c",
    "line_width": 3,
    "num_trail_points": 500,
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
# VISUALIZATION 1: Tesseract (4D Hypercube)
# =============================================================================
class Tesseract:
    """4D Hypercube projection"""

    name = "4D Tesseract"
    num_lines = 32

    def __init__(self):
        self.angle_xy = self.angle_zw = self.angle_xz = self.angle_yz = 0.0
        self.hue_offset = 0.0
        self.vertices_4d = [
            [x, y, z, w]
            for x in [-1, 1]
            for y in [-1, 1]
            for z in [-1, 1]
            for w in [-1, 1]
        ]
        self.edges = [
            (i, j)
            for i in range(16)
            for j in range(i + 1, 16)
            if sum(
                1 for k in range(4) if self.vertices_4d[i][k] != self.vertices_4d[j][k]
            )
            == 1
        ]

    def update(self):
        try:
            self.angle_xy += CONFIG["rotation_speed"] * 1.5
            self.angle_zw += CONFIG["rotation_speed"] * 1.05
            self.angle_xz += CONFIG["rotation_speed"]
            self.angle_yz += CONFIG["rotation_speed"] * 0.5
            self.hue_offset += CONFIG["color_cycle_speed"]
        except Exception:
            pass

    def get_edges(self, width, height):
        try:
            projected = []
            for v in self.vertices_4d:
                x, y, z, w = v
                c, s = math.cos(self.angle_xy), math.sin(self.angle_xy)
                x, w = x * c - w * s, x * s + w * c
                c, s = math.cos(self.angle_zw), math.sin(self.angle_zw)
                z, w = z * c - w * s, z * s + w * c
                c, s = math.cos(self.angle_xz), math.sin(self.angle_xz)
                x, z = x * c - z * s, x * s + z * c
                c, s = math.cos(self.angle_yz), math.sin(self.angle_yz)
                y, z = y * c - z * s, y * s + z * c

                d4, d3 = 3.0, 4.0
                s4 = d4 / (d4 - w)
                x3, y3, z3 = x * s4, y * s4, z * s4
                s3 = d3 / (d3 - z3)
                size = min(width, height) * 0.14
                projected.append(
                    (
                        width / 2 + x3 * s3 * size,
                        height / 2 - y3 * s3 * size,
                        (w + 1) / 2,
                        s4 * s3,
                    )
                )

            edges = []
            for idx, (i, j) in enumerate(self.edges):
                x1, y1, d1, s1 = projected[i]
                x2, y2, d2, s2 = projected[j]
                hue = (idx / len(self.edges) + self.hue_offset) % 1.0
                color = hsv_to_hex(
                    hue, 0.7 + (d1 + d2) / 4 * 0.3, 0.6 + (d1 + d2) / 4 * 0.4
                )
                lw = max(1, int(CONFIG["line_width"] * (s1 + s2) / 2))
                edges.append((x1, y1, x2, y2, color, lw))
            return edges
        except Exception:
            return []


# =============================================================================
# VISUALIZATION 2: Spirograph 3D
# =============================================================================
class Spirograph3D:
    """3D Spirograph with evolving parameters"""

    name = "3D Spirograph"
    num_lines = 400

    def __init__(self):
        self.t = 0.0
        self.hue_offset = 0.0
        self.R, self.r = 1.0, 0.4
        self.k = 3.0 + random.random() * 3
        self.m = 2.0 + random.random()
        self.points = []
        self.angle = 0.0

    def update(self):
        try:
            self.k += 0.0003
            self.m += 0.0002
            if self.k > 12:
                self.k = 2.0 + random.random() * 2
            if self.m > 8:
                self.m = 1.0 + random.random()

            for _ in range(3):
                self.t += 0.02
                x = self.R * math.cos(self.t) + self.r * math.cos(self.k * self.t)
                y = self.R * math.sin(self.t) + self.r * math.sin(self.k * self.t)
                z = 0.5 * math.sin(self.m * self.t)
                self.points.append((x, y, z, self.hue_offset))

            if len(self.points) > CONFIG["num_trail_points"]:
                self.points = self.points[-CONFIG["num_trail_points"] :]

            self.angle += CONFIG["rotation_speed"]
            self.hue_offset += CONFIG["color_cycle_speed"]
        except Exception:
            pass

    def get_edges(self, width, height):
        try:
            edges = []
            cos_a, sin_a = math.cos(self.angle), math.sin(self.angle)
            size = min(width, height) * 0.25

            for i in range(1, len(self.points)):
                x1, y1, z1, _ = self.points[i - 1]
                x2, y2, z2, _ = self.points[i]

                x1r, x2r = x1 * cos_a - z1 * sin_a, x2 * cos_a - z2 * sin_a
                z1r, z2r = x1 * sin_a + z1 * cos_a, x2 * sin_a + z2 * cos_a

                d = 4.0
                s1, s2 = d / (d - z1r), d / (d - z2r)
                sx1, sy1 = width / 2 + x1r * s1 * size, height / 2 - y1 * s1 * size
                sx2, sy2 = width / 2 + x2r * s2 * size, height / 2 - y2 * s2 * size

                t = i / len(self.points)
                hue = (t * 0.8 + self.hue_offset) % 1.0
                color = hsv_to_hex(hue, 0.8, 0.5 + t * 0.5)
                edges.append((sx1, sy1, sx2, sy2, color, CONFIG["line_width"]))
            return edges
        except Exception:
            return []


# =============================================================================
# VISUALIZATION 3: Lissajous Knot
# =============================================================================
class LissajousKnot:
    """3D Lissajous curves forming knots"""

    name = "Lissajous Knot"
    num_lines = 400

    def __init__(self):
        self.t = 0.0
        self.hue_offset = 0.0
        self.a, self.b, self.c = 3.0, 2.0, 5.0
        self.delta = random.random() * math.pi
        self.points = []
        self.angle_x = self.angle_y = 0.0

    def update(self):
        try:
            self.delta += 0.0001
            if self.delta > math.pi * 2:
                self.a = 2 + random.randint(0, 5)
                self.b = 2 + random.randint(0, 4)
                self.c = 3 + random.randint(0, 4)
                self.delta = 0.0

            for _ in range(3):
                self.t += 0.015
                x = math.sin(self.a * self.t + self.delta)
                y = math.sin(self.b * self.t)
                z = math.sin(self.c * self.t)
                self.points.append((x, y, z))

            if len(self.points) > CONFIG["num_trail_points"]:
                self.points = self.points[-CONFIG["num_trail_points"] :]

            self.angle_x += CONFIG["rotation_speed"] * 0.7
            self.angle_y += CONFIG["rotation_speed"]
            self.hue_offset += CONFIG["color_cycle_speed"]
        except Exception:
            pass

    def get_edges(self, width, height):
        try:
            edges = []
            cx, sx = math.cos(self.angle_x), math.sin(self.angle_x)
            cy, sy = math.cos(self.angle_y), math.sin(self.angle_y)
            size = min(width, height) * 0.28

            for i in range(1, len(self.points)):
                x1, y1, z1 = self.points[i - 1]
                x2, y2, z2 = self.points[i]

                y1r, z1r = y1 * cx - z1 * sx, y1 * sx + z1 * cx
                y2r, z2r = y2 * cx - z2 * sx, y2 * sx + z2 * cx
                x1r, z1r = x1 * cy - z1r * sy, x1 * sy + z1r * cy
                x2r, z2r = x2 * cy - z2r * sy, x2 * sy + z2r * cy

                d = 4.0
                s1, s2 = d / (d - z1r), d / (d - z2r)
                sx1, sy1 = width / 2 + x1r * s1 * size, height / 2 - y1r * s1 * size
                sx2, sy2 = width / 2 + x2r * s2 * size, height / 2 - y2r * s2 * size

                t = i / len(self.points)
                hue = (t + self.hue_offset) % 1.0
                color = hsv_to_hex(hue, 0.85, 0.4 + t * 0.6)
                edges.append((sx1, sy1, sx2, sy2, color, CONFIG["line_width"]))
            return edges
        except Exception:
            return []


# =============================================================================
# VISUALIZATION 4: Toroidal Helix (3D спирала около торус)
# =============================================================================
class ToroidalHelix:
    """3D helix wrapped around a torus - mesmerizing donut spiral"""

    name = "Toroidal Helix"
    num_lines = 500

    def __init__(self):
        self.t = 0.0
        self.hue_offset = 0.0
        self.R = 1.0  # Major radius (torus)
        self.r = 0.35  # Minor radius (tube)
        self.p = 5 + random.random() * 3  # Helix winds (evolves)
        self.q = 2 + random.random() * 2  # Secondary frequency
        self.points = []
        self.angle_x = self.angle_y = 0.0

    def update(self):
        try:
            # Slowly evolve parameters
            self.p += 0.0002
            self.q += 0.00015
            if self.p > 12:
                self.p = 4 + random.random() * 2
            if self.q > 6:
                self.q = 1.5 + random.random()

            for _ in range(3):
                self.t += 0.025
                # Toroidal helix parametric equations
                x = (self.R + self.r * math.cos(self.p * self.t)) * math.cos(self.t)
                y = (self.R + self.r * math.cos(self.p * self.t)) * math.sin(self.t)
                z = self.r * math.sin(self.p * self.t) * math.cos(self.q * self.t)
                self.points.append((x, y, z))

            if len(self.points) > CONFIG["num_trail_points"]:
                self.points = self.points[-CONFIG["num_trail_points"] :]

            self.angle_x += CONFIG["rotation_speed"] * 0.6
            self.angle_y += CONFIG["rotation_speed"] * 0.8
            self.hue_offset += CONFIG["color_cycle_speed"]
        except Exception:
            pass

    def get_edges(self, width, height):
        try:
            edges = []
            cx, sx = math.cos(self.angle_x), math.sin(self.angle_x)
            cy, sy = math.cos(self.angle_y), math.sin(self.angle_y)
            size = min(width, height) * 0.22

            for i in range(1, len(self.points)):
                x1, y1, z1 = self.points[i - 1]
                x2, y2, z2 = self.points[i]

                # Rotate around X then Y
                y1r, z1r = y1 * cx - z1 * sx, y1 * sx + z1 * cx
                y2r, z2r = y2 * cx - z2 * sx, y2 * sx + z2 * cx
                x1r, z1r = x1 * cy - z1r * sy, x1 * sy + z1r * cy
                x2r, z2r = x2 * cy - z2r * sy, x2 * sy + z2r * cy

                # Perspective projection
                d = 4.0
                s1, s2 = d / (d - z1r), d / (d - z2r)
                sx1, sy1 = width / 2 + x1r * s1 * size, height / 2 - y1r * s1 * size
                sx2, sy2 = width / 2 + x2r * s2 * size, height / 2 - y2r * s2 * size

                t = i / len(self.points)
                hue = (t * 0.9 + self.hue_offset) % 1.0
                color = hsv_to_hex(hue, 0.85, 0.45 + t * 0.55)
                edges.append((sx1, sy1, sx2, sy2, color, CONFIG["line_width"]))
            return edges
        except Exception:
            return []


# =============================================================================
# VISUALIZATION 5: Modular Resonance (Cardioids, Nephroids, Stars)
# =============================================================================
class ModularResonance:
    """Modular arithmetic visualization - cardioids, nephroids, stars"""

    name = "Modular Resonance"
    num_lines = 120

    def __init__(self):
        self.n_points = 120  # Denser than standalone version
        self.t = 0.0
        self.phi = (1 + math.sqrt(5)) / 2  # Golden ratio
        self.psi = self.phi - 1
        self.params = {
            "base_mult": 2 + random.random() * 3,
            "wave_amp": 25 + random.random() * 20,
            "wave_speed": 0.08 + random.random() * 0.08,  # Reduced by 1/3
            "phi_amp": 10 + random.random() * 15,
            "psi_amp": 5 + random.random() * 10,
            "sqrt2_amp": 3 + random.random() * 7,
            "breath_amp": 0.01 + random.random() * 0.02,
            "breath_speed": 1.0 + random.random() * 1.0,
            "hue_speed": 0.02 + random.random() * 0.035,
            "time_speed": 0.0027 + random.random() * 0.002,  # Reduced by 1/3
        }
        self.t = random.random() * 100
        # Precompute circle points
        self.angles = [2 * math.pi * i / self.n_points for i in range(self.n_points)]
        self.cos_a = [math.cos(a) for a in self.angles]
        self.sin_a = [math.sin(a) for a in self.angles]

    def update(self):
        self.t += self.params["time_speed"]

    def get_edges(self, width, height):
        try:
            cx, cy = width / 2, height / 2
            base_radius = min(width, height) * 0.38
            p = self.params

            # Evolving multiplier with multiple irrational frequencies
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

            edges = []
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
                edges.append((x1, y1, x2, y2, color, 2))

            return edges
        except Exception:
            return []


# =============================================================================
# VISUALIZATION 6: Algorithmic Mandala
# =============================================================================
class AlgorithmicMandala:
    """Dynamic mandala with counter-rotating rings and sacred geometry"""

    name = "Algorithmic Mandala"
    num_lines = 200

    def __init__(self):
        self.symmetry = random.choice([6, 8, 12])
        self.n_rings = 6
        self.angles = [random.random() * math.pi * 2 for _ in range(self.n_rings)]
        self.hue_offset = 0.0
        self.t = 0.0
        self.params = {
            "base_speed": 0.006 + random.random() * 0.005,
            "hue_speed": 0.003 + random.random() * 0.003,
            "pulse_speed": 0.4 + random.random() * 0.4,
            "pulse_amp": 0.06 + random.random() * 0.08,
        }

    def update(self):
        p = self.params
        self.t += p["base_speed"]
        for i in range(self.n_rings):
            speed = 0.008 + i * 0.004
            self.angles[i] += speed * (1 if i % 2 == 0 else -1)
        self.hue_offset += p["hue_speed"]

    def get_edges(self, width, height):
        try:
            cx, cy = width / 2, height / 2
            max_r = min(width, height) * 0.38
            p = self.params
            pulse = 1 + p["pulse_amp"] * math.sin(self.t * p["pulse_speed"])
            edges = []

            # Ring points
            radii = [
                (i + 1) / self.n_rings * max_r * pulse for i in range(self.n_rings)
            ]
            ring_pts = []
            for ri, r in enumerate(radii):
                pts = []
                for j in range(self.symmetry):
                    a = self.angles[ri] + j * 2 * math.pi / self.symmetry
                    pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
                ring_pts.append(pts)

            # Ring polygons
            for ri, pts in enumerate(ring_pts):
                hue = (ri / self.n_rings + self.hue_offset) % 1.0
                for j in range(len(pts)):
                    x1, y1 = pts[j]
                    x2, y2 = pts[(j + 1) % len(pts)]
                    edges.append(
                        (x1, y1, x2, y2, hsv_to_hex((hue + j * 0.05) % 1, 0.8, 0.7), 2)
                    )

            # Inter-ring spokes
            for ri in range(len(ring_pts) - 1):
                hue = ((ri + 0.5) / self.n_rings + self.hue_offset) % 1.0
                for j in range(self.symmetry):
                    x1, y1 = ring_pts[ri][j]
                    x2, y2 = ring_pts[ri + 1][j]
                    edges.append((x1, y1, x2, y2, hsv_to_hex(hue, 0.7, 0.55), 2))

            # Cross connections (sacred geometry)
            for ri in range(0, len(ring_pts) - 1, 2):
                hue = (ri / self.n_rings + self.hue_offset + 0.5) % 1.0
                for j in range(self.symmetry):
                    x1, y1 = ring_pts[ri][j]
                    x2, y2 = ring_pts[ri + 1][(j + 1) % self.symmetry]
                    edges.append((x1, y1, x2, y2, hsv_to_hex(hue, 0.6, 0.45), 1))

            return edges
        except Exception:
            return []


# =============================================================================
# VISUALIZATION 7: Hexagonal Mesh - Shared Walls with Triangle Vertices
# =============================================================================
class HexagonalMesh:
    """Tessellated hexagons - 3 walls meet at each vertex forming triangles"""

    name = "Hexagonal Mesh"
    num_lines = 500

    def __init__(self):
        self.t = 0.0
        self.wave_angle = random.random() * math.pi * 2
        self.next_change = 200 + random.random() * 200
        self.hue_offset = 0.0
        self.vertices = {}  # Shared vertex cache
        self.params = {
            "wave_speed": 0.02 + random.random() * 0.015,
            "wave_freq": 0.05 + random.random() * 0.04,
            "vert_amp": 0.15,  # Vertex displacement amplitude
            "hue_speed": 0.004 + random.random() * 0.003,
        }

    def update(self):
        p = self.params
        self.t += p["wave_speed"]
        self.hue_offset += p["hue_speed"]
        if self.t > self.next_change:
            self.wave_angle += math.pi / 3 + random.random() * math.pi / 3
            self.next_change = self.t + 180 + random.random() * 220

    def get_edges(self, width, height):
        try:
            edges = []
            sz = min(width, height) * 0.07
            sqrt3 = math.sqrt(3)
            dx, dy = sz * 1.5, sz * sqrt3
            cols = int(width / dx) + 2
            rows = int(height / dy) + 2
            p = self.params
            wcos, wsin = math.cos(self.wave_angle), math.sin(self.wave_angle)

            # Build shared vertices grid - each vertex where 3 hex walls meet
            verts = {}
            for row in range(-1, rows + 1):
                for col in range(-1, cols + 1):
                    # Hex center
                    hcx = col * dx + sz * 0.5
                    hcy = row * dy + sz * 0.5
                    if col % 2:
                        hcy += dy / 2

                    # 6 vertices per hex (will be shared with neighbors)
                    for i in range(6):
                        a = i * math.pi / 3 + math.pi / 6
                        vx = hcx + sz * math.cos(a)
                        vy = hcy + sz * math.sin(a)
                        # Round to snap shared vertices
                        key = (round(vx, 1), round(vy, 1))
                        if key not in verts:
                            # Wave displacement at this vertex
                            dist = vx * wcos + vy * wsin
                            phase = dist * p["wave_freq"]
                            wave = math.sin(self.t - phase)
                            # Displace vertex radially from screen center
                            dcx, dcy = vx - width / 2, vy - height / 2
                            d = math.hypot(dcx, dcy) + 0.001
                            disp = wave * sz * p["vert_amp"]
                            verts[key] = (
                                vx + dcx / d * disp,
                                vy + dcy / d * disp,
                                dist,
                            )

            # Draw hex edges using shared vertices
            drawn = set()
            for row in range(rows):
                for col in range(cols):
                    hcx = col * dx + sz * 0.5
                    hcy = row * dy + sz * 0.5
                    if col % 2:
                        hcy += dy / 2
                    if hcx > width + sz or hcy > height + sz:
                        continue

                    # Get this hex's 6 vertices from shared pool
                    hex_verts = []
                    for i in range(6):
                        a = i * math.pi / 3 + math.pi / 6
                        vx = hcx + sz * math.cos(a)
                        vy = hcy + sz * math.sin(a)
                        key = (round(vx, 1), round(vy, 1))
                        hex_verts.append(verts.get(key, (vx, vy, 0)))

                    # Draw 6 edges (each shared with neighbor - draw once)
                    for i in range(6):
                        v1, v2 = hex_verts[i], hex_verts[(i + 1) % 6]
                        edge_key = (min(v1[:2], v2[:2]), max(v1[:2], v2[:2]))
                        if edge_key in drawn:
                            continue
                        drawn.add(edge_key)

                        hue = ((v1[2] + v2[2]) * 0.002 + self.hue_offset) % 1.0
                        edges.append(
                            (v1[0], v1[1], v2[0], v2[1], hsv_to_hex(hue, 0.7, 0.6), 2)
                        )

                    # Draw triangle spokes from center to vertices
                    hue2 = (hcx * 0.003 + self.hue_offset + 0.35) % 1.0
                    for i, v in enumerate(hex_verts):
                        edges.append(
                            (
                                hcx,
                                hcy,
                                v[0],
                                v[1],
                                hsv_to_hex((hue2 + i * 0.1) % 1, 0.85, 0.7),
                                2,
                            )
                        )

            return edges
        except Exception:
            return []


# =============================================================================
# STAR FIELD (Background)
# =============================================================================
class StarField:
    """Background stars with color cycling"""

    def __init__(self, width, height):
        self.width, self.height = max(1, width), max(1, height)
        self.hue_offset = 0.0
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

    def update(self):
        try:
            self.hue_offset += CONFIG["color_cycle_speed"] * 0.3
            for star in self.stars:
                star["x"] -= CONFIG["star_speed"] * star["z"]
                if star["x"] < 0:
                    star["x"] = self.width
                    star["y"] = random.randint(0, max(1, self.height))
                    star["hue"] = random.random()
        except Exception:
            pass

    def resize(self, w, h):
        self.width, self.height = max(1, w), max(1, h)

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


# =============================================================================
# MAIN SCREENSAVER
# =============================================================================
class Screensaver:
    """Multi-visualization screensaver with random rotation"""

    VISUALIZATIONS = [
        Tesseract,
        Spirograph3D,
        LissajousKnot,
        ToroidalHelix,
        ModularResonance,
        AlgorithmicMandala,
        HexagonalMesh,
    ]

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Lubuntu Screensaver")
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

        # Visualization name label
        self.name_label = tk.Label(
            self.clock_frame, text="", font=("Arial", 14), fg="#666666", bg="#000000"
        )
        self.name_label.place(relx=0.98, rely=0.5, anchor="e")

        # Canvas
        self.canvas = tk.Canvas(self.root, bg=CONFIG["bg_color"], highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Initialize
        self.stars = StarField(self.width, self.height)
        self.current_viz = None
        self.line_items = []
        self.star_items = [
            self.canvas.create_oval(0, 0, 1, 1, fill="", outline="")
            for _ in range(CONFIG["num_stars"])
        ]

        self._switch_visualization()

        # Bindings
        self.root.bind("<Escape>", lambda e: self.quit())
        self.root.bind(
            "<space>", lambda e: self._switch_visualization()
        )  # Manual switch
        self.root.bind("<Configure>", self._on_resize)
        self.root.protocol("WM_DELETE_WINDOW", self.quit)

        self.frame_time = 1000 // CONFIG["fps"]
        self.running = True

        # Schedule auto-switch
        self.root.after(CONFIG["switch_interval"], self._auto_switch)

    def _switch_visualization(self):
        """Switch to random visualization"""
        try:
            choices = [
                v for v in self.VISUALIZATIONS if not isinstance(self.current_viz, v)
            ]
            VizClass = (
                random.choice(choices)
                if choices
                else random.choice(self.VISUALIZATIONS)
            )
            self.current_viz = VizClass()

            for item in self.line_items:
                self.canvas.delete(item)
            self.line_items = [
                self.canvas.create_line(0, 0, 0, 0, fill="", width=1)
                for _ in range(self.current_viz.num_lines)
            ]

            self.name_label.config(text=self.current_viz.name)
            self.root.title(f"Screensaver - {self.current_viz.name}")
        except Exception:
            pass

    def _auto_switch(self):
        """Auto-switch every 30 minutes"""
        if self.running:
            self._switch_visualization()
            self.root.after(CONFIG["switch_interval"], self._auto_switch)

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

            s = CONFIG["star_size"]
            for i, (x, y, color) in enumerate(self.stars.get_stars()):
                if i < len(self.star_items):
                    self.canvas.coords(self.star_items[i], x - s, y - s, x + s, y + s)
                    self.canvas.itemconfig(self.star_items[i], fill=color)

            edges = (
                self.current_viz.get_edges(self.width, self.height)
                if self.current_viz
                else []
            )
            for i, item in enumerate(self.line_items):
                if i < len(edges):
                    x1, y1, x2, y2, color, lw = edges[i]
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
                if self.current_viz:
                    self.current_viz.update()
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
