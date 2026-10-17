"""Port of web/engine.mjs: a seeded, display-independent particle world.

The world's state is a namedtuple of numpy arrays so that every rule compiles
with numba; `World` wraps it with the same methods as the JavaScript class.
Kernels mirror the JavaScript methods one-for-one (snake_cased) and keep its
evaluation order, including the order of random draws, so both versions follow
the same rules. Scalars that kernels mutate (tick, seed, flags) are stored in
one-element arrays.
"""
import math
from collections import namedtuple
from types import SimpleNamespace

import numpy as np
from numba import njit

from .gravity import radial_gravity

# Kernels run without reference counting: with it, any branch in a function
# that receives the state tuple increments and decrements every one of its
# arrays, which made a tick about 40 times slower. Kernels therefore cannot
# allocate; gravity, which builds its source list, is the one exception.
# Small per-cell helpers are also inlined to avoid passing the whole tuple.
kernel = njit(cache=True, _nrt=False)
hot = njit(cache=True, _nrt=False, inline='always')

Element = namedtuple('Element', 'name symbol light dark density viscosity thermal electrical temperature state hint')

ELEMENTS = (
    Element('Erase', '⌁', '#666960', '#a4a79d', 0, 0, 0, 0, 20, 'empty', 'Remove particles.'),
    Element('Sand', '·', '#886000', '#ffe9a3', 1.8, 0, .08, 0, 20, 'powder', 'Settles through water, mixes into mud, and supports roots. Intense heat fuses it into crystal.'),
    Element('Water', '○', '#006cab', '#4ad6ff', 1, .05, .5, .65, 20, 'liquid', 'Supplies roots, carries charge, freezes below zero, and boils above 100°.'),
    Element('Oil', '/', '#8919b8', '#da91ff', .7, .65, .04, 0, 20, 'liquid', 'Floats on water. Electrically insulating and combustible.'),
    Element('Fire', ':', '#bd3000', '#ff7b4f', .12, 0, .5, 0, 650, 'gas', 'Burns fuel and drives an upward air current. Wind bends the flame; water extinguishes it.'),
    Element('Vapor', '|', '#30618c', '#c1e9f3', .05, .1, .06, 0, 120, 'gas', 'Drifts with air currents. Cooler vapor has a shorter condensation half-life.'),
    Element('Stone', '■', '#3d434a', '#5b636c', 9, 1, .35, 0, 20, 'solid', 'A fixed, electrically insulating barrier to particles and wind.'),
    Element('Seed', '+', '#386e00', '#a5ed60', 1.1, 0, .08, .01, 20, 'powder', 'Roots on sand or mud. Absorbs water to grow upward, branching into thinner shoots.'),
    Element('Crystal', '◇', '#007763', '#59f4e1', 3, 1, .25, 1, 20, 'solid', 'A fast electrical conductor. Charge waves reflect at the ends of connected paths.'),
    Element('Spark', '×', '#806000', '#ffe56c', .02, 0, .4, 1, 850, 'energy', 'Scatters outward, ignites fuel, and injects a pulse into adjacent conductors.'),
    Element('Lava', '≋', '#c02008', '#ff644b', 2.8, .88, .85, .18, 1100, 'liquid', 'Hot, slow, and dense. Cools into stone; contact with water produces vapor.'),
    Element('Mud', '∷', '#71430c', '#d0a66d', 2.1, .92, .28, .12, 20, 'liquid', 'Wet soil that holds water for roots. Flows slowly and dries into sand when heated.'),
    Element('Ice', '✧', '#2857b8', '#a7d8ff', .92, 1, .65, .01, -25, 'solid', 'Cools its surroundings and melts above zero. Conducts heat much better than charge.'),
    Element('Wind', '~', '#147158', '#b0e9ce', 0, 0, 0, 0, 20, 'field', 'Move to aim; hold to blow in that direction. Sends air around obstacles without adding particles.'),
    Element('Scramble', '?', '#a12b80', '#ff91dd', 1.2, 0, .12, .05, 20, 'powder', 'Contact changes a neighbor into a random material and consumes the question mark. Phase lock makes it reusable; locked neighbors are protected.'),
    Element('Metal', '□', '#4b5663', '#a6b3c1', 8, 1, .9, .95, 20, 'solid', 'Conducts heat and electricity. Hot lava melts it, as does any heat above 800°.'),
    Element('Grav', 'g', '#153d87', '#658edc', 9, 1, 0, 0, 20, 'solid', 'A fixed source that attracts nearby moving matter. Antigrav reverses the force for newly placed sources.'),
    Element('Bacterium', '△', '#7524a0', '#c38cf4', .3, 1, .15, 0, 20, 'life', 'Life rules: survives with 2–3 neighbors, born with 3. Eats plant matter; heat and cold kill it. Phase lock isolates a colony from other elements.'),
    # U+FE0E requests the text (not emoji) presentation of the warning sign.
    Element('Gunpowder', '⚠︎', '#3f3a33', '#d9ccb4', 1.5, 0, .1, 0, 20, 'powder', 'Fire, sparks, lava, or heat above 180° detonate it: a blast of pressure, wind, and fire that chains through connected powder. Cannot be phase locked.'),
    Element('Boids', 'v', '#4a3d33', '#e6d3bd', 1.05, 0, .1, 0, 20, 'life', 'Flocking birds: each steers toward its neighbors’ heading and center while keeping its distance, and avoids obstacles. Feesh fall inert until they reach water, then school.'),
    Element('Liquid N₂', '⋄', '#126a79', '#9af4ff', .81, .02, .3, 0, -200, 'liquid', 'Liquid nitrogen: an intensely cold liquid. Boils above −196° into nitrogen vapor; phase lock keeps it liquid and cold.'),
)

# Kernels read ids as module constants; Python callers use the ID namespace.
(EMPTY, SAND, WATER, OIL, FIRE, VAPOR, STONE, SEED, CRYSTAL, SPARK, LAVA, MUD, ICE, WIND, SCRAMBLE,
 METAL, GRAV, BACTERIUM, GUNPOWDER, BOID, NITROGEN) = range(len(ELEMENTS))
ID = SimpleNamespace(
    EMPTY=EMPTY, SAND=SAND, WATER=WATER, OIL=OIL, FIRE=FIRE, VAPOR=VAPOR, STONE=STONE, SEED=SEED,
    CRYSTAL=CRYSTAL, SPARK=SPARK, LAVA=LAVA, MUD=MUD, ICE=ICE, WIND=WIND, SCRAMBLE=SCRAMBLE, METAL=METAL,
    GRAV=GRAV, BACTERIUM=BACTERIUM, GUNPOWDER=GUNPOWDER, BOID=BOID, NITROGEN=NITROGEN)

PHASE_LOCKABLE = frozenset((SAND, WATER, OIL, FIRE, VAPOR, SEED, LAVA, MUD, ICE, SCRAMBLE, METAL, BACTERIUM, NITROGEN))
LOCKED_SYMBOLS = {SAND: '•', WATER: '●', ICE: '✦', BACTERIUM: '▲'}
ANTIGRAV_COLOR = {'light': '#8b2533', 'dark': '#dc727c'}
FEESH_COLOR = {'light': '#a64a00', 'dark': '#ffa45c'}
MAX_PRESSURE = 60
MAX_AIR_SPEED = 12
# Ordinary downward acceleration on powders and liquids, per tick.
NORMAL_GRAVITY = .045
# Peak grav acceleration: slightly above ordinary gravity, so a nearby source
# can lift resting matter off the ground.
GRAV_STRENGTH = .06
# Boids: flocking radius (cells) and speed bounds (cells per tick).
BOID_RADIUS, BOID_MIN_SPEED, BOID_MAX_SPEED, FEESH_MAX_SPEED = 6, .25, .8, .5

STATES = ('empty', 'powder', 'liquid', 'gas', 'solid', 'energy', 'life', 'field')
LIQUID, GAS, SOLID = STATES.index('liquid'), STATES.index('gas'), STATES.index('solid')
# Per-id lookup tables; numba freezes these globals as constants.
STATE = np.array([STATES.index(element.state) for element in ELEMENTS], np.uint8)
DENSITY = np.array([element.density for element in ELEMENTS], np.float64)
VISCOSITY = np.array([element.viscosity for element in ELEMENTS], np.float64)
THERMAL = np.array([element.thermal for element in ELEMENTS], np.float64)
ELECTRICAL = np.array([element.electrical for element in ELEMENTS], np.float64)
TEMPERATURE = np.array([element.temperature for element in ELEMENTS], np.float64)
LOCKABLE = np.array([id in PHASE_LOCKABLE for id in range(len(ELEMENTS))], np.bool_)
SCRAMBLE_RESULTS = np.array([id for id in range(1, len(ELEMENTS)) if id not in (WIND, SCRAMBLE)], np.int64)
SCRAMBLE_INDEX = np.array([int(np.argmax(SCRAMBLE_RESULTS == id)) for id in range(len(ELEMENTS))], np.int64)


def element_symbol(id, locked=False):
    return LOCKED_SYMBOLS.get(id, ELEMENTS[id].symbol) if locked else ELEMENTS[id].symbol


# Particle properties move with their particle; `exchange` swaps each of them.
PARTICLE_FIELDS = {
    'heat': np.float64, 'charge': np.float64, 'charge_velocity': np.float64, 'life': np.uint16,
    'vx': np.float64, 'vy': np.float64, 'travel_x': np.float64, 'travel_y': np.float64,
    'moisture': np.float64, 'burn': np.float64, 'roots': np.int32, 'branch': np.int8,
    'generation': np.uint8, 'phase_locked': np.uint8, 'polarity': np.int8, 'nitrogen_vapor': np.uint8,
}
GRID_FIELDS = {
    'cells': np.uint8, 'updated': np.uint32, 'moved': np.uint32, 'gravity_x': np.float64, 'gravity_y': np.float64,
    'neighbors': np.uint8, 'locked_neighbors': np.uint8, 'force': np.float64, 'pressure': np.float64,
    'next_pressure': np.float64, 'curl': np.float64, 'wind_x': np.float64, 'wind_y': np.float64,
    'next_wind_x': np.float64, 'next_wind_y': np.float64, 'air_mask': np.uint8, 'supported_matter': np.uint8,
    'support_queue': np.int32, 'air_heat': np.float64, 'next_air_heat': np.float64,
}
# random_override, when non-negative, replaces random draws (tests only).
SCALAR_FIELDS = {
    'tick': np.int64, 'seed': np.int64, 'support_tick': np.int64, 'gravity_dirty': np.uint8,
    'zero_gravity': np.uint8, 'wind_strength': np.float64, 'grav_strength': np.float64, 'random_override': np.float64,
}
State = namedtuple('State', ['size', 'length', *PARTICLE_FIELDS, *GRID_FIELDS, *SCALAR_FIELDS])


@hot
def fill(array, value):
    # Slice assignment needs reference counting, which kernels run without.
    for i in range(len(array)):
        array[i] = value


@hot
def copy(target, source):
    for i in range(len(target)):
        target[i] = source[i]


@hot
def js_round(value):
    """JavaScript's Math.round: halves round toward +∞ (Python rounds to even)."""
    return int(math.floor(value + .5))


@hot
def sign(value):
    return 1 if value > 0 else -1 if value < 0 else 0


@kernel
def brush_start(position, diameter):
    """Odd diameters center on a cell; even diameters center between cells."""
    return js_round(position - (diameter - 1) / 2)


@hot
def condensation_chance(temperature):
    if temperature >= 100:
        return 0.0
    half_life = 25 + max(0.0, temperature - 20) * 3
    return 1 - math.exp(-math.log(2) / half_life)


@hot
def random(w):
    """Xorshift32, bit-identical to the JavaScript generator for the same seed."""
    if w.random_override[0] >= 0:
        return w.random_override[0]
    seed = w.seed[0]
    seed ^= (seed << 13) & 0xFFFFFFFF
    seed ^= seed >> 17
    seed ^= (seed << 5) & 0xFFFFFFFF
    w.seed[0] = seed
    return seed / 4294967296.0


@hot
def blocked(w, i):
    material = w.cells[i]
    return STATE[material] == SOLID or (material == SEED and w.roots[i] >= 0)


@hot
def gust(w, i, x, y):
    if blocked(w, i):
        return
    w.wind_x[i] = max(-MAX_AIR_SPEED, min(MAX_AIR_SPEED, w.wind_x[i] + x))
    w.wind_y[i] = max(-MAX_AIR_SPEED, min(MAX_AIR_SPEED, w.wind_y[i] + y))


@hot
def pressurize(w, i, amount):
    if not blocked(w, i):
        w.pressure[i] = max(-MAX_PRESSURE, min(MAX_PRESSURE, w.pressure[i] + amount))


@kernel
def place(w, i, material, temperature, locked, alternate):
    """JavaScript `set`. `alternate` selects an element's second form: antigrav
    for Grav, feesh for Boids. Both store it in polarity (1 or -1), which moves
    with the particle."""
    if material == WIND:
        pressurize(w, i, .6)
        return
    if w.cells[i] == GRAV or material == GRAV:
        w.gravity_dirty[0] = 1
    w.cells[i] = material
    w.polarity[i] = (-1 if alternate else 1) if material == GRAV or material == BOID else 0
    w.phase_locked[i] = 1 if locked and LOCKABLE[material] else 0
    w.nitrogen_vapor[i] = 0
    w.heat[i] = temperature
    w.charge[i] = 1.0 if material == SPARK else 0.0
    w.charge_velocity[i] = 0
    # Boids use life as a wingbeat clock; a random start keeps flocks out of phase.
    if material == FIRE:
        w.life[i] = 300 + int(random(w) * 240)
    elif material == SPARK:
        w.life[i] = 18 + int(random(w) * 18)
    elif material == BOID:
        w.life[i] = int(random(w) * 256)
    else:
        w.life[i] = 0
    w.burn[i] = 0
    w.moisture[i] = 2 if material == MUD else 0
    w.roots[i] = -1; w.branch[i] = 0; w.generation[i] = 0
    angle = random(w) * math.pi * 2 if material == SPARK or material == BOID else 0.0
    speed = 1.0 if material == SPARK else BOID_MIN_SPEED if material == BOID else 0.0
    w.vx[i] = speed * math.cos(angle)
    w.vy[i] = speed * math.sin(angle)
    w.travel_x[i] = 0; w.travel_y[i] = 0
    w.updated[i] = w.tick[0]


@kernel
def reset(w, i, material):
    """Places a material at its default temperature, unlocked."""
    place(w, i, material, TEMPERATURE[material], False, False)


@kernel
def blow(w, x, y, diameter, strength, direction_x, direction_y):
    n = w.size
    w.wind_strength[0] = max(10.0, min(100.0, strength))
    length = math.hypot(direction_x, direction_y)
    if not length:
        return
    ux = direction_x / length; uy = direction_y / length
    start_x = brush_start(x, diameter); start_y = brush_start(y, diameter)
    radius = diameter / 2; center = (diameter - 1) / 2
    for row in range(diameter):
        for col in range(diameter):
            dx = col - center; dy = row - center; distance = dx * dx + dy * dy
            px = start_x + col; py = start_y + row
            if distance > radius * radius or px < 0 or py < 0 or px >= n or py >= n:
                continue
            i = py * n + px
            if blocked(w, i):
                continue
            weight = math.exp(-distance / (radius * radius * .7))
            # A held nozzle adds momentum, not just pressure in a static balloon.
            # A small balanced pressure dipole helps entrain the surrounding air.
            gust(w, i, ux * strength * .22 * weight, uy * strength * .22 * weight)
            for side in (-1, 1):
                tx = px + side * ux; ty = py + side * uy
                left = int(math.floor(tx)); top = int(math.floor(ty)); fx = tx - left; fy = ty - top
                # Bilinear deposition preserves the continuous angle of the nozzle.
                for corner_row in range(2):
                    for corner_col in range(2):
                        nx = left + corner_col; ny = top + corner_row
                        fraction = (fx if corner_col else 1 - fx) * (fy if corner_row else 1 - fy)
                        if not fraction or nx < 0 or ny < 0 or nx >= n or ny >= n:
                            continue
                        if nx != px and ny != py and (blocked(w, py * n + nx) or blocked(w, ny * n + px)):
                            continue
                        pressurize(w, ny * n + nx, -side * strength * .07 * weight * fraction)


@kernel
def paint(w, x, y, material, diameter, strength, locked, direction_x, direction_y, alternate):
    if material == WIND:
        blow(w, x, y, diameter, strength, direction_x, direction_y)
        return
    n = w.size
    start_x = brush_start(x, diameter); start_y = brush_start(y, diameter)
    radius = diameter / 2; center = (diameter - 1) / 2
    for row in range(diameter):
        for col in range(diameter):
            dx = col - center; dy = row - center
            if dx * dx + dy * dy > radius * radius:
                continue
            px = start_x + col; py = start_y + row
            if px < 0 or py < 0 or px >= n or py >= n:
                continue
            i = py * n + px
            if not material:
                w.pressure[i] = 0; w.wind_x[i] = 0; w.wind_y[i] = 0
            if not material or not w.cells[i]:
                place(w, i, material, TEMPERATURE[material], locked, alternate)
                if material == SPARK and (dx or dy):
                    length = math.hypot(dx, dy)
                    w.vx[i] = dx / length; w.vy[i] = dy / length


@hot
def exchange(w, a, b):
    """Swaps two particles with all of their properties (PARTICLE_FIELDS)."""
    w.cells[a], w.cells[b] = w.cells[b], w.cells[a]
    w.heat[a], w.heat[b] = w.heat[b], w.heat[a]
    w.charge[a], w.charge[b] = w.charge[b], w.charge[a]
    w.charge_velocity[a], w.charge_velocity[b] = w.charge_velocity[b], w.charge_velocity[a]
    w.life[a], w.life[b] = w.life[b], w.life[a]
    w.vx[a], w.vx[b] = w.vx[b], w.vx[a]
    w.vy[a], w.vy[b] = w.vy[b], w.vy[a]
    w.travel_x[a], w.travel_x[b] = w.travel_x[b], w.travel_x[a]
    w.travel_y[a], w.travel_y[b] = w.travel_y[b], w.travel_y[a]
    w.moisture[a], w.moisture[b] = w.moisture[b], w.moisture[a]
    w.burn[a], w.burn[b] = w.burn[b], w.burn[a]
    w.roots[a], w.roots[b] = w.roots[b], w.roots[a]
    w.branch[a], w.branch[b] = w.branch[b], w.branch[a]
    w.generation[a], w.generation[b] = w.generation[b], w.generation[a]
    w.phase_locked[a], w.phase_locked[b] = w.phase_locked[b], w.phase_locked[a]
    w.polarity[a], w.polarity[b] = w.polarity[b], w.polarity[a]
    w.nitrogen_vapor[a], w.nitrogen_vapor[b] = w.nitrogen_vapor[b], w.nitrogen_vapor[a]
    tick = w.tick[0]
    w.updated[a] = tick; w.updated[b] = tick; w.moved[a] = tick; w.moved[b] = tick


@hot
def density(w, i):
    state = STATE[w.cells[i]]
    expansion = 1 / 293 if state == GAS else .0007 if state == LIQUID else 0.0
    return DENSITY[w.cells[i]] / max(.25, 1 + expansion * (w.heat[i] - 20))


@hot
def move(w, i, x, y, displace):
    n = w.size
    if x < 0 or y < 0 or x >= n or y >= n:
        return False
    j = y * n + x
    target = w.cells[j]
    dx = x - i % n; dy = y - i // n
    along_gravity = (dx * (w.gravity_x[i] + w.gravity_x[j]) * .5 +
                     dy * ((w.gravity_y[i] + w.gravity_y[j]) * .5 + (0.0 if w.zero_gravity[0] else NORMAL_GRAVITY)))
    displacement = (displace and w.moved[j] != w.tick[0] and
                    (STATE[target] == LIQUID or STATE[target] == GAS) and
                    along_gravity * (density(w, i) - density(w, j)) > 1e-9)
    if not target or displacement:
        exchange(w, i, j)
        return True
    return False


@hot
def _air_exchange(w, particle, cell):
    rate = min(.08, THERMAL[w.cells[particle]]) * .25
    transfer = (w.heat[particle] - w.air_heat[cell]) * rate
    w.air_heat[cell] += transfer
    # Air has one tenth the cell heat capacity of matter.
    if not w.phase_locked[particle]:
        w.heat[particle] -= transfer * .1


@hot
def _air_pair(w, i, j, is_blocked):
    other_blocked = blocked(w, j)
    if not is_blocked and not other_blocked:
        transfer = (w.air_heat[i] - w.air_heat[j]) * .08
        w.air_heat[i] -= transfer; w.air_heat[j] += transfer
    elif is_blocked != other_blocked:
        if is_blocked:
            _air_exchange(w, i, j)
        else:
            _air_exchange(w, j, i)


@kernel
def air_thermal(w):
    # Air occupies the flow field, not particle slots: moving/erasing matter
    # must not reset its temperature. Solids exchange through exposed faces.
    n = w.size
    i = 0
    for y in range(n):
        for x in range(n):
            is_blocked = blocked(w, i)
            if not is_blocked and w.cells[i]:
                _air_exchange(w, i, i)
            if x + 1 < n:
                _air_pair(w, i, i + 1, is_blocked)
            if y + 1 < n:
                _air_pair(w, i, i + n, is_blocked)
            i += 1


@hot
def thermal_pair(w, a, b):
    if not w.cells[b]:
        return
    conductivity = min(THERMAL[w.cells[a]], THERMAL[w.cells[b]])
    heat = (w.heat[a] - w.heat[b]) * conductivity * .2
    # Locked matter is a thermal reservoir: it still heats/cools its neighbors.
    if not w.phase_locked[a]:
        w.heat[a] -= heat
    if not w.phase_locked[b]:
        w.heat[b] += heat


@hot
def electrical_pair(w, a, b):
    conductivity = min(ELECTRICAL[w.cells[a]], ELECTRICAL[w.cells[b]])
    if not conductivity:
        return
    force = (w.charge[b] - w.charge[a]) * conductivity * .07
    w.force[a] += force; w.force[b] -= force


@kernel
def electricity(w):
    # A damped wave on the conductive adjacency graph, not diffusion. Missing
    # edges have zero flux, so pulses reflect at conductor boundaries. A single
    # substep keeps the front visible; its speed scales with conductivity.
    n = w.size
    fill(w.force, 0)
    for i in range(w.length):
        if not ELECTRICAL[w.cells[i]]:
            continue
        if i % n < n - 1:
            electrical_pair(w, i, i + 1)
        if i + n < w.length:
            electrical_pair(w, i, i + n)
    for i in range(w.length):
        if not ELECTRICAL[w.cells[i]]:
            w.charge[i] = 0; w.charge_velocity[i] = 0
            continue
        w.charge_velocity[i] = (w.charge_velocity[i] + w.force[i]) * .997
        w.charge[i] = max(-3.0, min(3.0, (w.charge[i] + w.charge_velocity[i]) * .999))


@hot
def sample_flow(w, field, x, y, fallback):
    n = w.size
    x = max(0.0, min(n - 1.001, x)); y = max(0.0, min(n - 1.001, y))
    ix = int(math.floor(x)); iy = int(math.floor(y)); i = iy * n + ix; fx = x - ix; fy = y - iy
    mask = w.air_mask
    a = fallback if mask[i] else field[i]
    b = fallback if mask[i + 1] else field[i + 1]
    c = fallback if mask[i + n] else field[i + n]
    d = fallback if mask[i + n + 1] else field[i + n + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


@kernel
def airflow(w):
    n = w.size
    mask = w.air_mask; pressure = w.pressure; wind_x = w.wind_x; wind_y = w.wind_y
    next_x = w.next_wind_x; next_y = w.next_wind_y; curl = w.curl; next_pressure = w.next_pressure
    down = 0.0 if w.zero_gravity[0] else NORMAL_GRAVITY
    persistence = .999 + .00095 * max(0.0, min(1.0, (w.wind_strength[0] - 10) / 90))
    for i in range(w.length):
        mask[i] = 1 if blocked(w, i) else 0
    # Compressible pressure/velocity coupling preserves traveling pressure waves.
    # Semi-Lagrangian velocity transport and weak vorticity confinement retain
    # wakes around obstacles. This is a bounded artistic approximation, not CFD.
    i = 0
    for y in range(n):
        for x in range(n):
            if mask[i]:
                next_x[i] = 0; next_y[i] = 0; pressure[i] = 0
                w.next_air_heat[i] = w.air_heat[i]
                i += 1
                continue
            p = pressure[i]
            left = x > 0 and not mask[i - 1]; right = x < n - 1 and not mask[i + 1]
            up = y > 0 and not mask[i - n]; down_open = y < n - 1 and not mask[i + n]
            # Keep the backtrace inside adjacent cells so fast flow cannot sample
            # through a wall. Momentum magnitude remains independent of transport.
            transport = min(.3, .9 / max(.001, abs(wind_x[i]), abs(wind_y[i])))
            bx = x - wind_x[i] * transport; by = y - wind_y[i] * transport
            w.next_air_heat[i] = sample_flow(w, w.air_heat, bx, by, w.air_heat[i])
            # Isotropic nine-point gradients reduce the axial cross of a four-neighbor
            # stencil. Diagonal paths are closed when either adjoining face is blocked.
            nw = pressure[i - n - 1] if left and up and not mask[i - n - 1] else p
            ne = pressure[i - n + 1] if right and up and not mask[i - n + 1] else p
            sw = pressure[i + n - 1] if left and down_open and not mask[i + n - 1] else p
            se = pressure[i + n + 1] if right and down_open and not mask[i + n + 1] else p
            east = pressure[i + 1] if right else p; west = pressure[i - 1] if left else p
            south = pressure[i + n] if down_open else p; north = pressure[i - n] if up else p
            vx = sample_flow(w, wind_x, bx, by, wind_x[i]) - (4 * (east - west) + ne + se - nw - sw) * (.28 / 6)
            vy = sample_flow(w, wind_y, bx, by, wind_y[i]) - (4 * (south - north) + sw + se - nw - ne) * (.28 / 6)
            thermal_lift = max(-.08, min(.08, (w.air_heat[i] - 20) * .00025)) / NORMAL_GRAVITY
            vx -= w.gravity_x[i] * thermal_lift
            vy -= (w.gravity_y[i] + down) * thermal_lift
            if (not left and vx < 0) or (not right and vx > 0):
                vx = 0.0
            if (not up and vy < 0) or (not down_open and vy > 0):
                vy = 0.0
            next_x[i] = vx * persistence; next_y[i] = vy * persistence
            i += 1
    i = 0
    for y in range(n):
        for x in range(n):
            if mask[i]:
                curl[i] = 0
            else:
                curl[i] = ((next_y[i + 1] if x < n - 1 else 0.0) - (next_y[i - 1] if x else 0.0) -
                           (next_x[i + n] if y < n - 1 else 0.0) + (next_x[i - n] if y else 0.0)) * .5
            i += 1
    i = 0
    for y in range(n):
        for x in range(n):
            if mask[i]:
                next_pressure[i] = 0
                i += 1
                continue
            left = x > 0 and not mask[i - 1]; right = x < n - 1 and not mask[i + 1]
            up = y > 0 and not mask[i - n]; down_open = y < n - 1 and not mask[i + n]
            nw = left and up and not mask[i - n - 1]; ne = right and up and not mask[i - n + 1]
            sw = left and down_open and not mask[i + n - 1]; se = right and down_open and not mask[i + n + 1]
            sx = next_x[i]; sy = next_y[i]
            diagonal_x = ((next_x[i - n + 1] if ne else -sx) + (next_x[i + n + 1] if se else -sx) -
                          (next_x[i - n - 1] if nw else -sx) - (next_x[i + n - 1] if sw else -sx))
            diagonal_y = ((next_y[i + n - 1] if sw else -sy) + (next_y[i + n + 1] if se else -sy) -
                          (next_y[i - n - 1] if nw else -sy) - (next_y[i - n + 1] if ne else -sy))
            axial = ((next_x[i + 1] if right else -sx) - (next_x[i - 1] if left else -sx) +
                     (next_y[i + n] if down_open else -sy) - (next_y[i - n] if up else -sy))
            divergence = (4 * axial + diagonal_x + diagonal_y) / 12
            p = pressure[i] - divergence * .55
            next_pressure[i] = max(-MAX_PRESSURE, min(MAX_PRESSURE, p * persistence))
            gx = (abs(curl[i + 1]) if right else 0.0) - (abs(curl[i - 1]) if left else 0.0)
            gy = (abs(curl[i + n]) if down_open else 0.0) - (abs(curl[i - n]) if up else 0.0)
            scale = .035 * curl[i] / (math.sqrt(gx * gx + gy * gy) + .001)
            vx = next_x[i] + gy * scale; vy = next_y[i] - gx * scale
            if (not left and vx < 0) or (not right and vx > 0):
                vx = 0.0
            if (not up and vy < 0) or (not down_open and vy > 0):
                vy = 0.0
            next_x[i] = max(-MAX_AIR_SPEED, min(MAX_AIR_SPEED, vx))
            next_y[i] = max(-MAX_AIR_SPEED, min(MAX_AIR_SPEED, vy))
            i += 1
    # JavaScript swaps the buffers; copying keeps the namedtuple's arrays fixed.
    copy(wind_x, next_x); copy(wind_y, next_y)
    copy(pressure, next_pressure)
    copy(w.air_heat, w.next_air_heat)


@kernel
def transform(w, i, material, temperature):
    if w.phase_locked[i]:
        return
    vx = w.vx[i]; vy = w.vy[i]
    nitrogen = material == VAPOR and (w.cells[i] == NITROGEN or w.nitrogen_vapor[i] != 0)
    place(w, i, material, temperature, False, False)
    w.nitrogen_vapor[i] = 1 if nitrogen else 0
    if material:
        w.vx[i] = vx; w.vy[i] = vy


@kernel
def contact(w, i, j):
    source = w.cells[i]; target = w.cells[j]
    igniter = source == FIRE or source == SPARK or source == LAVA
    if igniter and target == GUNPOWDER:
        w.burn[j] = 1
    if not w.phase_locked[j] and igniter and (target == OIL or target == SEED):
        thermal = THERMAL[target]
        w.heat[j] += max(0.0, w.heat[i] - w.heat[j]) * thermal * .08
        w.burn[j] += thermal * (2 if source == SPARK else .4)
        if source == SPARK:
            w.heat[j] = max(w.heat[j], 260.0)
    if source == FIRE and target == WATER:
        transform(w, i, EMPTY, TEMPERATURE[EMPTY]); transform(w, j, VAPOR, 105.0)
    elif source == LAVA and (target == WATER or target == ICE):
        transform(w, i, STONE, 400.0); transform(w, j, VAPOR, 150.0)
    # Conduction alone cannot melt metal: it spreads heat faster than lava can
    # supply it. Hot lava instead dissolves touching metal at a bounded rate.
    elif source == LAVA and target == METAL and w.heat[i] > 800 and random(w) < .03:
        transform(w, j, LAVA, w.heat[i])
    elif source == SAND and target == WATER and not w.phase_locked[i] and not w.phase_locked[j] and random(w) < .015:
        reset(w, i, MUD); reset(w, j, EMPTY)
    elif source == SPARK and ELECTRICAL[target] > .05 and w.life[i] > 10:
        w.charge[j] = min(.9, w.charge[j] + .65)
        w.charge[i] = 0
        w.life[i] = 10  # One finite pulse per spark, rather than unbounded pumping.


@kernel
def explode(w, i, x, y):
    """Detonation: a flash fire plus a bounded overpressure and radial gust that
    throws loose matter outward. Adjacent powder ignites at once, so a connected
    charge goes off within a few ticks."""
    n = w.size; radius = 5
    reset(w, i, FIRE)
    w.life[i] = 60 + int(random(w) * 60)
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            px = x + dx; py = y + dy; distance = math.hypot(dx, dy)
            if not distance or distance > radius or px < 0 or py < 0 or px >= n or py >= n:
                continue
            j = py * n + px; material = w.cells[j]; falloff = 1 - distance / (radius + 1)
            ux = dx / distance; uy = dy / distance
            pressurize(w, j, 18 * falloff)
            gust(w, j, ux * 3 * falloff, uy * 3 * falloff)
            if material == GUNPOWDER:
                if distance < 2:
                    w.burn[j] = 1
            elif not material and distance < 2.5 and random(w) < .6:
                reset(w, j, FIRE)
                w.life[j] = 40 + int(random(w) * 60)
            elif material and STATE[material] != SOLID and material != BACTERIUM:
                w.vx[j] += ux * 2.5 * falloff; w.vy[j] += uy * 2.5 * falloff
    pressurize(w, i, 18)


@hot
def submerged(w, i, x, y):
    """Feesh swim only while touching water; otherwise they are inert matter."""
    n = w.size; cells = w.cells
    return ((x > 0 and cells[i - 1] == WATER) or (x < n - 1 and cells[i + 1] == WATER) or
            (y > 0 and cells[i - n] == WATER) or (y < n - 1 and cells[i + n] == WATER))


@hot
def _boid_open(w, x, y, ux, uy, medium):
    n = w.size
    ax = js_round(x + ux * 3); ay = js_round(y + uy * 3)
    return ax >= 0 and ay >= 0 and ax < n and ay < n and (w.cells[ay * n + ax] == medium or w.cells[ay * n + ax] == BOID)


@kernel
def boid(w, i, x, y):
    """Reynolds boids on the grid: alignment, cohesion, and separation among the
    same form within BOID_RADIUS, plus look-ahead obstacle avoidance and wall
    repulsion. Birds move through air; feesh swap places with water."""
    n = w.size; fish = w.polarity[i] < 0; medium = WATER if fish else EMPTY
    w.life[i] = (w.life[i] + 1) & 0xffff
    if fish and not submerged(w, i, x, y):
        transport_particle(w, i, x, y)
        return
    count = 0; heading_x = 0.0; heading_y = 0.0; center_x = 0.0; center_y = 0.0; away_x = 0.0; away_y = 0.0
    for dy in range(-BOID_RADIUS, BOID_RADIUS + 1):
        for dx in range(-BOID_RADIUS, BOID_RADIUS + 1):
            px = x + dx; py = y + dy; distance = dx * dx + dy * dy
            if not distance or distance > BOID_RADIUS * BOID_RADIUS or px < 0 or py < 0 or px >= n or py >= n:
                continue
            j = py * n + px
            if w.cells[j] != BOID or w.polarity[j] != w.polarity[i]:
                continue
            count += 1; heading_x += w.vx[j]; heading_y += w.vy[j]; center_x += dx; center_y += dy
            if distance <= 2:
                away_x -= dx / distance; away_y -= dy / distance
    vx = w.vx[i]; vy = w.vy[i]
    if count:
        vx += (heading_x / count - vx) * .08 + center_x / count * .004 + away_x * .04
        vy += (heading_y / count - vy) * .08 + center_y / count * .004 + away_y * .04
    # Look ahead along the heading; turn toward whichever side is open.
    speed = math.sqrt(vx * vx + vy * vy) or 1.0
    ux = vx / speed; uy = vy / speed
    if not _boid_open(w, x, y, ux, uy, medium):
        left = _boid_open(w, x, y, ux * .5 + uy * .87, uy * .5 - ux * .87, medium)
        right = _boid_open(w, x, y, ux * .5 - uy * .87, uy * .5 + ux * .87, medium)
        turn = (1 if random(w) < .5 else -1) if left == right else 1 if left else -1
        vx += uy * .12 * turn; vy -= ux * .12 * turn
    margin = 3
    # Active flight/swimming counters moderate fields with bounded thrust.
    # Stronger fields still overpower it; stranded feesh use ordinary transport.
    gravity = math.hypot(w.gravity_x[i], w.gravity_y[i])
    residual = max(0.0, 1 - .05 / gravity) if gravity else 0.0
    vx += ((.03 if x < margin else 0.0) - (.03 if x >= n - margin else 0.0) + (random(w) - .5) * .04 +
           w.wind_x[i] * .02 + w.gravity_x[i] * residual)
    vy += ((.03 if y < margin else 0.0) - (.03 if y >= n - margin else 0.0) + (random(w) - .5) * .04 +
           w.wind_y[i] * .02 + w.gravity_y[i] * residual)
    # Hold speed within bounds; ease down from bursts (e.g. explosions).
    maximum = FEESH_MAX_SPEED if fish else BOID_MAX_SPEED
    current = math.sqrt(vx * vx + vy * vy)
    if not current:
        scale = 0.0
    elif current > maximum:
        scale = max(maximum / current, .9)
    elif current < BOID_MIN_SPEED:
        scale = BOID_MIN_SPEED / current
    else:
        scale = 1.0
    w.vx[i] = vx * scale if scale else BOID_MIN_SPEED
    w.vy[i] = vy * scale if scale else 0.0
    # Facing (for the fish glyph) changes only on a clear horizontal heading.
    if abs(w.vx[i]) > .05:
        w.branch[i] = -1 if w.vx[i] < 0 else 1
    w.travel_x[i] += w.vx[i]; w.travel_y[i] += w.vy[i]
    step_x = math.trunc(w.travel_x[i]); step_y = math.trunc(w.travel_y[i])
    w.travel_x[i] -= step_x; w.travel_y[i] -= step_y
    tick = w.tick[0]
    if step_x:
        tx = x + sign(step_x); j = y * n + tx
        if tx >= 0 and tx < n and w.cells[j] == medium and w.moved[j] != tick:
            exchange(w, i, j); i = j; x = tx
        else:
            w.vx[i] *= -.5; w.travel_x[i] = 0
    if step_y:
        ty = y + sign(step_y); j = ty * n + x
        if ty >= 0 and ty < n and w.cells[j] == medium and w.moved[j] != tick:
            exchange(w, i, j)
        else:
            w.vy[i] *= -.5; w.travel_y[i] = 0


@hot
def supported(w, root):
    below = root + w.size
    return below < w.length and (w.cells[below] == SAND or w.cells[below] == MUD)


@kernel
def absorb(w, root):
    if w.moisture[root] >= 18:
        return
    n = w.size; x = root % n; y = root // n
    for dy in range(-1, 3):
        for dx in range(-2, 3):
            if x + dx < 0 or x + dx >= n or y + dy < 0 or y + dy >= n:
                continue
            j = (y + dy) * n + x + dx
            if w.cells[j] == WATER and not w.phase_locked[j]:
                reset(w, j, EMPTY); w.moisture[root] += 6
                return
            if w.cells[j] == MUD and w.moisture[j] >= .25:
                w.moisture[j] -= .25; w.moisture[root] += 2
                return


@kernel
def grow(w, i, x, y):
    n = w.size
    root = w.roots[i]
    if root < 0:
        if not supported(w, i):
            return False
        absorb(w, i)
        if w.moisture[i] < 1:
            return False
        root = i; w.roots[i] = i; w.life[i] = 1
    if w.cells[root] != SEED or w.roots[root] != root or not supported(w, root):
        w.roots[i] = -1; w.life[i] = 0
        return False
    if root == i and w.tick[0] % 20 == 0:
        absorb(w, root)
    if w.life[i] != 1 or not y or w.moisture[root] < 1 or random(w) > .025:
        return True
    direction = int(w.branch[i])
    if not direction and random(w) < .35:
        direction = -1 if random(w) < .5 else 1
    grown = 0
    split = w.generation[i] < 4 and random(w) < .2
    for attempt in range(2 if split else 1):
        if split:
            dx = 1 if attempt else -1
        else:
            dx = direction if random(w) < .7 else 0
        if x + dx < 0 or x + dx >= n or w.moisture[root] < 1:
            continue
        j = (y - 1) * n + x + dx
        if w.cells[j]:
            continue
        place(w, j, SEED, w.heat[i], w.phase_locked[i] != 0, False)
        w.roots[j] = root; w.life[j] = 1
        w.branch[j] = dx; w.generation[j] = w.generation[i] + (1 if split else 0)
        w.moisture[root] -= 1; grown += 1
    if grown:
        w.life[i] = 2  # Mature stem; only the new tips extend.
    return True


@kernel
def drift(w, i, x, y):
    dx = js_round(w.vx[i] + (random(w) - .5) * .7)
    dy = js_round(w.vy[i] + (random(w) - .5) * .7)
    if not dx and not dy:
        dx = -1 if random(w) < .5 else 1
    if not move(w, i, x + sign(dx), y + sign(dy), False):
        w.vx[i] *= -.8; w.vy[i] *= -.8


@hot
def _support_visit(w, j, dx, dy, down, tail):
    material = w.cells[j]
    if w.supported_matter[j] or not material or STATE[material] == GAS or material == SPARK:
        return tail
    if dx * w.gravity_x[j] + dy * (w.gravity_y[j] + down) <= 1e-9:
        return tail
    w.supported_matter[j] = 1; w.support_queue[tail] = j
    return tail + 1


@kernel
def update_support(w):
    # One linear-time snapshot per tick. Support propagates uphill from fixed
    # obstacles and chamber boundaries, never from an airborne fluid cluster.
    n = w.size; supported_matter = w.supported_matter; queue = w.support_queue
    down = 0.0 if w.zero_gravity[0] else NORMAL_GRAVITY
    fill(supported_matter, 0)
    head = 0; tail = 0
    i = 0
    for y in range(n):
        for x in range(n):
            material = w.cells[i]
            if material and STATE[material] != GAS and material != SPARK:
                gx = w.gravity_x[i]; gy = w.gravity_y[i] + down
                if (blocked(w, i) or (x == 0 and gx < -1e-9) or (x == n - 1 and gx > 1e-9) or
                        (y == 0 and gy < -1e-9) or (y == n - 1 and gy > 1e-9)):
                    supported_matter[i] = 1; queue[tail] = i; tail += 1
            i += 1
    while head < tail:
        i = queue[head]; head += 1
        x = i % n; y = i // n
        if x:
            tail = _support_visit(w, i - 1, 1, 0, down, tail)
        if x + 1 < n:
            tail = _support_visit(w, i + 1, -1, 0, down, tail)
        if y:
            tail = _support_visit(w, i - n, 0, 1, down, tail)
        if y + 1 < n:
            tail = _support_visit(w, i + n, 0, -1, down, tail)
    w.support_tick[0] = w.tick[0]


@hot
def _liquid_neighbor(w, j, surrounding, neighbors):
    if w.supported_matter[j] and STATE[w.cells[j]] == LIQUID:
        return surrounding + density(w, j), neighbors + 1
    return surrounding, neighbors


@kernel
def transport_particle(w, i, x, y):
    if w.support_tick[0] != w.tick[0]:
        update_support(w)
    n = w.size
    material = w.cells[i]
    gas = STATE[material] == GAS; liquid = STATE[material] == LIQUID
    gx = w.gravity_x[i]; gy = w.gravity_y[i] + (0.0 if w.zero_gravity[0] else NORMAL_GRAVITY)
    magnitude = math.hypot(gx, gy)
    ux = gx / magnitude if magnitude else 0.0; uy = gy / magnitude if magnitude else 0.0
    scale = max(abs(gx), abs(gy))
    down_x = js_round(gx / scale) if scale else 0; down_y = js_round(gy / scale) if scale else 0
    above_x = x - down_x; above_y = y - down_y
    above = above_y * n + above_x
    exposed = (magnitude > 1e-9 and 0 <= above_x < n and 0 <= above_y < n and
               (not w.cells[above] or STATE[w.cells[above]] == GAS))
    # Surface grains feel the faster air just above the bed, not only the
    # stagnant air at their centers. Shear lifts exposed matter into the flow.
    air_x = w.wind_x[i] * .5 + w.wind_x[above] * .5 if exposed else w.wind_x[i]
    air_y = w.wind_y[i] * .5 + w.wind_y[above] * .5 if exposed else w.wind_y[i]
    shear = abs(air_x * uy - air_y * ux)
    if gas:
        drag = .12
    else:
        drag = (.08 + .08 * min(1.0, math.sqrt(air_x * air_x + air_y * air_y))) / (DENSITY[material] + .25)
    below_x = x + down_x; below_y = y + down_y
    on_surface = (not (0 <= below_x < n and 0 <= below_y < n) or
                  (w.cells[below_y * n + below_x] != 0 and STATE[w.cells[below_y * n + below_x]] != GAS))
    vx = w.vx[i]; vy = w.vy[i]
    vx += (air_x * .5 - vx) * drag
    vy += (air_y * .5 - vy) * drag
    if gas:
        # Temperature is a proxy for molecular agitation and expansion. Unlike
        # gravity-driven matter, gas diffuses in every direction with mild lift.
        agitation = max(.3, min(2.5, (w.heat[i] + 273) / 393))
        vx += (random(w) - .5) * .5 * agitation
        jitter = (random(w) - .5) * .5 * agitation
        lift = max(-.04, min(.04, (w.heat[i] - w.air_heat[i]) * .00012)) / NORMAL_GRAVITY
        vx -= gx * lift; vy += jitter - gy * lift
        pressurize(w, i, max(0.0, w.heat[i] - 20) * .00002)
    else:
        if magnitude > 1e-9:
            # Immersed liquids feel displaced-fluid weight; hot parcels can rise
            # through colder parcels instead of being forced down every tick.
            surrounding = 0.0; neighbors = 0
            if liquid and w.supported_matter[i]:
                if x:
                    surrounding, neighbors = _liquid_neighbor(w, i - 1, surrounding, neighbors)
                if x + 1 < n:
                    surrounding, neighbors = _liquid_neighbor(w, i + 1, surrounding, neighbors)
                if y:
                    surrounding, neighbors = _liquid_neighbor(w, i - n, surrounding, neighbors)
                if y + 1 < n:
                    surrounding, neighbors = _liquid_neighbor(w, i + n, surrounding, neighbors)
            buoyancy = 1 - surrounding / neighbors / density(w, i) if neighbors >= 2 else 1.0
            vx += gx * buoyancy; vy += gy * buoyancy
        if exposed and on_surface and shear > .4:
            lift = min(.12, (shear - .4) * .045 / (DENSITY[material] + .25))
            vx -= ux * lift; vy -= uy * lift
    w.vx[i] = max(-3.0, min(3.0, vx))
    w.vy[i] = max(-3.0, min(3.0, vy))
    w.travel_x[i] += w.vx[i]; w.travel_y[i] += w.vy[i]
    dx = math.trunc(w.travel_x[i]); dy = math.trunc(w.travel_y[i])
    w.travel_x[i] -= dx; w.travel_y[i] -= dy
    steps = max(abs(dx), abs(dy))
    previous_x = 0; previous_y = 0
    # Sweep at most three cells, checking every crossed cell (no tunneling).
    for step in range(1, steps + 1):
        offset_x = js_round(dx * step / steps); offset_y = js_round(dy * step / steps)
        sx = offset_x - previous_x; sy = offset_y - previous_y
        previous_x = offset_x; previous_y = offset_y
        if sx:
            if move(w, i, x + sx, y, True):
                x += sx; i = y * n + x
            else:
                w.vx[i] *= -.5 if gas else -.1; w.travel_x[i] = 0
        if sy:
            if move(w, i, x, y + sy, True):
                y += sy; i = y * n + x
            else:
                w.vy[i] *= -.5 if gas else -.1; w.travel_y[i] = 0
    if gas or magnitude < 1e-9 or (liquid and not w.supported_matter[i]):
        return
    support_x = x + down_x; support_y = y + down_y
    if 0 <= support_x < n and 0 <= support_y < n:
        support = w.cells[support_y * n + support_x]
        if not support or STATE[support] == GAS:
            return
    tangent = w.vx[i] * uy - w.vy[i] * ux
    if abs(tangent) > .1:
        side = sign(tangent)
    else:
        side = -1 if random(w) < .5 else 1
    mobile = random(w) < (.6 * (1 - VISCOSITY[material]) if liquid else .35)
    # Neighbor steps on either side of the downhill direction. Clamp diagonal
    # combinations to one cell so settling cannot leap over a thin obstacle.
    if mobile and (move(w, i, x + sign(down_x + side * down_y), y + sign(down_y - side * down_x), True) or
                   move(w, i, x + sign(down_x - side * down_y), y + sign(down_y + side * down_x), True)):
        return
    if liquid and mobile and (move(w, i, x + side * down_y, y - side * down_x, True) or
                              move(w, i, x - side * down_y, y + side * down_x, True)):
        return
    friction = .985 if shear > .4 else .9 - VISCOSITY[material] * .3 if liquid else .65
    w.vx[i] -= tangent * uy * (1 - friction)
    w.vy[i] += tangent * ux * (1 - friction)


@kernel
def scramble(w, i, x, y):
    n = w.size
    # One conversion per eight ticks for a readable, bounded reaction rate.
    if w.phase_locked[i] and (w.tick[0] + i) % 8:
        return
    start = int(math.floor(random(w) * 4))
    for turn in range(4):
        direction = (start + turn) % 4
        nx = x + (-1 if direction == 0 else 1 if direction == 1 else 0)
        ny = y + (-1 if direction == 2 else 1 if direction == 3 else 0)
        if nx < 0 or ny < 0 or nx >= n or ny >= n:
            continue
        j = ny * n + nx; target = w.cells[j]
        if not target or target == SCRAMBLE or w.phase_locked[j]:
            continue
        # Only real materials (not Erase, Wind, or Scramble), always a change.
        choice = int(math.floor(random(w) * (len(SCRAMBLE_RESULTS) - 1)))
        if choice >= SCRAMBLE_INDEX[target]:
            choice += 1
        reset(w, j, SCRAMBLE_RESULTS[choice])
        if not w.phase_locked[i]:
            reset(w, i, EMPTY)
        return


@njit(cache=True)
def gravity(w):  # Allocates; runs with reference counting.
    if not w.gravity_dirty[0]:
        return
    w.gravity_dirty[0] = 0
    n = w.size
    sources = np.flatnonzero(w.cells == GRAV)
    xs = (sources % n).astype(np.float64); ys = (sources // n).astype(np.float64)
    signs = w.polarity[sources].astype(np.float64)
    radial_gravity(n, xs, ys, signs, w.gravity_x, w.gravity_y, GRAV_STRENGTH)
    w.gravity_x[:] *= w.grav_strength[0]; w.gravity_y[:] *= w.grav_strength[0]


@kernel
def bacteria(w):
    if w.tick[0] % 12:
        return
    n = w.size
    fill(w.neighbors, 0); fill(w.locked_neighbors, 0)
    for i in range(w.length):
        if w.cells[i] != BACTERIUM:
            continue
        x = i % n; y = i // n
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                if (not dx and not dy) or x + dx < 0 or x + dx >= n or y + dy < 0 or y + dy >= n:
                    continue
                j = i + dy * n + dx
                w.neighbors[j] += 1; w.locked_neighbors[j] += w.phase_locked[i]
    # Conway's rules apply to every colony. Phase lock only isolates cells from
    # other elements: locked cells do not eat, overheat, or react.
    for i in range(w.length):
        material = w.cells[i]; neighbors = w.neighbors[i]; locked = w.locked_neighbors[i]
        if material == BACTERIUM and neighbors != 2 and neighbors != 3:
            reset(w, i, EMPTY)
        elif not material and neighbors == 3:
            place(w, i, BACTERIUM, 20.0, locked >= 2, False)
        elif material == SEED and not w.phase_locked[i] and neighbors > locked:
            reset(w, i, BACTERIUM)


@kernel
def _react(w, i, x, y, material):
    """Phase changes and state-driven transformations of an unlocked particle.
    Returns False when the particle is gone or has detonated."""
    heat = w.heat[i]
    if (material == BACTERIUM or material == BOID) and (heat > 90 or heat < -10):
        reset(w, i, EMPTY)
        return False
    if material == GUNPOWDER and (w.burn[i] >= 1 or heat > 180):
        explode(w, i, x, y)
        return False
    if material == METAL and heat > 800:
        transform(w, i, LAVA, heat)
    if material == WATER and heat > 100:
        transform(w, i, VAPOR, heat)
    elif material == WATER and heat < 0:
        transform(w, i, ICE, heat)
    elif material == ICE and heat > 1:
        transform(w, i, WATER, heat)
    elif material == NITROGEN and heat > -196:
        transform(w, i, VAPOR, heat)
    elif material == VAPOR and w.nitrogen_vapor[i]:
        if heat < -196:
            transform(w, i, NITROGEN, heat)
    elif material == VAPOR and random(w) < condensation_chance(heat):
        transform(w, i, WATER, heat)
    elif material == OIL or material == SEED:
        w.burn[i] += THERMAL[material] * .15 * max(0.0, min(2.0, (heat - 130) / 120))
        if heat < 100:
            w.burn[i] *= .99
        if w.burn[i] >= 1:
            thermal = THERMAL[material]
            reset(w, i, FIRE)
            w.life[i] = js_round(360 + (1 - thermal) * 240 + random(w) * 180)
    elif material == SAND and heat > 300:
        place(w, i, CRYSTAL, heat, False, False)
    elif material == LAVA and heat < 650:
        place(w, i, STONE, heat, False, False)
    elif material == MUD and heat > 110:
        place(w, i, SAND, heat, False, False)
    return True


@kernel
def _burn(w, i, x, y):
    """Fire's heat, pressure, and draft along the local gravity vector."""
    n = w.size
    if not w.phase_locked[i]:
        w.heat[i] = max(w.heat[i], min(650.0, w.life[i] * 8.0))
    pressurize(w, i, .08 * w.heat[i] / 650)
    gx = w.gravity_x[i]; gy = w.gravity_y[i] + (0.0 if w.zero_gravity[0] else NORMAL_GRAVITY)
    gust(w, i, (random(w) - .5) * .035 - gx * (.07 / NORMAL_GRAVITY), -gy * (.07 / NORMAL_GRAVITY))
    peak = max(abs(gx), abs(gy))
    if peak > 1e-9:
        ax = x - js_round(gx / peak); ay = y - js_round(gy / peak)
        if ax >= 0 and ay >= 0 and ax < n and ay < n:
            gust(w, ay * n + ax, -gx * (.04 / NORMAL_GRAVITY), -gy * (.04 / NORMAL_GRAVITY))


@kernel
def step(w):
    w.tick[0] += 1
    if w.tick[0] == 0xffffffff:
        w.tick[0] = 1; fill(w.updated, 0); fill(w.moved, 0)
    tick = w.tick[0]
    n = w.size
    # World.step updates gravity first; that kernel allocates.
    electricity(w); air_thermal(w); airflow(w)
    i = 0
    for y in range(n):
        for x in range(n):
            if w.cells[i]:
                if x < n - 1:
                    thermal_pair(w, i, i + 1)
                if y < n - 1:
                    thermal_pair(w, i, i + n)
                if not w.phase_locked[i]:
                    w.heat[i] += w.charge[i] * w.charge[i] * 1.2
                    # Weak radiative loss to the environment, separate from local air exchange.
                    loss = .003 if w.cells[i] == VAPOR else .0004 if w.cells[i] == LAVA else .0001
                    w.heat[i] += (20 - w.heat[i]) * loss
            i += 1
    for y in range(n - 1, -1, -1):
        for col in range(n):
            x = n - 1 - col if (tick + y) % 2 else col
            i = y * n + x
            material = w.cells[i]
            if not material or w.updated[i] == tick:
                continue
            w.updated[i] = tick
            if material == SCRAMBLE:
                scramble(w, i, x, y)
                if not w.cells[i]:
                    continue
            if not w.phase_locked[i] and not _react(w, i, x, y, material):
                continue
            material = w.cells[i]
            if material == FIRE or material == SPARK or material == LAVA or material == SAND:
                if x > 0:
                    contact(w, i, i - 1)
                if x < n - 1:
                    contact(w, i, i + 1)
                if y > 0:
                    contact(w, i, i - n)
                if y < n - 1:
                    contact(w, i, i + n)
                material = w.cells[i]
                if not material:
                    continue
            if material == BOID:
                boid(w, i, x, y)
                continue
            if material == FIRE or material == SPARK:
                if not w.phase_locked[i]:
                    w.life[i] -= 1
                    if w.life[i] == 0:
                        reset(w, i, EMPTY)
                        continue
                if material == FIRE:
                    _burn(w, i, x, y)
                else:
                    drift(w, i, x, y)
                    continue
            if material == SEED and grow(w, i, x, y):
                continue
            if STATE[material] != SOLID and material != BACTERIUM:
                transport_particle(w, i, x, y)
    bacteria(w)


class World:
    """The JavaScript World's interface over a numba-compiled state."""

    def __init__(self, size=112, seed=731):
        self.size = size
        self.length = size * size
        arrays = {name: np.zeros(self.length, dtype) for name, dtype in {**PARTICLE_FIELDS, **GRID_FIELDS}.items()}
        scalars = {name: np.zeros(1, dtype) for name, dtype in SCALAR_FIELDS.items()}
        self.state = State(size=size, length=self.length, **arrays, **scalars)
        for name in arrays:
            setattr(self, name, arrays[name])
        self.state.seed[0] = seed or 731
        self.state.random_override[0] = -1
        self.wind_strength = 10
        self.grav_strength = 1
        # Zero-g removes gravity-driven effects: weight, settling, buoyancy, and
        # convection. Grav sources, wind, and momentum still act.
        self.zero_gravity = False
        self.clear()

    def _scalar(name, kind):
        def get(self):
            return kind(getattr(self.state, name)[0])

        def put(self, value):
            getattr(self.state, name)[0] = value
        return property(get, put)

    tick = _scalar('tick', int)
    seed = _scalar('seed', int)
    wind_strength = _scalar('wind_strength', float)
    grav_strength = _scalar('grav_strength', float)
    zero_gravity = _scalar('zero_gravity', bool)
    support_tick = _scalar('support_tick', int)
    del _scalar

    @property
    def fixed_random(self):
        """When set, every random draw returns this value (tests only)."""
        value = self.state.random_override[0]
        return None if value < 0 else float(value)

    @fixed_random.setter
    def fixed_random(self, value):
        self.state.random_override[0] = -1 if value is None else value

    def clear(self):
        s = self.state
        s.support_tick[0] = -1
        s.gravity_dirty[0] = 1
        # The gravity field is recomputed from its (now absent) sources on demand.
        for name in (*PARTICLE_FIELDS, *GRID_FIELDS):
            if name not in ('gravity_x', 'gravity_y'):
                getattr(s, name).fill(0)
        s.heat.fill(20); s.roots.fill(-1)
        s.air_heat.fill(20); s.next_air_heat.fill(20)
        s.tick[0] = 0

    def set(self, i, id, temperature=None, locked=False, alternate=False):
        place(self.state, int(i), int(id), float(ELEMENTS[id].temperature if temperature is None else temperature),
              bool(locked), bool(alternate))

    def paint(self, x, y, id, diameter=5, strength=1, locked=False, direction_x=1, direction_y=0, alternate=False):
        paint(self.state, float(x), float(y), int(id), int(diameter), float(strength), bool(locked),
              float(direction_x), float(direction_y), bool(alternate))

    def transform(self, i, id, temperature=None):
        transform(self.state, int(i), int(id), float(ELEMENTS[id].temperature if temperature is None else temperature))

    def set_grav_strength(self, value):
        if not math.isfinite(value):
            return
        strength = max(0.0, min(3.0, float(value)))
        if strength == self.grav_strength:
            return
        self.grav_strength = strength
        self.state.gravity_dirty[0] = 1
        self.state.support_tick[0] = -1

    def step(self):
        gravity(self.state)
        step(self.state)

    def gravity(self): gravity(self.state)
    def airflow(self): airflow(self.state)
    def air_thermal(self): air_thermal(self.state)
    def electricity(self): electricity(self.state)
    def update_support(self): update_support(self.state)
    def blocked(self, i): return blocked(self.state, int(i))
    def density(self, i): return density(self.state, int(i))
    def move(self, i, x, y, displace=False): return move(self.state, int(i), int(x), int(y), bool(displace))
    def transport_particle(self, i, x, y): transport_particle(self.state, int(i), int(x), int(y))
    def boid(self, i, x, y): boid(self.state, int(i), int(x), int(y))
    def submerged(self, i, x, y): return submerged(self.state, int(i), int(x), int(y))
    def scramble(self, i, x, y): scramble(self.state, int(i), int(x), int(y))
    def grow(self, i, x, y): return grow(self.state, int(i), int(x), int(y))
    def contact(self, i, j): contact(self.state, int(i), int(j))
    def thermal_pair(self, a, b): thermal_pair(self.state, int(a), int(b))
    def gust(self, i, x, y): gust(self.state, int(i), float(x), float(y))
    def pressurize(self, i, amount): pressurize(self.state, int(i), float(amount))

    def scene(self, name='estuary'):
        self.clear()
        n = self.size
        margin = max(1, math.floor(n * .025)); far = n - margin - 1

        def chamber():
            def inside(x, y):
                return (margin <= x <= far and margin <= y <= far and
                        min(x - margin, far - x) + min(y - margin, far - y) >= 2)
            for y in range(margin, far + 1):
                for x in range(margin, far + 1):
                    if not inside(x, y):
                        continue
                    # An eight-neighbor rim seals the stepped corners against diagonal motion.
                    if any(not inside(x + dx, y + dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1)):
                        self.set(y * n + x, CRYSTAL)

        if name == 'convection':
            chamber()
            width = max(4, math.floor(n * .28)); depth = max(2, math.floor(n * .035))
            # Matched glass reservoirs: a low heater and a suspended cooling bath.
            for left, top, material, temperature in ((margin + 3, far - depth - 2, LAVA, 1100),
                                                     (far - width - 2, margin + 2, NITROGEN, -200)):
                for y in range(top, top + depth + 2):
                    for x in range(left, left + width + 1):
                        wall = x == left or x == left + width or y == top + depth + 1
                        self.set(y * n + x, CRYSTAL if wall else material, 20 if wall else temperature, not wall)
            for y in range(margin + 3, far - 2):
                for x in range(margin + 2, far - 1):
                    i = y * n + x
                    if not self.cells[i] and (x + 3 * y) % 9 == 0:
                        self.set(i, VAPOR, 20, True)
            return
        if name == 'water-cycle':
            chamber()
            left, right, floor = margin, far, math.floor(n * .78)
            # A melting-point ice ceiling is a permanent cold reservoir without
            # freezing the rain. A compact, enclosed heater balances its heat removal.
            for x in range(left + 3, right - 2):
                self.set((margin + 1) * n + x, ICE, 0, True)
            # A thin crystal basin conducts heat from an isolated, perpetual lava bath.
            # The cool upper chamber leaves room for clouds and returning rain.
            hearth_left, hearth_right = math.floor(n * .44), math.ceil(n * .56)
            hearth_floor = min(far - 1, floor + 4)
            for x in range(left, right + 1):
                self.set(floor * n + x, CRYSTAL)
                if left < x < right:
                    for y in range(floor - max(2, math.floor(n * .04)), floor):
                        self.set(y * n + x, WATER)
                for y in range(floor + 1, far):
                    if ((x == hearth_left or x == hearth_right) and y <= hearth_floor or
                            y == hearth_floor and hearth_left <= x <= hearth_right):
                        self.set(y * n + x, STONE)
                    elif hearth_left < x < hearth_right and floor + 1 < y < hearth_floor:
                        self.set(y * n + x, LAVA, 1100, True)
            return
        if name == 'test-tubes':
            top, bottom, half = math.floor(n * .19), math.floor(n * .66), max(2, math.floor(n * .055))
            gap = max(2, math.floor(n * .05)); pot_floor = min(n - 2, bottom + gap + 2)
            for tube, material in enumerate((WATER, OIL, ICE)):
                center = math.floor(n * (.2 + tube * .3))

                def inside(x, y):
                    return (abs(x - center) <= half and y <= bottom and
                            (y <= bottom - half or (x - center) ** 2 + (y - (bottom - half)) ** 2 <= (half + .5) ** 2))
                for y in range(top, bottom + 1):
                    for x in range(center - half, center + half + 1):
                        if not inside(x, y):
                            continue
                        if any(not inside(x + dx, y + dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1)):
                            self.set(y * n + x, CRYSTAL)
                        elif y > bottom - n * .18:
                            self.set(y * n + x, material)
                # Open side pockets accept a painted heat source without opening the tube.
                # On the smallest grids the outer holders reach past the chamber walls.
                pot_half = min(half + gap, math.floor(n * .14))
                holders = [(center - pot_half, y) for y in range(bottom - half, pot_floor + 1)]
                holders += [(center + pot_half, y) for y in range(bottom - half, pot_floor + 1)]
                holders += [(x, pot_floor) for x in range(center - pot_half, center + pot_half + 1)]
                for x, y in holders:
                    if 0 <= x < n:
                        self.set(y * n + x, STONE)
            return
        for y in range(n):
            for x in range(n):
                px, py = x / n, y / n
                floor = .84 + math.sin(px * 9) * .04
                if py > floor:
                    self.set(y * n + x, SAND)
                elif py > .72 and px < .55:
                    self.set(y * n + x, WATER)
                elif .68 < py < .72 and px < .35:
                    self.set(y * n + x, OIL)
                elif .53 < py < .55 and .57 < px < .85:
                    self.set(y * n + x, STONE)
        self.paint(n * .45, n * .69, SEED, 7)
        self.paint(n * .7, n * .45, SAND, 11)
        self.paint(n * .25, n * .25, VAPOR, 11)
