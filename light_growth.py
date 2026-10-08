"""
Tree growth simulation: buds compete for light and space on a grid.

How it works
------------
* Every Branch has a growing tip and extends by one internode per cycle.
* At each new node a side bud may appear. Its fate is rolled once:
  abort (more likely in shade), flower, bloom, or grow into a new branch.
* A branch ends in a flower/bloom after MAX_AGE cycles (side branches also
  stop at MAX_BRANCH_LENGTH). It aborts early if it runs into another
  branch, hits the edge of the grid, or runs out of light.
* Light comes from a point source at (LIGHT_X, LIGHT_Y). Tips bend toward it,
  and the light a tip receives drops with the amount of other wood sitting on
  the straight line between the tip and the light (plus distance falloff).
* Click on the plot to move the light and regrow the same tree (same seed),
  or press "r" for a different tree.
"""
import math
import random

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle

# --- Parameters ---
WIDTH = 12.0
HEIGHT = 12.0
GRID_SIZE = 120            # cells per side
MAX_CYCLES = 35
SEED = None                # set to an int for a repeatable tree

# --- Tree parameters ---
MAX_BRANCH_LENGTH = 4.0    # side branches stop growing at this length
BASE_GROWTH = 0.12         # growth per cycle, as a fraction of MAX_BRANCH_LENGTH
GROWTH_FACTOR = 0.025      # extra growth in full light (same units)
APICAL_FACTOR = 0.4        # side branches grow (1 - this) as fast as the leader
ABORT_PROB = 0.35          # new side bud dies; scaled by shade, so 0 in full light
FLOWER_PROB = 0.25         # new side bud becomes a flower
BLOOM_PROB = 0.30          # new side bud becomes a bloom
                           # ...whatever probability is left grows into a branch
MAX_AGE = 14               # cycles a branch grows before ending in a flower/bloom
NUM_TREES = 1

# --- Light model ---
LIGHT_X = 6.0              # light position in world units; can be outside the 0..WIDTH box
LIGHT_Y = 14.0
LIGHT_FALLOFF = 0.5        # 0 = same brightness at any distance, higher = dimmer when far
SHADE_STRENGTH = 2.5       # light lost per world unit of wood the ray passes through
MIN_LIGHT = 0.05           # tips in less light than this give up
RAY_STEP = 0.08            # world units between shadow samples along the ray
RAY_START = 0.15           # skip the start of the ray so a tip doesn't shade itself

# --- Drawing ---
TRUNK_COLOR = (0.1, 0.1, 0.1)
TRUNK_WIDTH = 0.6          # trunk line width = TRUNK_WIDTH * 10 pt, tapering per order
TRUNK_ANGLE = 90.0         # degrees, 90 = straight up
FLOWER_COLOR = (1.0, 0.0, 0.0)
BLOOM_COLOR = (1.0, 1.0, 0.0)
FLOWER_RADIUS = 0.09


class Branch:
    def __init__(self, bid, x, y, angle, order=0, parent=None):
        self.id = bid
        self.pts = [(x, y)]
        self.angle = angle                 # radians
        self.order = order                 # 0 = trunk, 1 = side branch, ...
        self.age = 0
        self.length = 0.0
        self.state = "active"              # active | aborted | flower | bloom
        self.ancestors = set() if parent is None else parent.ancestors | {parent.id}
        self.family = np.fromiter(self.ancestors | {bid}, dtype=int)   # me + ancestors

    @property
    def tip(self):
        return self.pts[-1]


class Simulation:
    def __init__(self, light_x=LIGHT_X, light_y=LIGHT_Y):
        self.light_x = light_x
        self.light_y = light_y
        self.branches = []
        self.owner = np.full((GRID_SIZE, GRID_SIZE), -1, dtype=int)  # branch id per cell, -1 = empty
        for k in range(NUM_TREES):
            x = WIDTH * (k + 1) / (NUM_TREES + 1)
            self.add_branch(x, 0.0, math.radians(TRUNK_ANGLE))

    # ---- grid helpers ----
    @staticmethod
    def cell(x, y):
        return int(x / WIDTH * GRID_SIZE), int(y / HEIGHT * GRID_SIZE)

    @staticmethod
    def inside(i, j):
        return 0 <= i < GRID_SIZE and 0 <= j < GRID_SIZE

    def add_branch(self, x, y, angle, order=0, parent=None):
        b = Branch(len(self.branches), x, y, angle, order, parent)
        self.branches.append(b)
        return b

    def stamp(self, b, p0, p1):
        """Mark the cells along a new segment as occupied by branch b."""
        n = max(2, int(math.dist(p0, p1) / HEIGHT * GRID_SIZE * 2))
        for t in range(n + 1):
            x = p0[0] + (p1[0] - p0[0]) * t / n
            y = p0[1] + (p1[1] - p0[1]) * t / n
            i, j = self.cell(x, y)
            if self.inside(i, j):
                self.owner[j, i] = b.id

    def light_at(self, b, x, y):
        """Light (0..1) reaching (x, y): distance falloff times how much *other*
        wood sits on the straight line from the point to the light."""
        dx, dy = self.light_x - x, self.light_y - y
        dist = math.hypot(dx, dy)
        if dist < 1e-6:
            return 1.0
        light = 1.0 / (1.0 + LIGHT_FALLOFF * (dist / WIDTH) ** 2)

        reach = min(dist, math.hypot(WIDTH, HEIGHT))     # no wood exists beyond the box
        s = np.arange(RAY_START, reach, RAY_STEP)
        xs = x + dx / dist * s
        ys = y + dy / dist * s
        ok = (xs >= 0) & (xs < WIDTH) & (ys >= 0) & (ys < HEIGHT)
        i = (xs[ok] / WIDTH * GRID_SIZE).astype(int)
        j = (ys[ok] / HEIGHT * GRID_SIZE).astype(int)
        ids = self.owner[j, i]
        ids = ids[ids >= 0]
        if ids.size:
            ids = ids[~np.isin(ids, b.family)]           # a branch doesn't shade itself
        return light * math.exp(-SHADE_STRENGTH * ids.size * RAY_STEP)

    def blocked(self, b, x, y):
        """True if (x, y) is off the grid or touches a branch that isn't family."""
        i, j = self.cell(x, y)
        if not (1 <= i < GRID_SIZE - 1 and 1 <= j < GRID_SIZE - 1):
            return True
        for other in np.unique(self.owner[j - 1:j + 2, i - 1:i + 2]):
            other = int(other)
            if other < 0 or other == b.id or other in b.ancestors:
                continue
            if b.id in self.branches[other].ancestors:   # my own descendants
                continue
            return True
        return False

    # ---- growth ----
    @staticmethod
    def terminal_fate():
        p = FLOWER_PROB / (FLOWER_PROB + BLOOM_PROB)
        return "flower" if random.random() < p else "bloom"

    def grow(self, b):
        x, y = b.tip
        light = self.light_at(b, x, y)

        # bend toward the light source with a little wobble
        target = math.atan2(self.light_y - y, self.light_x - x)
        diff = (target - b.angle + math.pi) % (2 * math.pi) - math.pi
        b.angle += 0.15 * diff + random.gauss(0, 0.10)

        step = MAX_BRANCH_LENGTH * (BASE_GROWTH + GROWTH_FACTOR * light)
        if b.order > 0:
            step *= 1.0 - APICAL_FACTOR          # apical dominance
        nx = x + step * math.cos(b.angle)
        ny = y + step * math.sin(b.angle)

        if light < MIN_LIGHT or self.blocked(b, nx, ny):
            b.state = "aborted"
            return

        b.pts.append((nx, ny))
        b.length += step
        b.age += 1
        self.stamp(b, (x, y), (nx, ny))

        too_old = b.age >= MAX_AGE
        too_long = b.order > 0 and b.length >= MAX_BRANCH_LENGTH
        if too_old or too_long:
            b.state = self.terminal_fate()
        else:
            self.spawn_side_bud(b, light)

    def spawn_side_bud(self, parent, light):
        x, y = parent.tip
        side = 1 if len(parent.pts) % 2 else -1       # alternate left / right
        angle = parent.angle + side * random.uniform(math.radians(30), math.radians(70))

        p_abort = ABORT_PROB * (1.0 - light)           # shade kills buds
        r = random.random()
        if r < p_abort:
            return                                      # aborted: nothing to draw
        if r < p_abort + FLOWER_PROB + BLOOM_PROB:
            state = "flower" if r < p_abort + FLOWER_PROB else "bloom"
            bud = self.add_branch(x, y, angle, parent.order + 1, parent)
            bud.pts.append((x + 0.2 * math.cos(angle), y + 0.2 * math.sin(angle)))  # short stalk
            bud.state = state
        else:
            self.add_branch(x, y, angle, parent.order + 1, parent)   # grows next cycle

    def step(self):
        for b in list(self.branches):                  # snapshot: new buds start next cycle
            if b.state == "active":
                self.grow(b)

    # ---- drawing ----
    def draw(self, ax):
        for b in self.branches:
            if len(b.pts) < 2:
                continue
            xs, ys = zip(*b.pts)
            stalk = b.state in ("flower", "bloom") and b.length == 0
            lw = 1.0 if stalk else max(0.8, TRUNK_WIDTH * 10 * 0.6 ** b.order)
            ax.plot(xs, ys, color=TRUNK_COLOR, linewidth=lw, solid_capstyle="round")
            if b.state in ("flower", "bloom"):
                color = FLOWER_COLOR if b.state == "flower" else BLOOM_COLOR
                ax.add_patch(Circle(b.tip, FLOWER_RADIUS, facecolor=color,
                                    edgecolor=(0.4, 0.3, 0.0), linewidth=0.5,
                                    alpha=0.85, zorder=3))


def run(light_x, light_y, seed):
    random.seed(seed)
    sim = Simulation(light_x, light_y)
    for _ in range(MAX_CYCLES):
        sim.step()
    return sim


def render(ax, sim):
    ax.clear()
    ax.axis("off")
    ax.set_aspect("equal")
    ax.set_xlim(min(-1, sim.light_x - 1), max(WIDTH + 1, sim.light_x + 1))
    ax.set_ylim(min(-1, sim.light_y - 1), max(HEIGHT + 1, sim.light_y + 1))
    # faint outline of the simulated area (branches stop at its edge)
    ax.plot([0, WIDTH, WIDTH, 0, 0], [0, 0, HEIGHT, HEIGHT, 0],
            color=(0.8, 0.8, 0.8), linewidth=0.8, linestyle="--")
    sim.draw(ax)
    ax.plot([sim.light_x], [sim.light_y], marker="*", markersize=26,
            markerfacecolor="gold", markeredgecolor="darkorange", zorder=5)
    ax.set_title(f"light at ({sim.light_x:.1f}, {sim.light_y:.1f})   "
                 "click = move light, r = new tree", fontsize=10)


def main():
    seed = SEED if SEED is not None else random.randrange(10 ** 6)
    state = {"x": LIGHT_X, "y": LIGHT_Y, "seed": seed}

    fig, ax = plt.subplots(figsize=(10, 10))

    def redraw():
        sim = run(state["x"], state["y"], state["seed"])
        states = [b.state for b in sim.branches]
        print(f"light ({state['x']:.1f}, {state['y']:.1f}): {len(states)} branches, "
              f"{states.count('flower')} flowers, {states.count('bloom')} blooms, "
              f"{states.count('aborted')} aborted")
        render(ax, sim)
        fig.canvas.draw_idle()

    def on_click(event):
        toolbar = fig.canvas.toolbar
        if toolbar is not None and toolbar.mode:         # ignore clicks while zooming/panning
            return
        if event.inaxes is ax and event.button == 1:
            state["x"], state["y"] = event.xdata, event.ydata
            redraw()

    def on_key(event):
        if event.key == "r":
            state["seed"] = random.randrange(10 ** 6)
            redraw()

    fig.canvas.mpl_connect("button_press_event", on_click)
    fig.canvas.mpl_connect("key_press_event", on_key)
    redraw()
    plt.show()


if __name__ == "__main__":
    main()