"""Light-influenced tree growth with a Tkinter/Matplotlib GUI.

Includes adjustable light position, cycle count, light falloff, shade strength,
minimum light, phototropism, directional wobble, bud abortion, flower/bloom
probabilities, branch maximum age/length, seed control, click-to-move-light,
regeneration, statistics and PNG export.
"""

import math
import random
import tkinter as tk
from tkinter import ttk, filedialog
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from matplotlib.patches import Circle

WIDTH, HEIGHT = 12.0, 12.0
GRID_SIZE = 120
MAX_BRANCHES = 10_000

DEFAULTS = {
    "light_x": 6.0, "light_y": 14.0, "cycles": 35,
    "falloff": 0.5, "shade": 2.5, "min_light": 0.05,
    "bend": 0.15, "wobble": 0.10, "abort": 0.35,
    "flower": 0.25, "bloom": 0.30, "max_age": 14,
    "max_length": 4.0, "base_growth": 0.12,
    "growth_factor": 0.025, "apical_factor": 0.4,
    "ray_step": 0.08, "ray_start": 0.15,
}


class Branch:
    def __init__(self, bid, x, y, angle, order=0, parent=None):
        self.id = bid
        self.pts = [(x, y)]
        self.angle = angle
        self.order = order
        self.age = 0
        self.length = 0.0
        self.state = "active"
        self.ancestors = set() if parent is None else parent.ancestors | {parent.id}
        self.family = self.ancestors | {bid}

    @property
    def tip(self):
        return self.pts[-1]


class Simulation:
    def __init__(self, params, seed):
        self.p = params
        self.rng = random.Random(seed)
        self.light_x = params["light_x"]
        self.light_y = params["light_y"]
        self.branches = []
        self.owner = np.full((GRID_SIZE, GRID_SIZE), -1, dtype=np.int32)
        self.add_branch(WIDTH / 2, 0.0, math.radians(90))

    def cell(self, x, y):
        return int(x / WIDTH * GRID_SIZE), int(y / HEIGHT * GRID_SIZE)

    @staticmethod
    def inside(i, j):
        return 0 <= i < GRID_SIZE and 0 <= j < GRID_SIZE

    def add_branch(self, x, y, angle, order=0, parent=None):
        b = Branch(len(self.branches), x, y, angle, order, parent)
        self.branches.append(b)
        return b

    def stamp(self, b, p0, p1):
        n = max(2, int(math.dist(p0, p1) / HEIGHT * GRID_SIZE * 2))
        for t in range(n + 1):
            x = p0[0] + (p1[0] - p0[0]) * t / n
            y = p0[1] + (p1[1] - p0[1]) * t / n
            i, j = self.cell(x, y)
            if self.inside(i, j):
                self.owner[j, i] = b.id

    def light_at(self, b, x, y):
        p = self.p
        dx, dy = self.light_x - x, self.light_y - y
        dist = math.hypot(dx, dy)
        if dist < 1e-6:
            return 1.0
        light = 1.0 / (1.0 + p["falloff"] * (dist / WIDTH) ** 2)
        reach = min(dist, math.hypot(WIDTH, HEIGHT))
        s = p["ray_start"]
        while s < reach:
            rx, ry = x + dx / dist * s, y + dy / dist * s
            if 0 <= rx < WIDTH and 0 <= ry < HEIGHT:
                i, j = self.cell(rx, ry)
                other_id = int(self.owner[j, i])
                if other_id >= 0 and other_id not in b.family:
                    light *= math.exp(-p["shade"] * p["ray_step"])
            s += p["ray_step"]
        return light

    def blocked(self, b, x, y):
        i, j = self.cell(x, y)
        if not (1 <= i < GRID_SIZE - 1 and 1 <= j < GRID_SIZE - 1):
            return True
        for yy in range(j - 1, j + 2):
            for xx in range(i - 1, i + 2):
                other_id = int(self.owner[yy, xx])
                if other_id < 0 or other_id == b.id or other_id in b.ancestors:
                    continue
                if b.id in self.branches[other_id].ancestors:
                    continue
                return True
        return False

    def terminal_fate(self):
        p = self.p
        total = p["flower"] + p["bloom"]
        if total <= 0:
            return "aborted"
        return "flower" if self.rng.random() < p["flower"] / total else "bloom"

    def spawn_side_bud(self, parent, light):
        p = self.p
        x, y = parent.tip
        side = 1 if len(parent.pts) % 2 else -1
        angle = parent.angle + side * self.rng.uniform(math.radians(30), math.radians(70))
        p_abort = p["abort"] * (1.0 - light)
        r = self.rng.random()
        if r < p_abort:
            return
        if r < p_abort + p["flower"] + p["bloom"]:
            state = "flower" if r < p_abort + p["flower"] else "bloom"
            bud = self.add_branch(x, y, angle, parent.order + 1, parent)
            bud.pts.append((x + 0.2 * math.cos(angle), y + 0.2 * math.sin(angle)))
            bud.state = state
        else:
            self.add_branch(x, y, angle, parent.order + 1, parent)

    def grow(self, b):
        p = self.p
        x, y = b.tip
        light = self.light_at(b, x, y)
        target = math.atan2(self.light_y - y, self.light_x - x)
        diff = (target - b.angle + math.pi) % (2 * math.pi) - math.pi
        b.angle += p["bend"] * diff + self.rng.gauss(0, p["wobble"])
        step = p["max_length"] * (p["base_growth"] + p["growth_factor"] * light)
        if b.order > 0:
            step *= 1.0 - p["apical_factor"]
        nx, ny = x + step * math.cos(b.angle), y + step * math.sin(b.angle)
        if light < p["min_light"] or self.blocked(b, nx, ny):
            b.state = "aborted"
            return
        p0, p1 = (x, y), (nx, ny)
        b.pts.append(p1)
        b.length += step
        b.age += 1
        self.stamp(b, p0, p1)
        if b.age >= p["max_age"] or (b.order > 0 and b.length >= p["max_length"]):
            b.state = self.terminal_fate()
        else:
            self.spawn_side_bud(b, light)

    def step(self):
        for b in list(self.branches):
            if b.state == "active":
                self.grow(b)
        if len(self.branches) > MAX_BRANCHES:
            raise RuntimeError(
                f"Simulation exceeded {MAX_BRANCHES:,} branches. "
                "Reduce cycle count or bud probabilities."
            )

    def run(self):
        for _ in range(self.p["cycles"]):
            self.step()
        return self


def render_simulation(ax, sim):
    p = sim.p
    ax.clear()
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(min(-1, sim.light_x - 1), max(WIDTH + 1, sim.light_x + 1))
    ax.set_ylim(min(-1, sim.light_y - 1), max(HEIGHT + 1, sim.light_y + 1))
    ax.plot([0, WIDTH, WIDTH, 0, 0], [0, 0, HEIGHT, HEIGHT, 0],
            color=(0.8, 0.8, 0.8), linewidth=0.8, linestyle="--")
    for b in sim.branches:
        if len(b.pts) < 2:
            continue
        xs, ys = zip(*b.pts)
        stalk = b.state in ("flower", "bloom") and b.length == 0
        lw = 1.0 if stalk else max(0.8, 6.0 * 0.6 ** b.order)
        ax.plot(xs, ys, color=(0.1, 0.1, 0.1), linewidth=lw, solid_capstyle="round")
        if b.state in ("flower", "bloom"):
            color = (1, 0, 0) if b.state == "flower" else (1, 1, 0)
            ax.add_patch(Circle(b.tip, 0.09, facecolor=color,
                                edgecolor=(0.4, 0.3, 0), linewidth=0.5, alpha=0.85, zorder=3))
    ax.plot([sim.light_x], [sim.light_y], marker="*", markersize=18,
            markerfacecolor="gold", markeredgecolor="darkorange", zorder=5)
    ax.set_title(f"Light at ({sim.light_x:.1f}, {sim.light_y:.1f})")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Light-influenced tree growth")
        self.geometry("1250x820")
        self.minsize(950, 650)
        self.vars = {}
        self.last_sim = None
        self._build_ui()
        self.run_simulation()

    def _build_ui(self):
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)
        panel = ttk.Frame(outer, padding=(0, 0, 12, 0))
        panel.pack(side="left", fill="y")
        plot_frame = ttk.Frame(outer)
        plot_frame.pack(side="left", fill="both", expand=True)

        settings = [
            ("light_x", "Light X", -4, 16, 6, 0.5),
            ("light_y", "Light Y", -4, 20, 14, 0.5),
            ("cycles", "Growth cycles", 1, 35, 35, 1),
            ("falloff", "Light falloff", 0, 3, 0.5, 0.1),
            ("shade", "Shade strength", 0, 5, 2.5, 0.1),
            ("min_light", "Minimum light", 0, 0.5, 0.05, 0.01),
            ("bend", "Light bending", 0, 1, 0.15, 0.05),
            ("wobble", "Directional wobble", 0, 0.5, 0.1, 0.02),
            ("abort", "Bud abortion", 0, 0.9, 0.35, 0.05),
            ("flower", "Flower probability", 0, 0.8, 0.25, 0.05),
            ("bloom", "Bloom probability", 0, 0.8, 0.3, 0.05),
            ("max_age", "Maximum age", 1, 35, 14, 1),
            ("max_length", "Maximum side-branch length", 0.5, 6, 4, 0.25),
        ]
        ttk.Label(panel, text="Light-model parameters", font=("", 12, "bold")).pack(anchor="w", pady=(0, 8))
        for key, label, lo, hi, default, step in settings:
            row = ttk.Frame(panel)
            row.pack(fill="x", pady=3)
            var = tk.DoubleVar(value=default)
            self.vars[key] = var
            ttk.Label(row, text=label, width=25).pack(side="left")
            scale = ttk.Scale(row, from_=lo, to=hi, variable=var, orient="horizontal", length=130)
            scale.pack(side="left", fill="x", expand=True)
            value = ttk.Label(row, width=6, text=str(default))
            value.pack(side="left")
            def update_label(v=var, label_widget=value, st=step):
                n = v.get()
                label_widget.configure(text=f"{n:.2f}".rstrip("0").rstrip(".") if st < 1 else f"{n:.0f}")
            scale.configure(command=lambda _x, f=update_label: f())
        self.seed_var = tk.StringVar(value="42")
        seedrow = ttk.Frame(panel)
        seedrow.pack(fill="x", pady=(8, 4))
        ttk.Label(seedrow, text="Random seed", width=25).pack(side="left")
        ttk.Entry(seedrow, textvariable=self.seed_var, width=12).pack(side="left")

        ttk.Button(panel, text="Run / Regrow", command=self.run_simulation).pack(fill="x", pady=(8, 4))
        ttk.Button(panel, text="New random seed", command=self.new_seed).pack(fill="x", pady=4)
        ttk.Button(panel, text="Export PNG", command=self.export_png).pack(fill="x", pady=4)
        self.status = ttk.Label(panel, text="", wraplength=320, justify="left")
        self.status.pack(anchor="w", pady=8)

        self.fig = Figure(figsize=(8, 8), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        toolbar = NavigationToolbar2Tk(self.canvas, plot_frame)
        toolbar.update()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.canvas.mpl_connect("button_press_event", self.on_click)
        self.bind("r", lambda _e: self.new_seed())

    def parameters(self):
        p = dict(DEFAULTS)
        for key, var in self.vars.items():
            value = var.get()
            p[key] = int(round(value)) if key in ("cycles", "max_age") else float(value)
        p["light_x"] = self.vars["light_x"].get()
        p["light_y"] = self.vars["light_y"].get()
        return p

    def run_simulation(self):
        try:
            seed = int(self.seed_var.get())
            if seed < 0:
                raise ValueError("Seed must be a nonnegative integer.")
            p = self.parameters()
            sim = Simulation(p, seed).run()
            self.last_sim = sim
            render_simulation(self.ax, sim)
            self.canvas.draw()
            states = [b.state for b in sim.branches]
            self.status.configure(
                text=(f"Seed {seed}: {len(states)} branches, "
                      f"{states.count('flower')} flowers, {states.count('bloom')} blooms, "
                      f"{states.count('aborted')} aborted.")
            )
        except Exception as err:
            self.status.configure(text=str(err), foreground="#b00020")

    def new_seed(self):
        self.seed_var.set(str(random.randrange(10**6)))
        self.run_simulation()

    def on_click(self, event):
        if event.inaxes is not self.ax or event.xdata is None or event.ydata is None:
            return
        self.vars["light_x"].set(max(-4, min(16, event.xdata)))
        self.vars["light_y"].set(max(-4, min(20, event.ydata)))
        self.run_simulation()

    def export_png(self):
        path = filedialog.asksaveasfilename(
            title="Export light-influenced tree", defaultextension=".png",
            filetypes=[("PNG image", "*.png")]
        )
        if path:
            self.fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
            self.status.configure(text=f"Saved image to {path}")


if __name__ == "__main__":
    App().mainloop()
