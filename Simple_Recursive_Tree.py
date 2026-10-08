"""
L-system (Lindenmayer system) tree generator with a GUI.

Pick a preset or type your own growth instructions, then press Draw:

  Axiom        the starting string, e.g.  F
  Rules        how each symbol is rewritten, one per line, e.g.  F=F[+F]F[-F]F
  Angle        how far each + or - turns, in degrees
  Iterations   how many times the rules are applied

Drawing symbols
  F or G   draw a line forward           f   move forward without drawing
  +        turn left                     -   turn right
  [        remember position + heading   ]   jump back to the remembered one
  Any other symbol (like X) does nothing when drawing, but can be used in rules.

Where the recursion is: expand() rewrites a symbol by calling itself on every
symbol of its replacement, one level down, until it reaches depth 0. The
brackets [ ] act like function calls: "[" starts a sub-branch, "]" returns to
the parent, which interpret() does with its stack.
"""
import math
import tkinter as tk
from functools import lru_cache
from tkinter import ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.collections import LineCollection
from matplotlib.figure import Figure

MAX_SYMBOLS = 9_000_000    # refuse to build strings longer than this
MAX_ITERATIONS = 12

# name -> (axiom, rules, angle in degrees, iterations)
# (classic examples from Prusinkiewicz & Lindenmayer, "The Algorithmic Beauty of Plants")
PRESETS = {
    "Simple branching tree": ("F", {"F": "F[+F]F[-F]F"}, 25.7, 4),
    "Sparse tree": ("F", {"F": "F[+F]F[-F][F]"}, 20.0, 4),
    "Bushy tree": ("F", {"F": "FF-[-F+F+F]+[+F-F-F]"}, 22.5, 4),
    "Airy tree": ("X", {"X": "F[+X]F[-X]+X", "F": "FF"}, 20.0, 6),
    "Dense tree": ("X", {"X": "F[+X][-X]FX", "F": "FF"}, 25.7, 6),
    "Fractal plant": ("X", {"X": "F-[[X]+X]+F[+FX]-X", "F": "FF"}, 22.5, 5),
}
CUSTOM = "Custom"


# ---------------------------------------------------------------- L-system

def parse_rule(line):
    """'F=FF+[+F-F]' or 'F->FF+[+F-F]'  ->  ('F', 'FF+[+F-F]')"""
    sep = "->" if "->" in line else "="
    if sep not in line:
        raise ValueError("use the form  F=FF")
    left, right = (part.strip().replace(" ", "") for part in line.split(sep, 1))
    if len(left) != 1:
        raise ValueError("the left side must be a single symbol")
    return left, right


def final_length(axiom, rules, iterations):
    """How many symbols the expanded string will have (without building it)."""
    @lru_cache(maxsize=None)
    def size(symbol, depth):
        if depth == 0:
            return 1
        return sum(size(c, depth - 1) for c in rules.get(symbol, symbol))

    return sum(size(c, iterations) for c in axiom)


def expand(axiom, rules, iterations):
    """Apply the rules `iterations` times, recursively."""
    @lru_cache(maxsize=None)
    def grow(symbol, depth):
        if depth == 0:
            return symbol
        # replace the symbol, then grow every symbol of the replacement one level less
        return "".join(grow(c, depth - 1) for c in rules.get(symbol, symbol))

    return "".join(grow(c, iterations) for c in axiom)


def interpret(commands, angle_deg, step=1.0):
    """Turn the symbol string into line segments, like a turtle drawing."""
    x, y, heading = 0.0, 0.0, 90.0           # start at the origin, pointing up
    stack = []
    segments, depths = [], []

    for c in commands:
        if c in "FGf":
            nx = x + step * math.cos(math.radians(heading))
            ny = y + step * math.sin(math.radians(heading))
            if c != "f":
                segments.append(((x, y), (nx, ny)))
                depths.append(len(stack))     # how many branches deep we are
            x, y = nx, ny
        elif c == "+":
            heading += angle_deg
        elif c == "-":
            heading -= angle_deg
        elif c == "[":
            stack.append((x, y, heading))
        elif c == "]":
            if stack:
                x, y, heading = stack.pop()
    return segments, depths


# ---------------------------------------------------------------- drawing

def draw(ax, segments, depths, title):
    """Draw the segments on a matplotlib axis, brown trunk to green tips."""
    ax.clear()
    ax.axis("off")
    ax.set_title(title, fontsize=10)
    if not segments:
        return

    max_depth = max(depths) or 1
    trunk, leaf = (0.36, 0.22, 0.08), (0.15, 0.65, 0.15)
    colors = [tuple(a + (b - a) * d / max_depth for a, b in zip(trunk, leaf))
              for d in depths]
    widths = [max(0.4, 2.4 * 0.8 ** d) for d in depths]

    ax.add_collection(LineCollection(segments, colors=colors, linewidths=widths,
                                     capstyle="round"))
    ax.autoscale()
    ax.set_aspect("equal")


# ---------------------------------------------------------------- GUI

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("L-system tree")
        self.geometry("1050x720")
        self.minsize(820, 560)

        self.preset_var = tk.StringVar()
        self.axiom_var = tk.StringVar()
        self.angle_var = tk.StringVar()
        self.iter_var = tk.StringVar()

        self.build_controls()
        self.build_plot()

        self.load_preset(next(iter(PRESETS)))
        self.draw_tree()

    # ---- layout ----
    def build_controls(self):
        panel = ttk.Frame(self, padding=12)
        panel.pack(side="left", fill="y")

        ttk.Label(panel, text="Preset").pack(anchor="w")
        combo = ttk.Combobox(panel, textvariable=self.preset_var, state="readonly",
                             values=[CUSTOM] + list(PRESETS), width=30)
        combo.pack(fill="x", pady=(0, 10))
        combo.bind("<<ComboboxSelected>>", lambda e: self.on_preset_chosen())

        ttk.Label(panel, text="Axiom").pack(anchor="w")
        axiom = ttk.Entry(panel, textvariable=self.axiom_var)
        axiom.pack(fill="x", pady=(0, 10))

        ttk.Label(panel, text="Rules (one per line, e.g. F=FF)").pack(anchor="w")
        self.rules_text = tk.Text(panel, width=32, height=7, font="TkFixedFont", wrap="none")
        self.rules_text.pack(fill="x", pady=(0, 10))

        row = ttk.Frame(panel)
        row.pack(fill="x", pady=(0, 10))
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

        ttk.Button(panel, text="Draw  (Ctrl+Enter)", command=self.draw_tree).pack(fill="x", pady=(0, 8))

        self.status = ttk.Label(panel, text="", wraplength=260, justify="left")
        self.status.pack(anchor="w", pady=(0, 12))

        legend = ("Symbols\n"
                  "F, G   draw forward\n"
                  "f      move without drawing\n"
                  "+ / -  turn left / right\n"
                  "[      start a branch\n"
                  "]      end it, go back\n"
                  "other  (e.g. X) does nothing")
        ttk.Label(panel, text=legend, font="TkFixedFont", justify="left").pack(anchor="w")

        for widget in (axiom, angle, iters):
            widget.bind("<Return>", lambda e: self.draw_tree())
        self.bind("<Control-Return>", lambda e: self.draw_tree())

    def build_plot(self):
        frame = ttk.Frame(self)
        frame.pack(side="left", fill="both", expand=True)
        self.fig = Figure(figsize=(7, 7))
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=frame)
        NavigationToolbar2Tk(self.canvas, frame).update()      # zoom / pan / save
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    # ---- behavior ----
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
        """Read and validate every field. Raises ValueError with a friendly message."""
        axiom = self.axiom_var.get().replace(" ", "")
        if not axiom:
            raise ValueError("The axiom can't be empty.")

        rules = {}
        for number, line in enumerate(self.rules_text.get("1.0", "end").splitlines(), 1):
            if line.strip():
                try:
                    symbol, replacement = parse_rule(line.strip())
                except ValueError as err:
                    raise ValueError(f"Rule on line {number}: {err}.")
                rules[symbol] = replacement

        try:
            angle = float(self.angle_var.get())
        except ValueError:
            angle = math.nan
        if not -360 <= angle <= 360:          
            raise ValueError("Angle must be a number from -360 to 360.")


        try:
            iterations = int(self.iter_var.get())
        except ValueError:
            iterations = -1
        if not 0 <= iterations <= MAX_ITERATIONS:
            raise ValueError(f"Iterations must be a whole number from 0 to {MAX_ITERATIONS}.")

        return axiom, rules, angle, iterations

    def draw_tree(self):
        try:
            axiom, rules, angle, iterations = self.read_inputs()
            total = final_length(axiom, rules, iterations)
            if total > MAX_SYMBOLS:
                raise ValueError(f"That would create {total:,} symbols (limit {MAX_SYMBOLS:,}). "
                                 "Lower the iterations or simplify the rules.")
        except ValueError as err:
            self.set_status(str(err), error=True)
            return

        # name the tree after a preset if the fields still match one exactly
        name = next((n for n, p in PRESETS.items() if p == (axiom, rules, angle, iterations)), CUSTOM)
        self.preset_var.set(name)

        self.set_status("Drawing...")
        self.update_idletasks()

        commands = expand(axiom, rules, iterations)
        segments, depths = interpret(commands, angle)
        draw(self.ax, segments, depths, f"{name}: {iterations} iterations, {angle:g} deg")
        self.canvas.draw()

        if segments:
            self.set_status(f"{len(commands):,} symbols, {len(segments):,} branches")
        else:
            self.set_status("Nothing to draw: the result has no F or G.", error=True)


if __name__ == "__main__":
    App().mainloop()