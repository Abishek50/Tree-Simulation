"""Simple recursive L-system tree generator with a Tkinter GUI.

Features:
- Presets and editable axiom/rules
- Turn angle and iteration controls
- Recursive symbol expansion with a safety cap
- Turtle interpretation of F/G/f/+/-/[/]
- Branch-depth coloring, branch statistics, repeatable redraws, and PNG export
"""

import math
import tkinter as tk
from functools import lru_cache
from tkinter import ttk, filedialog, messagebox

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.collections import LineCollection
from matplotlib.figure import Figure

MAX_SYMBOLS = 250_000
MAX_ITERATIONS = 12

PRESETS = {
    "Simple branching tree": ("F", {"F": "F[+F]F[-F]F"}, 25.7, 4),
    "Sparse tree": ("F", {"F": "F[+F]F[-F][F]"}, 20.0, 4),
    "Bushy tree": ("F", {"F": "FF-[-F+F+F]+[+F-F-F]"}, 22.5, 4),
    "Airy tree": ("X", {"X": "F[+X]F[-X]+X", "F": "FF"}, 20.0, 6),
    "Dense tree": ("X", {"X": "F[+X][-X]FX", "F": "FF"}, 25.7, 6),
    "Fractal plant": ("X", {"X": "F-[[X]+X]+F[+FX]-X", "F": "FF"}, 22.5, 5),
}
CUSTOM = "Custom"


def parse_rule(line):
    sep = "->" if "->" in line else "="
    if sep not in line:
        raise ValueError("Use the form F=FF or F->FF.")
    left, right = (part.strip().replace(" ", "") for part in line.split(sep, 1))
    if len(left) != 1:
        raise ValueError("The left side must be a single symbol.")
    return left, right


def final_length(axiom, rules, iterations, limit=MAX_SYMBOLS):
    @lru_cache(maxsize=None)
    def size(symbol, depth):
        if depth == 0:
            return 1
        total = 0
        for c in rules.get(symbol, symbol):
            total += size(c, depth - 1)
            if total > limit:
                break
        return total

    total = 0
    for c in axiom:
        total += size(c, iterations)
        if total > limit:
            break
    return total


def expand(axiom, rules, iterations):
    @lru_cache(maxsize=None)
    def grow(symbol, depth):
        if depth == 0:
            return symbol
        return "".join(grow(c, depth - 1) for c in rules.get(symbol, symbol))
    return "".join(grow(c, iterations) for c in axiom)


def interpret(commands, angle_deg, step=1.0):
    x, y, heading = 0.0, 0.0, 90.0
    stack = []
    segments, depths = [], []
    for c in commands:
        if c in "FGf":
            nx = x + step * math.cos(math.radians(heading))
            ny = y + step * math.sin(math.radians(heading))
            if c != "f":
                segments.append(((x, y), (nx, ny)))
                depths.append(len(stack))
            x, y = nx, ny
        elif c == "+":
            heading += angle_deg
        elif c == "-":
            heading -= angle_deg
        elif c == "[":
            stack.append((x, y, heading))
        elif c == "]" and stack:
            x, y, heading = stack.pop()
    return segments, depths


def draw(ax, segments, depths, title):
    ax.clear()
    ax.axis("off")
    ax.set_title(title, fontsize=10)
    if not segments:
        return
    max_depth = max(depths) or 1
    trunk, leaf = (0.36, 0.22, 0.08), (0.15, 0.65, 0.15)
    colors = [
        tuple(a + (b - a) * d / max_depth for a, b in zip(trunk, leaf))
        for d in depths
    ]
    widths = [max(0.4, 2.4 * 0.8 ** d) for d in depths]
    ax.add_collection(LineCollection(
        segments, colors=colors, linewidths=widths, capstyle="round"
    ))
    ax.autoscale()
    ax.set_aspect("equal", adjustable="datalim")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Simple Recursive Tree — L-system")
        self.geometry("1150x760")
        self.minsize(850, 560)

        self.preset_var = tk.StringVar()
        self.axiom_var = tk.StringVar()
        self.angle_var = tk.StringVar()
        self.iter_var = tk.StringVar()
        self.seed_var = tk.StringVar(value="42")  # retained for cross-model experiment records
        self._build_controls()
        self._build_plot()
        self.load_preset(next(iter(PRESETS)))
        self.draw_tree()

    def _build_controls(self):
        panel = ttk.Frame(self, padding=12)
        panel.pack(side="left", fill="y")
        ttk.Label(panel, text="Preset").pack(anchor="w")
        combo = ttk.Combobox(
            panel, textvariable=self.preset_var, state="readonly",
            values=[CUSTOM] + list(PRESETS), width=29
        )
        combo.pack(fill="x", pady=(0, 8))
        combo.bind("<<ComboboxSelected>>", lambda _e: self.on_preset_chosen())

        ttk.Label(panel, text="Axiom").pack(anchor="w")
        axiom = ttk.Entry(panel, textvariable=self.axiom_var)
        axiom.pack(fill="x", pady=(0, 8))
        ttk.Label(panel, text="Rules (one per line)").pack(anchor="w")
        self.rules_text = tk.Text(panel, width=32, height=7, font="TkFixedFont", wrap="none")
        self.rules_text.pack(fill="x", pady=(0, 8))

        row = ttk.Frame(panel)
        row.pack(fill="x", pady=(0, 8))
        left = ttk.Frame(row)
        left.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ttk.Label(left, text="Angle (degrees)").pack(anchor="w")
        angle = ttk.Entry(left, textvariable=self.angle_var, width=10)
        angle.pack(fill="x")
        right = ttk.Frame(row)
        right.pack(side="left", fill="x", expand=True)
        ttk.Label(right, text="Iterations").pack(anchor="w")
        iters = ttk.Spinbox(right, textvariable=self.iter_var, from_=0,
                            to=MAX_ITERATIONS, width=6)
        iters.pack(fill="x")

        ttk.Label(panel, text="Experiment seed (for shared records)").pack(anchor="w", pady=(4, 0))
        seed = ttk.Entry(panel, textvariable=self.seed_var)
        seed.pack(fill="x", pady=(0, 8))
        ttk.Label(panel, text="The L-system is deterministic; the seed does not change its tree.",
                  wraplength=260).pack(anchor="w", pady=(0, 8))

        ttk.Button(panel, text="Draw tree (Ctrl+Enter)", command=self.draw_tree).pack(fill="x", pady=(0, 6))
        ttk.Button(panel, text="Export PNG", command=self.export_png).pack(fill="x", pady=(0, 6))
        self.status = ttk.Label(panel, text="", wraplength=260, justify="left")
        self.status.pack(anchor="w", pady=(0, 12))

        legend = ("Symbols\nF, G   draw forward\nf      move without drawing\n"
                  "+ / -  turn left / right\n[      start a branch\n"
                  "]      return to saved position\nother  may appear in rules")
        ttk.Label(panel, text=legend, font="TkFixedFont", justify="left").pack(anchor="w")

        for widget in (axiom, angle, iters, seed):
            widget.bind("<Return>", lambda _e: self.draw_tree())
        self.bind("<Control-Return>", lambda _e: self.draw_tree())

    def _build_plot(self):
        frame = ttk.Frame(self)
        frame.pack(side="left", fill="both", expand=True)
        self.fig = Figure(figsize=(7, 7), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=frame)
        toolbar = NavigationToolbar2Tk(self.canvas, frame)
        toolbar.update()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def set_status(self, text, error=False):
        self.status.configure(text=text, foreground="#b00020" if error else "#222222")

    def load_preset(self, name):
        axiom, rules, angle, iterations = PRESETS[name]
        self.preset_var.set(name)
        self.axiom_var.set(axiom)
        self.angle_var.set(str(angle))
        self.iter_var.set(str(iterations))
        self.rules_text.delete("1.0", "end")
        self.rules_text.insert("1.0", "\n".join(f"{k}={v}" for k, v in rules.items()))

    def on_preset_chosen(self):
        name = self.preset_var.get()
        if name in PRESETS:
            self.load_preset(name)
            self.draw_tree()

    def read_inputs(self):
        axiom = self.axiom_var.get().replace(" ", "")
        if not axiom:
            raise ValueError("The axiom cannot be empty.")
        rules = {}
        for number, line in enumerate(self.rules_text.get("1.0", "end").splitlines(), 1):
            if line.strip():
                try:
                    symbol, replacement = parse_rule(line.strip())
                except ValueError as err:
                    raise ValueError(f"Rule on line {number}: {err}")
                rules[symbol] = replacement
        try:
            angle = float(self.angle_var.get())
        except ValueError:
            raise ValueError("Angle must be a number from -360 to 360.")
        if not math.isfinite(angle) or not -360 <= angle <= 360:
            raise ValueError("Angle must be a number from -360 to 360.")
        try:
            iterations = int(self.iter_var.get())
        except ValueError:
            raise ValueError(f"Iterations must be a whole number from 0 to {MAX_ITERATIONS}.")
        if not 0 <= iterations <= MAX_ITERATIONS:
            raise ValueError(f"Iterations must be a whole number from 0 to {MAX_ITERATIONS}.")
        return axiom, rules, angle, iterations

    def draw_tree(self):
        try:
            axiom, rules, angle, iterations = self.read_inputs()
            total = final_length(axiom, rules, iterations)
            if total > MAX_SYMBOLS:
                raise ValueError(
                    f"That would create more than {MAX_SYMBOLS:,} symbols. "
                    "Lower iterations or simplify the rules."
                )
            commands = expand(axiom, rules, iterations)
            segments, depths = interpret(commands, angle)
            name = next(
                (n for n, p in PRESETS.items()
                 if p == (axiom, rules, angle, iterations)),
                CUSTOM
            )
            self.preset_var.set(name)
            draw(self.ax, segments, depths,
                 f"{name}: {iterations} iterations, {angle:g}°")
            self.canvas.draw()
            self.set_status(
                f"{len(commands):,} symbols, {len(segments):,} drawn segments."
                if segments else "Nothing to draw: no F or G symbols."
            )
        except ValueError as err:
            self.set_status(str(err), error=True)

    def export_png(self):
        path = filedialog.asksaveasfilename(
            title="Export L-system tree",
            defaultextension=".png",
            filetypes=[("PNG image", "*.png")]
        )
        if path:
            self.fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
            self.set_status(f"Saved image to {path}")


if __name__ == "__main__":
    App().mainloop()
