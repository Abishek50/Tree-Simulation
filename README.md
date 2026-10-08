# Tree Simulations

Two different ways to grow a tree on screen, in Python with matplotlib:

1. **Light-controlled tree** (`tree_growth.py`): branches grow toward a movable light, compete for light and space, and die when shaded. Click to move the light and watch the tree respond.
2. **L-system tree** (`lsystem_gui.py`): you type growth instructions (an axiom, rewriting rules, an angle and a number of iterations) into a window, and the tree is drawn from them. A terminal version (`lsystem_tree.py`) does the same with prompts.

## Contents

- [Files](#files)
- [Which one is which](#which-one-is-which)
- [Requirements](#requirements)
- [Part 1: Light-controlled tree](#part-1-light-controlled-tree)
- [Part 2: L-system tree](#part-2-l-system-tree)

## Files

| File | What it is |
|---|---|
| `tree_growth.py` | Light-controlled growth simulation. Click on the plot to move the light. |
| `lsystem_gui.py` | L-system tree generator with a window: preset dropdown and input fields. |
| `lsystem_tree.py` | The same L-system generator driven by terminal prompts instead of a window. |
| `README.md` | This file. |

## Which one is which

| | Light-controlled tree | L-system tree |
|---|---|---|
| Idea | Branches react to their environment (light, shade, neighbors) | A string is rewritten by rules, then drawn |
| Randomness | Yes: wobble, side-bud fates, branch angles | None: the same input always gives the same picture |
| Environment | A point light and a collision grid | None: branches can overlap |
| You control | Light position, seed, growth constants in the code | Axiom, rules, angle, iterations, typed in the window |
| Good for | Seeing how light shapes a tree | Quickly designing and exploring tree shapes from rules |

## Requirements

- Python 3.8 or newer
- `matplotlib` and `numpy` (for `tree_growth.py`); `matplotlib` only (for the L-system files)
- `tkinter`, which `lsystem_gui.py` needs for its window (matplotlib also uses it by default to open plot windows on most systems). It ships with Python on Windows and macOS. On Linux you may need `sudo apt install python3-tk`.

```bash
pip install matplotlib numpy
```

---

# Part 1: Light-controlled tree

A small simulation of a tree growing toward a movable point light. Branches compete for light and space on a grid: branches in the open thrive, shaded ones die, and branches that bump into each other stop. Click on the plot to move the light and watch the tree regrow.

## Quick start

```bash
python tree_growth.py
```

| Input | What it does |
|---|---|
| Left click on the plot | Moves the light there and regrows the tree with the same random seed |
| Press `r` | Grows a different tree (new random seed) |
| `LIGHT_X`, `LIGHT_Y` | Starting position of the light, set at the top of the file |
| `SEED` | Set to an int to get the same tree every run |

Each run prints a summary line, for example `light (6.0, 14.0): 406 branches, 105 flowers, 148 blooms, 150 aborted`.

## The big picture

The world is a `WIDTH x HEIGHT` box (12 x 12 by default) with y pointing up. The tree starts at the bottom edge. Time moves in **cycles** (`MAX_CYCLES = 35`). In every cycle each growing branch tip does the same thing:

1. Measure how much light reaches it.
2. Turn a little toward the light.
3. Grow one segment forward (shaded tips grow a bit slower).
4. Give up if it is too dark or it ran into another branch.
5. If it didn't give up and isn't finished, leave a side bud at the new node.

A branch ends when it gets old, gets too long (side branches only), runs out of light, or hits something. Old branches end in a flower or bloom. The tree you see is just what's left after 35 cycles.

### Two coordinate systems

- **World units**: the continuous coordinates of branches and the light, from `0` to `WIDTH` / `HEIGHT`. The light is allowed to be outside this range.
- **Grid cells**: a `GRID_SIZE x GRID_SIZE` array (120 x 120) laid over the world. Each cell remembers the id of the branch that occupies it. With the defaults a cell is 0.1 world units wide. The grid is how the simulation detects collisions and shadows.

## Parameters

### Setup

| Name | Default | Meaning |
|---|---|---|
| `WIDTH`, `HEIGHT` | 12.0 | Size of the simulated world. Branches stop at its edge. |
| `GRID_SIZE` | 120 | Cells per side of the collision/shadow grid. |
| `MAX_CYCLES` | 35 | How many growth cycles to run. |
| `SEED` | `None` | Random seed. `None` picks a random one each launch. |
| `NUM_TREES` | 1 | Number of trunks, spaced evenly along the bottom edge. |

### Tree

| Name | Default | Meaning |
|---|---|---|
| `MAX_BRANCH_LENGTH` | 4.0 | Side branches stop growing at this length. Also the scale for growth speed. |
| `BASE_GROWTH` | 0.12 | Growth per cycle as a fraction of `MAX_BRANCH_LENGTH`. |
| `GROWTH_FACTOR` | 0.025 | Extra growth in full light, same units as `BASE_GROWTH`. |
| `APICAL_FACTOR` | 0.4 | Side branches grow `(1 - 0.4) = 60%` as fast as the trunk. |
| `ABORT_PROB` | 0.35 | Chance a new side bud dies, at zero light. It scales down to 0 in full light. |
| `FLOWER_PROB` | 0.25 | Chance a new side bud becomes a flower. |
| `BLOOM_PROB` | 0.30 | Chance a new side bud becomes a bloom. Whatever probability is left grows into a branch. |
| `MAX_AGE` | 14 | Cycles a branch can grow before it ends in a flower or bloom. |

### Light

| Name | Default | Meaning |
|---|---|---|
| `LIGHT_X`, `LIGHT_Y` | 6.0, 14.0 | Light position in world units. |
| `LIGHT_FALLOFF` | 0.5 | How fast light dims with distance. `0` means equally bright everywhere. |
| `SHADE_STRENGTH` | 2.5 | Light lost per world unit of other wood between a tip and the light. |
| `MIN_LIGHT` | 0.05 | A tip receiving less light than this gives up. |
| `RAY_STEP` | 0.08 | Spacing of the shadow-ray samples, in world units. |
| `RAY_START` | 0.15 | How far from the tip the shadow ray starts, so a tip doesn't shade itself. |

### Drawing

| Name | Default | Meaning |
|---|---|---|
| `TRUNK_COLOR` | near black | Color of all branches. |
| `TRUNK_WIDTH` | 0.6 | Trunk line width is `TRUNK_WIDTH * 10` points, and each branch order is 60% as thick. |
| `TRUNK_ANGLE` | 90 | Starting direction of the trunk in degrees. 90 is straight up. |
| `FLOWER_COLOR`, `BLOOM_COLOR` | red, yellow | Dot colors. |
| `FLOWER_RADIUS` | 0.09 | Dot size in world units. |

## Code walkthrough

### `class Branch`

One branch of the tree. It stores everything the simulation needs to know about it and has no behavior of its own.

**`__init__(bid, x, y, angle, order, parent)`**

1. `id`: a unique number. It is the branch's position in `Simulation.branches` and is the value written into the grid.
2. `pts`: the list of points along the branch. It starts with just the starting point, and every growth step appends one more.
3. `angle`: the direction the tip is currently heading, in radians.
4. `order`: 0 for the trunk, 1 for a branch off the trunk, 2 for a branch off that, and so on. It controls line thickness and whether the length limit applies.
5. `age` and `length`: how many cycles the branch has grown and how long it is. Both start at 0.
6. `state`: one of `"active"` (still growing), `"aborted"` (stopped early), `"flower"` or `"bloom"` (finished).
7. `ancestors`: the ids of the parent, grandparent and so on up to the trunk. It is copied from the parent and extended with the parent's own id.
8. `family`: the same ids plus the branch's own, as a numpy array. The shadow code uses this to ignore a branch's own wood.

**`tip` (property)**

Returns the last point in `pts`, which is where the branch is currently growing from.

### `class Simulation`

Holds the whole tree, the grid, and the light position, and runs the growth cycles.

**`__init__(light_x, light_y)`**

1. Stores the light position.
2. Creates an empty list of branches.
3. Creates `owner`, a `GRID_SIZE x GRID_SIZE` integer array filled with `-1`. Each cell will hold the id of the branch that passes through it, and `-1` means empty.
4. For each of the `NUM_TREES` trunks, picks an x position that spreads trunks evenly, then plants a trunk at `y = 0` pointing in the `TRUNK_ANGLE` direction.

#### Grid helpers

**`cell(x, y)`**

Converts world coordinates to grid indices. It scales by `GRID_SIZE / WIDTH` (or `HEIGHT`) and rounds down. The result can be outside the grid, so callers check it with `inside`.

**`inside(i, j)`**

Returns `True` if the cell indices are within the grid.

**`add_branch(x, y, angle, order, parent)`**

1. Creates a `Branch` whose id is the current length of the list, which is the index it is about to get.
2. Appends it to `self.branches`.
3. Returns it.

**`stamp(b, p0, p1)`**

Records that branch `b` now occupies the straight segment from `p0` to `p1`.

1. Works out how many sample points to use, about two per grid cell of length, so no cell along the segment is skipped.
2. Walks from `p0` to `p1` in that many even steps.
3. Converts each sample to a cell.
4. If the cell is inside the grid, writes `b.id` into it. A later branch overwrites an earlier owner in a shared cell.

**`light_at(b, x, y)`**

Returns how much light (0 to 1) reaches a point for branch `b`. This is the core of the light model.

1. Computes the vector from the point to the light and its length. If the point is on top of the light, it returns 1.
2. **Distance falloff**: `1 / (1 + LIGHT_FALLOFF * (dist / WIDTH)^2)`. Closer to the light means closer to 1.
3. Chooses how far to look along the ray: the distance to the light, but never more than the box diagonal, since no wood exists beyond the box.
4. Places sample points along the ray from the point toward the light, every `RAY_STEP` units, starting `RAY_START` away from the point.
5. Throws away samples that fall outside the world box.
6. Looks up the owner id in the grid for each remaining sample. Empty cells are dropped.
7. Drops samples owned by `b.family`, because a branch and its ancestors don't shade their own tip.
8. What remains is wood from other branches on the line between the point and the light. Multiplying the sample count by `RAY_STEP` approximates the length of wood the ray passes through.
9. **Shade**: `exp(-SHADE_STRENGTH * length)`. One thin branch costs a little, several layers cost a lot.
10. Returns falloff times shade.

**`blocked(b, x, y)`**

Returns `True` if branch `b` can't grow to the point `(x, y)`.

1. Converts the point to a cell. If it is within one cell of the grid's edge, or off the grid, it is blocked. This is why branches stop at the box boundary.
2. Looks at the 3 x 3 block of cells around the point and checks each distinct owner id.
3. Ignores empty cells, the branch's own cells, and its ancestors, since a branch has to be allowed to sprout from its parent.
4. Also ignores the branch's own descendants, so a parent isn't blocked by the side branches it already grew.
5. If any other branch is in that block, the point is blocked.

#### Growth

**`terminal_fate()`**

Decides what a finished branch tip turns into. It picks `"flower"` with probability `FLOWER_PROB / (FLOWER_PROB + BLOOM_PROB)` (about 45% with the defaults) and `"bloom"` otherwise.

**`grow(b)`**

Advances one active branch by one cycle. This is the main per-branch step.

1. **Measure light** at the current tip with `light_at`.
2. **Steer**: calculates the direction from the tip to the light, finds the shortest signed angle between the branch's heading and that direction, and turns the heading 15% of the way toward it. A small random wobble (standard deviation 0.10 rad) is added so branches aren't perfectly smooth.
3. **Choose the step length**: `MAX_BRANCH_LENGTH * (BASE_GROWTH + GROWTH_FACTOR * light)`. With the defaults that is about 0.48 to 0.58 units. Side branches multiply this by `1 - APICAL_FACTOR`, so they are slower than the trunk.
4. **Propose the next point** by moving that far along the new heading.
5. **Check for failure**: if the light is below `MIN_LIGHT` or `blocked` says the point is taken, the branch becomes `"aborted"` and stops. It keeps whatever it grew so far.
6. **Commit the growth**: appends the point, adds to `length`, increments `age`, and calls `stamp` so other branches see this segment.
7. **Check for the end of life**: a branch is finished if its age reached `MAX_AGE`, or if it is a side branch (order above 0) whose length reached `MAX_BRANCH_LENGTH`. Finished branches take the state returned by `terminal_fate`.
8. If it isn't finished, it calls `spawn_side_bud` at the new tip.

**`spawn_side_bud(parent, light)`**

Possibly creates a side bud at the parent's newest node. The `light` passed in is the value measured at the start of the parent's growth step.

1. Picks a side. It alternates left and right depending on how many points the parent has.
2. Picks the bud's direction: the parent's heading plus or minus a random 30 to 70 degrees.
3. Computes the abort chance: `ABORT_PROB * (1 - light)`. In full light buds never abort, and in deep shade the chance is the full 35%.
4. Rolls one random number `r` and walks through the outcomes in order:
   - `r` below the abort chance: the bud dies and nothing is created.
   - Next `FLOWER_PROB` slice: a **flower**.
   - Next `BLOOM_PROB` slice: a **bloom**.
   - Anything left: a new **active branch** that starts growing next cycle.
5. For a flower or bloom it creates a branch with a short 0.2 unit stalk in the bud's direction, sets its state, and it never grows.
6. For an active branch it just creates the branch at the node. It will be picked up by `step` next cycle.

With the defaults, about 45% of buds in full light become branches, and only 10% in deep shade. This is why the inside of the crown thins out.

**`step()`**

Runs one full cycle.

1. Takes a snapshot of the branch list. Branches created during this cycle are not in the snapshot, so new buds wait until next cycle to grow.
2. Calls `grow` on every branch whose state is `"active"`, in the order they were created. Older branches therefore claim light and space slightly before newer ones.

#### Drawing

**`draw(ax)`**

Draws every branch on a matplotlib axis.

1. Skips branches with fewer than two points, which means they never grew and have nothing to draw.
2. Splits the points into x and y lists.
3. Detects flower and bloom stalks, which are finished branches with zero length. They get a thin 1 point line.
4. Everything else gets a line width of `TRUNK_WIDTH * 10 * 0.6 ** order`, never below 0.8. With the defaults, the trunk is 6, first-order branches 3.6, then 2.2, 1.3, and 0.8.
5. Plots the polyline in `TRUNK_COLOR`.
6. For flowers and blooms, adds a small circle at the tip, red or yellow with a thin brown outline.

### Module-level functions

**`run(light_x, light_y, seed)`**

Grows a complete tree.

1. Seeds Python's random generator, so the same seed gives the same random numbers.
2. Creates a `Simulation` with the given light position.
3. Calls `step()` `MAX_CYCLES` times.
4. Returns the finished simulation.

**`render(ax, sim)`**

Draws a finished simulation, including the light.

1. Clears the axis and turns off axis lines.
2. Uses equal scaling so the world isn't stretched.
3. Sets the view to the world box plus a margin, expanded if needed so the light is always visible.
4. Draws a faint dashed outline of the world box, which is where branches stop.
5. Calls `sim.draw` to draw the tree.
6. Draws the light as a gold star.
7. Sets a title showing the light position and the controls.

**`main()`**

Opens the window and wires up the controls.

1. Picks the seed: `SEED` if you set one, otherwise a random number.
2. Creates a `state` dictionary holding the current light x, light y, and seed. The handlers below read and modify it.
3. Creates the figure.
4. Defines three inner functions:
   - **`redraw()`** runs a new simulation from the current state, prints a one-line summary, calls `render`, and asks matplotlib to refresh.
   - **`on_click(event)`** ignores clicks while the zoom or pan tool is active, or outside the plot. Otherwise it stores the clicked position as the new light position and calls `redraw`.
   - **`on_key(event)`** responds to `r` by choosing a new random seed and calling `redraw`.
5. Connects both handlers to matplotlib's event system.
6. Draws the first tree and calls `plt.show()` to open the window.

## One cycle at a glance

For a single growing branch, the order of operations is:

```
light_at  ->  steer  ->  step length  ->  propose point
   |
   +-- too dark or blocked?  -> aborted, stop
   |
   +-- commit point + stamp into grid
          |
          +-- too old or too long?  -> flower / bloom, stop
          |
          +-- otherwise: spawn_side_bud (abort / flower / bloom / new branch)
```

## Tuning guide

| To get... | Change |
|---|---|
| A bigger or smaller tree | `MAX_CYCLES`, `MAX_BRANCH_LENGTH`, `MAX_AGE`, or the world size |
| More branching | Lower `FLOWER_PROB` and `BLOOM_PROB` (more probability is left for branches) |
| Fewer flowers and blooms | Lower `FLOWER_PROB` and `BLOOM_PROB` |
| Harsher competition between branches | Raise `SHADE_STRENGTH` or `ABORT_PROB` |
| Softer shading | Lower `SHADE_STRENGTH` |
| A tree that cares less how far the light is | Lower `LIGHT_FALLOFF` (0 turns distance off) |
| Branches that bend more strongly toward the light | Raise the 0.15 turn rate in `grow` |
| A straighter, more regular tree | Lower the 0.10 wobble in `grow` |
| A more dominant trunk | Raise `APICAL_FACTOR` |
| A forest | Raise `NUM_TREES` |
| The same tree every time | Set `SEED` |

## Known limitations

- **Same seed is not a perfectly controlled experiment.** Moving the light reuses the same random seed, but once branches start dying in different places the number of random rolls changes, so the trees drift apart. You still see the same overall character, but it isn't the identical tree under different light.
- **Branches stop at the box edge.** A light placed far outside the box produces a tree pressed against that wall.
- **A light inside the canopy** makes branches curl and circle around it, because each tip keeps turning toward the point source.
- **Shadows are approximate.** The ray is sampled in steps, and a grid cell holds only the most recent branch that passed through it, so thin gaps can leak a little light.
- **Branches are processed in creation order**, so older branches get first claim on space.

---

# Part 2: L-system tree

An **L-system** (Lindenmayer system) grows a structure by repeatedly rewriting a string. After a few rounds of rewriting, the string is read as drawing instructions, and the instructions draw a tree. The whole tree is defined by four things you type in: an axiom, rewriting rules, an angle, and a number of iterations.

## Quick start

```bash
python lsystem_gui.py
```

A window opens with a preset already drawn. Pick another preset from the dropdown, or edit any field and press **Draw**.

| Field | What to enter |
|---|---|
| Preset | A built-in example. Choosing one fills in every field below and draws it. `Custom` leaves your fields alone. |
| Axiom | The starting string, for example `F` or `X`. Cannot be empty. |
| Rules | One rule per line, as `F=FF` or `F->FF`. The left side is a single symbol. |
| Angle | How far each `+` or `-` turns, in degrees, from -360 to 360. |
| Iterations | How many times the rules are applied, from 0 to 12. |
| Draw button | Draws the tree. Enter in the axiom, angle or iterations field does the same, and so does Ctrl+Enter anywhere. Enter inside the rules box just starts a new line. |

Under the picture there is a toolbar for zooming, panning and saving the image. Errors appear in red under the Draw button, and the previous tree stays on screen.

## How an L-system works

### 1. Rewriting

Start with the **axiom**. Then, once per iteration, replace every symbol that has a rule with that rule's replacement. All symbols are replaced at the same time, and symbols with no rule stay as they are.

Take the rule `F = F[+F]F[-F]F`:

| Iterations | Result | Symbols |
|---|---|---|
| 0 | `F` | 1 |
| 1 | `F[+F]F[-F]F` | 11 |
| 2 | `S1[+S1]S1[-S1]S1`, where `S1` is the iteration 1 string | 61 |
| 3 | The same pattern again, with every `F` replaced by `S1` | 311 |
| 4 | | 1,561 |

The string grows very quickly, because every `F` becomes five of them.

### 2. Reading the string as a drawing

A virtual pen, called the turtle, reads the final string one symbol at a time. It starts at the origin, pointing straight up.

| Symbol | What the turtle does |
|---|---|
| `F` or `G` | Draws a line one step forward |
| `f` | Moves one step forward without drawing |
| `+` | Turns left by the angle |
| `-` | Turns right by the angle |
| `[` | Remembers its current position and direction (starts a branch) |
| `]` | Jumps back to the last remembered position and direction (ends the branch) |
| Anything else (like `X`) | Does nothing, but can still be used in rules |

Reading `F[+F]F` as an example: draw a line up, remember this spot, turn left and draw a short branch, jump back to the remembered spot, then keep drawing straight up. The brackets are what turn a single line into a tree: every `[` opens a side branch and every `]` closes it.

### 3. Why presets 4 to 6 start with `X`

In the presets that start with `X`, the symbol `X` is never drawn. It marks a growing tip: each iteration, every `X` sprouts new branches and a new `X` at the end of each one. The rule `F = FF` lengthens every segment that has already been drawn, so older branches end up longer than newer ones, like a real tree.

## Presets

All six are classic examples from *The Algorithmic Beauty of Plants* by Prusinkiewicz and Lindenmayer.

| Name | Axiom | Rules | Angle | Iterations |
|---|---|---|---|---|
| Simple branching tree | `F` | `F=F[+F]F[-F]F` | 25.7 | 4 |
| Sparse tree | `F` | `F=F[+F]F[-F][F]` | 20 | 4 |
| Bushy tree | `F` | `F=FF-[-F+F+F]+[+F-F-F]` | 22.5 | 4 |
| Airy tree | `X` | `X=F[+X]F[-X]+X`, `F=FF` | 20 | 6 |
| Dense tree | `X` | `X=F[+X][-X]FX`, `F=FF` | 25.7 | 6 |
| Fractal plant | `X` | `X=F-[[X]+X]+F[+FX]-X`, `F=FF` | 22.5 | 5 |

## Try your own

| Axiom | Rules | Angle | Iterations | What you get |
|---|---|---|---|---|
| `F` | `F=F[+F][-F]` | 30 | 6 | A perfectly symmetric tree, 729 branches |
| `F` | `F=F[+F]F` | 25 | 5 | A lopsided tree: branches only sprout to the left of the branch they grow from |

Things worth experimenting with: a smaller angle gives a taller, narrower tree and a larger angle gives a wider, bushier one. Adding `F=FF` to a system that uses an `X` gives branches of different lengths. Every `[` needs a matching `]`.

## How the program fits together

```
input fields -> read_inputs -> final_length (size check) -> expand -> interpret -> draw
 (what you      (validate)      (refuse if too big)        (rewrite)  (turtle ->   (matplotlib
  typed)                                                              segments)    picture)
```

`draw_tree` runs this whole chain every time you press Draw. `final_length`, `expand` and `interpret` are plain functions with no GUI code, and `draw` only needs a matplotlib axis, so they are easy to reuse on their own.

### Constants

| Name | Value | Meaning |
|---|---|---|
| `MAX_SYMBOLS` | 1,000,000 | The longest string the program will build. |
| `MAX_ITERATIONS` | 12 | The highest iteration count the field accepts. |
| `PRESETS` | six entries | Maps a preset name to `(axiom, rules, angle, iterations)`. |
| `CUSTOM` | `"Custom"` | The dropdown entry used when the fields don't match a preset. |

## Code walkthrough: `lsystem_gui.py`

### The L-system functions

**`parse_rule(line)`**

Turns one line of text into a `(symbol, replacement)` pair.

1. Chooses the separator: `->` if the line contains it, otherwise `=`.
2. If the separator isn't there, raises an error asking for the form `F=FF`.
3. Splits the line into a left and right half and removes all spaces from both.
4. If the left side isn't exactly one character, raises an error.
5. Returns the pair. An empty right side is allowed and means "delete this symbol".

Any single character can be on the left, including `+`, `-`, `[` and `]`.

**`final_length(axiom, rules, iterations)`**

Counts how long the expanded string will be, without building it. This lets the program refuse a request before it freezes the computer.

1. Defines an inner function `size(symbol, depth)`, cached with `lru_cache`.
2. At depth 0, a symbol counts as 1.
3. Otherwise, it looks up the symbol's replacement (or the symbol itself if it has no rule) and adds up `size` for each character of the replacement, one level lower.
4. Adds up `size(c, iterations)` for each character of the axiom.

The cache means each `(symbol, depth)` pair is worked out once, so this finishes instantly even when the answer is billions.

**`expand(axiom, rules, iterations)`**

Applies the rules, and this is the recursive part of the program.

1. Defines an inner function `grow(symbol, depth)`, cached with `lru_cache`.
2. At depth 0, it returns the symbol unchanged.
3. Otherwise, it looks up the symbol's replacement (or the symbol itself if there is no rule) and calls `grow` on each character of the replacement, one level lower, then joins the results.
4. Runs `grow(c, iterations)` for each character of the axiom and joins those.

Two details worth knowing. The recursion is only as deep as the number of iterations (at most 12), so Python's recursion limit is never a concern. And the cache is created fresh on every call, so one set of rules can never leak stale results into the next.

**`interpret(commands, angle_deg, step=1.0)`**

Plays the string like a turtle and records the lines it draws.

1. Starts at `(0, 0)` with a heading of 90 degrees (straight up), an empty stack, and empty lists for segments and depths.
2. For each symbol:
   - `F`, `G` or `f`: computes the point one `step` ahead along the heading. For `F` and `G` it records the segment and the current stack size, which is how many branches deep the turtle is. Then it moves there.
   - `+`: adds the angle to the heading, which turns left.
   - `-`: subtracts the angle, which turns right.
   - `[`: pushes `(x, y, heading)` onto the stack.
   - `]`: pops the last saved `(x, y, heading)` and restores it. If the stack is empty, the `]` is ignored.
3. Returns the list of segments and the list of depths.

Every line is exactly one step long. Longer branches come from rules like `F=FF`, not from changing the step.

**`draw(ax, segments, depths, title)`**

Draws the segments onto a matplotlib axis.

1. Clears the axis, hides the axis lines and sets the title.
2. If there are no segments, stops there, leaving just the title.
3. Finds the deepest nesting level (using 1 if everything is at depth 0).
4. Gives each segment a color by blending from brown at the trunk to green at the deepest tips, based on its depth.
5. Gives each segment a width of `2.4 * 0.8 ** depth`, never below 0.4, so deeper branches are thinner.
6. Adds all segments at once as a `LineCollection` with rounded line ends, which is much faster than drawing them one by one.
7. Rescales the view to fit and sets equal scaling so the tree isn't stretched.

### `class App`

The window. It is a `tk.Tk` subclass, so the whole program is one object.

**`__init__()`**

1. Creates the window with a title, a starting size of 1050 x 720 and a minimum size.
2. Creates four `StringVar`s that hold the preset name, axiom, angle and iterations. Each one is tied to an input field, so reading the variable reads the field.
3. Calls `build_controls` and `build_plot` to create the widgets.
4. Loads the first preset into the fields and draws it, so the window never opens empty.

**`build_controls()`**

Builds the left-hand panel.

1. A read-only dropdown of `Custom` plus all preset names. Choosing an entry calls `on_preset_chosen`.
2. A text field for the axiom.
3. A multi-line text box for the rules, in a fixed-width font with no line wrapping.
4. A text field for the angle and a spinner for the iterations, from 0 to `MAX_ITERATIONS`, side by side.
5. The Draw button.
6. The status label, which wraps long messages.
7. A small legend of the drawing symbols.
8. Key bindings: Enter in the axiom, angle or iterations field draws, and Ctrl+Enter draws from anywhere. Enter in the rules box is left alone so it can start a new line.

**`build_plot()`**

Builds the right-hand side.

1. Creates a matplotlib `Figure` directly, not through `pyplot`. This way Tk owns the window and matplotlib doesn't open a second one.
2. Embeds the figure in the window with `FigureCanvasTkAgg`.
3. Adds the standard navigation toolbar for zoom, pan and save.

**`set_status(text, error=False)`**

Shows a message under the Draw button, in dark gray normally and in red when `error` is true.

**`load_preset(name)`**

Fills every field from a preset: the dropdown, the axiom, the angle and iterations as text, and the rules box with one `symbol=replacement` line per rule. It does not draw.

**`on_preset_chosen()`**

Runs when the dropdown changes. If the choice is a real preset, it loads it and draws. If the choice is `Custom`, it does nothing, so your typing is kept.

**`read_inputs()`**

Reads and checks every field, and either returns clean values or raises a `ValueError` with a message meant for the user.

1. Axiom: removes spaces, and rejects an empty one.
2. Rules: goes through the box line by line, skips blank lines, and parses each with `parse_rule`. A bad line gives an error naming its line number. If two lines define the same symbol, the later one wins.
3. Angle: must be a number from -360 to 360. This also rejects `nan` and `inf`, which would otherwise break the drawing.
4. Iterations: must be a whole number from 0 to `MAX_ITERATIONS`.
5. Returns `(axiom, rules, angle, iterations)`.

**`draw_tree()`**

The button handler, and the place where the whole chain runs.

1. Calls `read_inputs`, then `final_length`. If either fails, or the string would be longer than `MAX_SYMBOLS`, it shows the message in red and stops. The tree already on screen is left as it was.
2. Works out the tree's name: if the values match a preset exactly, it uses the preset's name and updates the dropdown to show it, otherwise it uses `Custom`.
3. Shows "Drawing..." and refreshes the window so the message appears before the work starts.
4. Calls `expand` and `interpret`, then `draw`, then redraws the canvas.
5. Shows how many symbols and branches were made. If there were no branches at all, it says so in red, because the result contained no `F` or `G`.

### Starting the program

The last two lines create an `App` and start Tk's event loop, which waits for clicks and key presses until the window closes.

## Command-line version: `lsystem_tree.py`

The same program without a window. It reuses the same `expand`, `final_length` and `interpret` functions, so the pictures are identical. It asks for everything through prompts in the terminal, and pressing Enter keeps the default shown in brackets.

| Function | What it does |
|---|---|
| `draw(segments, depths, title)` | Like the GUI's `draw`, but it creates its own matplotlib figure and returns it. |
| `ask(prompt, default, cast)` | Asks until the answer converts with `cast`. Enter keeps the default. |
| `non_negative_int(text)` | Converter for the iterations prompt. Rejects negatives. |
| `angle_value(text)` | Converter for the angle prompt. Rejects anything outside -360 to 360, including `nan` and `inf`. |
| `parse_rule(line)` | Same as in the GUI version. |
| `ask_rules()` | Reads rules one line at a time until a blank line. A bad rule is explained and asked for again. |
| `get_settings()` | Prints the numbered presets, then asks for the axiom, rules, angle and iterations. Choosing a preset only asks for angle and iterations. |
| `main()` | Loops: ask, check the size, grow, draw, then ask whether to grow another tree. |

Two differences from the GUI: the size limit is 2,000,000 symbols instead of 1,000,000, and the iterations are not capped at 12, only by the symbol limit.

## Known limitations

- **Deterministic and context-free.** The same input always gives the same picture, and each rule replaces one symbol regardless of its neighbors. There is no randomness, no parameters on symbols and no context-sensitive rules.
- **No environment.** Unlike Part 1, nothing reacts to light or space, so branches freely overlap each other.
- **One rule per symbol.** If you enter two rules for the same symbol, the later one replaces the earlier one. It does not choose between them.
- **Fixed segment length.** Every drawn line is one step long. The picture is scaled to fit the window, so a tree with more iterations looks smaller, not bigger.
- **Unbalanced brackets.** A `]` with no matching `[` is ignored, and a `[` that is never closed is simply left open.
- **The window freezes while drawing.** Drawing runs on the same thread as the window, so a very large tree can make it unresponsive for a moment.
- **Colors come from nesting depth,** not from branch age or thickness, so a long unbranched trunk is all one color.
