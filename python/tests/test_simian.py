"""Port of tests/simian.test.mjs, test for test and in the same order."""
import math

import numpy as np
import pytest

from simian.aim import Direction, smooth_aim
from simian.clock import TICK_RATE, Clock, ticks_due
from simian.engine import (ANTIGRAV_COLOR, ELEMENTS, FEESH_COLOR, GRAV_STRENGTH, ID, MAX_AIR_SPEED, MAX_PRESSURE,
                           NORMAL_GRAVITY, World, condensation_chance, element_symbol)
from simian.gravity import radial_gravity
from simian.raster import blocked_mask, glyph_variant, temperature_pixels, trace_contours

SQRT1_2 = math.sqrt(.5)


def count(world, id):
    return int(np.count_nonzero(world.cells == id))


def index_of(array, value):
    """JavaScript indexOf: the first matching index, or -1."""
    matches = np.flatnonzero(array == value)
    return int(matches[0]) if len(matches) else -1


def mean_x(world, id, total):
    return float(np.sum(np.flatnonzero(world.cells == id) % world.size)) / total


def test_gravity_strength_rescales_existing_sources_and_survives_clearing():
    w = World(24); w.set(12 * 24 + 12, ID.GRAV); w.gravity()
    initial = w.gravity_x.copy()
    w.set_grav_strength(.5); w.gravity()
    assert np.all(np.abs(w.gravity_x - initial * .5) < 1e-8)
    w.set_grav_strength(3); w.gravity()
    assert np.all(np.abs(w.gravity_x - initial * 3) < 1e-7)
    w.clear(); assert w.grav_strength == 3
    w.set(100, ID.GRAV, 20, False, True); w.set_grav_strength(0); w.gravity()
    assert not w.gravity_x.any() and not w.gravity_y.any()


@pytest.mark.parametrize('fish', [False, True])
def test_birds_and_swimming_feesh_counter_moderate_gravity_but_strong_fields_overpower_them(fish):
    def accelerate(force):
        w, i = World(24), 12 * 24 + 12
        if fish:
            for y in range(8, 17):
                for x in range(8, 17):
                    w.set(y * 24 + x, ID.WATER, 20, True)
        w.set(i, ID.BOID, 20, False, fish); w.fixed_random = .5
        w.vx[i] = .3; w.vy[i] = 0; w.gravity_y[i] = force
        w.boid(i, 12, 12)
        return w.vy[i]
    assert abs(accelerate(.04)) < 1e-8
    assert abs(accelerate(.06) - .01) < 1e-7
    assert accelerate(.18) > .12
    assert accelerate(-.18) < -.12


def test_airborne_liquid_rows_and_blobs_accelerate_together_in_every_gravity_direction():
    n = 32
    for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0), (SQRT1_2, SQRT1_2)]:
        for depth in (0, 2):
            w = World(n); w.zero_gravity = True
            w.gravity_x.fill(dx * NORMAL_GRAVITY); w.gravity_y.fill(dy * NORMAL_GRAVITY)
            cells = []
            for y in range(16 - depth, 17 + depth):
                for x in range(13, 20):
                    i = y * n + x; w.set(i, ID.WATER, 20, True); cells.append(i)
            w.update_support()
            assert all(not w.supported_matter[i] for i in cells), 'no airborne parcel has hydrostatic support'
            for i in cells:
                w.transport_particle(i, i % n, i // n)
            for i in cells:
                assert abs(w.vx[i] - dx * NORMAL_GRAVITY) < 1e-7
                assert abs(w.vy[i] - dy * NORMAL_GRAVITY) < 1e-7


def test_fluid_support_reaches_through_a_resting_column_and_disappears_when_its_floor_is_removed():
    w = World(24)
    for y in range(8, 17):
        w.set(y * 24 + 12, ID.WATER, 20, True)
    w.set(17 * 24 + 12, ID.STONE); w.update_support()
    assert w.supported_matter[8 * 24 + 12]
    w.set(17 * 24 + 12, ID.EMPTY); w.tick += 1
    w.transport_particle(8 * 24 + 12, 12, 8)
    assert not w.supported_matter[8 * 24 + 12]
    assert w.vy[8 * 24 + 12] > 0, 'the top falls immediately, not only when neighbors peel away'


def test_density_sorting_liquid_buoyancy_and_settling_rotate_with_net_gravity():
    n = 16; i = 8 * n + 8
    for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
        w = World(n); w.zero_gravity = True; w.tick = 1
        w.gravity_x.fill(dx * NORMAL_GRAVITY); w.gravity_y.fill(dy * NORMAL_GRAVITY)
        w.set(i, ID.WATER, 20, True); w.set(i + dx + dy * n, ID.OIL, 20, True)
        assert w.move(i, 8 + dx, 8 + dy, True), 'dense liquid sinks along gravity'
        w.tick += 1
        assert not w.move(i + dx + dy * n, 8, 8, True), 'dense liquid cannot rise through lighter liquid'
        w.set(i, ID.WATER, 90, True)
        for j in (i - 1, i + 1, i - n, i + n):
            w.set(j, ID.WATER, 10, True)
        for side in (-1, 0, 1):
            w.set(i + 2 * (dx + dy * n) + side * (dy - dx * n), ID.STONE)
        # Give the side parcels a continuous supported column as well.
        for side in (-1, 1):
            w.set(i + dx + dy * n + side * (dy - dx * n), ID.WATER, 10, True)
        w.transport_particle(i, 8, 8)
        warm = index_of(w.heat, 90)
        assert w.vx[warm] * dx + w.vy[warm] * dy < 0, 'warm parcel rises opposite gravity'
        w.cells.fill(0); w.set(i, ID.SAND); w.set(i + dx + dy * n, ID.STONE)
        w.update_support()
        w.fixed_random = 0
        w.transport_particle(i, 8, 8)
        sand = index_of(w.cells, ID.SAND)
        assert (sand % n - 8) * dx + (sand // n - 8) * dy > 0, 'supported grains settle downhill even in zero-g with custom gravity'


def test_density_displacement_uses_combined_gravity_and_vanishes_when_gravity_cancels():
    w = World(16); i = 8 * 16 + 8
    w.tick = 1; w.gravity_y.fill(-.06)
    w.set(i, ID.WATER); w.set(i - 16, ID.OIL)
    assert w.move(i, 8, 7, True), 'custom upward gravity overcomes ordinary gravity'
    w.tick += 1; w.gravity_y.fill(-NORMAL_GRAVITY)
    w.set(i, ID.WATER); w.set(i + 16, ID.OIL)
    assert not w.move(i, 8, 9, True), 'no density sorting without net gravity'


def test_thermal_air_and_gas_buoyancy_follow_sideways_custom_gravity():
    w = World(16); i = 8 * 16 + 8
    w.zero_gravity = True; w.gravity_x.fill(NORMAL_GRAVITY)
    w.air_heat.fill(120); w.airflow()
    assert w.wind_x[i] < 0 and w.wind_y[i] == 0, 'hot air rises against sideways gravity'
    w.wind_x.fill(0); w.wind_y.fill(0); w.air_heat.fill(20)
    w.set(i, ID.VAPOR, 120, True); w.fixed_random = .5
    w.transport_particle(i, 8, 8)
    assert w.vx[i] < 0 and w.vy[i] == 0, 'gas has no hardcoded upward bias'


def test_gravity_is_radial_symmetric_softened_reversible_and_cached():
    w = World(65); center = 32 * 65 + 32
    w.set(center, ID.GRAV); w.gravity()
    axial, diagonal = center + 25, center + 15 + 20 * 65

    def strength(i):
        return math.hypot(w.gravity_x[i], w.gravity_y[i])
    assert abs(strength(axial) - strength(diagonal)) < 1e-8, 'equal Euclidean distances have equal strength'
    assert abs(w.gravity_x[diagonal] / w.gravity_y[diagonal] - 15 / 20) < 1e-6, 'force points directly at source'
    assert strength(center) == 0, 'no singularity or self-force'
    assert w.gravity_x[center - 25] == -w.gravity_x[axial]
    assert strength(center + 20) > strength(center + 30), 'strength decays radially'
    original = w.gravity_x.copy()
    w.gravity(); assert np.array_equal(w.gravity_x, original)
    w.set(center, ID.GRAV, 20, False, True); w.gravity()
    assert np.all(np.abs(w.gravity_x + original) < 1e-8)
    w.set(center, ID.EMPTY); w.gravity()
    assert not w.gravity_x.any() and not w.gravity_y.any()


def test_many_source_gravity_closely_matches_direct_radial_forces_including_mixed_polarities():
    n = 32
    positions = [i * 79 % (n * n) for i in range(80)]
    xs = np.array([p % n for p in positions], float); ys = np.array([p // n for p in positions], float)
    signs = np.array([1 if i % 3 else -1 for i in range(80)], float)
    field_x, field_y = np.zeros(n * n), np.zeros(n * n)
    radial_gravity(n, xs, ys, signs, field_x, field_y, GRAV_STRENGTH)
    error = 0
    for y in range(n):
        for x in range(n):
            dx, dy = xs - x, ys - y
            r2 = dx * dx + dy * dy + 9
            factor = 5 * signs / (r2 * np.sqrt(r2))
            fx, fy = float(np.sum(dx * factor)), float(np.sum(dy * factor))
            scale = min(1, GRAV_STRENGTH / (math.hypot(fx, fy) or 1)); i = y * n + x
            error += (field_x[i] - fx * scale) ** 2 + (field_y[i] - fy * scale) ** 2
            assert math.hypot(field_x[i], field_y[i]) <= GRAV_STRENGTH + 1e-8
    assert math.sqrt(error / (n * n)) < GRAV_STRENGTH * .03, 'RMS error below 3% of the acceleration cap'


def test_liquid_nitrogen_cools_air_boils_into_vapor_and_respects_phase_lock():
    w = World(24)
    w.set(200, ID.NITROGEN)
    for _ in range(120):
        w.step()
    assert count(w, ID.NITROGEN) == 0
    assert count(w, ID.VAPOR) == 1
    assert count(w, ID.WATER) == 0, 'nitrogen vapor does not condense into water'
    assert w.nitrogen_vapor[index_of(w.cells, ID.VAPOR)] == 1
    w.clear(); w.set(200, ID.NITROGEN, -200, True)
    for _ in range(120):
        w.step()
    i = index_of(w.cells, ID.NITROGEN)
    assert i >= 0; assert w.heat[i] == -200; assert w.phase_locked[i] == 1
    assert np.any(w.air_heat < 10), 'moving nitrogen significantly cools the air along its path'
    w.clear(); w.set(200, ID.NITROGEN); w.transform(200, ID.VAPOR, -210)
    w.step(); assert count(w, ID.NITROGEN) == 1
    w.clear(); assert not w.nitrogen_vapor.any()


def test_temperature_overlay_maps_air_and_matter_with_neutral_ambient_and_bounded_opacity():
    world = World(4)
    world.air_heat[0] = -25; world.air_heat[1] = 200
    world.set(2, ID.LAVA, 1100, True)
    for dark in (False, True):
        data = temperature_pixels(world, dark).ravel()
        assert data[2] > data[0], 'cold air is blue'
        assert data[4] > data[6], 'hot air is red'
        assert data[11] > data[7], 'lava is more intense than warm air'
        assert data[15] == 0, 'ambient air stays transparent'
        assert np.all(data[3::4] <= 110)


def test_aim_filters_pixel_staircase_jitter_and_turns_continuously_through_reversals():
    direction = Direction(1, 0)
    for i in range(80):
        smooth_aim(direction, .15 if i % 2 else 0, 0 if i % 2 else .15)
    assert .6 < direction.x < .8
    assert .6 < direction.y < .8
    before = math.atan2(direction.y, direction.x)
    smooth_aim(direction, -.1, 0)
    assert abs(math.atan2(direction.y, direction.x) - before) < .1
    for _ in range(50):
        smooth_aim(direction, -1, 0)
    assert direction.x < -.99
    assert abs(math.hypot(direction.x, direction.y) - 1) < 1e-10


def test_scramble_persists_alone_converts_a_neighbor_and_respects_locks():
    world = World(20); i, j = 210, 211
    world.set(i, ID.SCRAMBLE)
    world.scramble(i, 10, 10)
    assert world.cells[i] == ID.SCRAMBLE
    world.set(j, ID.STONE); world.scramble(i, 10, 10)
    assert world.cells[i] == ID.EMPTY
    assert ID.SAND <= world.cells[j] <= ID.ICE and world.cells[j] != ID.STONE
    world.set(i, ID.SCRAMBLE, 20, True); world.tick = 6
    world.set(j, ID.WATER, 20, True); world.scramble(i, 10, 10)
    assert world.cells[j] == ID.WATER; assert world.phase_locked[j] == 1
    world.set(j, ID.STONE)
    for t in range(20):
        previous = world.cells[j]; world.tick = 6 + t * 8; world.scramble(i, 10, 10)
        assert world.cells[j] != previous
        assert world.cells[i] == ID.SCRAMBLE; assert world.phase_locked[i] == 1
    assert element_symbol(ID.WATER, True) == '●'
    assert element_symbol(ID.ICE, True) == '✦'
    assert element_symbol(ID.SCRAMBLE, True) == '?'


def test_brush_diameter_is_its_exact_cell_footprint_for_every_supported_size():
    for diameter in range(1, 16):
        world = World(40)
        world.paint(20, 20, ID.STONE, diameter)
        filled = np.flatnonzero(world.cells)
        xs, ys = filled % 40, filled // 40
        assert xs.max() - xs.min() + 1 == diameter
        assert ys.max() - ys.min() + 1 == diameter
        if diameter == 1:
            assert len(xs) == 1
        world.paint(20, 20, ID.EMPTY, diameter)
        assert count(world, ID.STONE) == 0


def test_a_held_wind_nozzle_propagates_forward_and_stops_at_a_solid_wall():
    open_world, wall = World(48), World(48)
    for y in range(48):
        wall.set(y * 48 + 20, ID.STONE)
    for _ in range(120):
        for world in (open_world, wall):
            world.paint(12, 24, ID.WIND, 5, 1, False, 1, 0); world.airflow()
    assert open_world.wind_x[24 * 48 + 24] > .5, 'Held nozzle reaches particles twelve cells ahead'
    assert wall.wind_x[24 * 48 + 24] == 0
    for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1), (.6, .8)]:
        world = World(20); world.paint(10, 10, ID.WIND, 1, 1, False, dx, dy)
        assert abs(world.wind_x[210] - .22 * dx) < .00001
        assert abs(world.wind_y[210] - .22 * dy) < .00001


def test_holding_wind_moves_a_sand_pile_before_releasing_the_brush():
    means = []
    for blowing in (False, True):
        world = World(48)
        for x in range(48):
            world.set(28 * 48 + x, ID.STONE)
        world.paint(22, 25, ID.SAND, 5)
        initial = count(world, ID.SAND)
        for _ in range(150):
            if blowing:
                world.paint(12, 26, ID.WIND, 5, 10, False, 1, 0)
            world.step()
        assert count(world, ID.SAND) == initial
        means.append(mean_x(world, ID.SAND, initial))
    assert means[1] > means[0] + 3


def test_minimum_wind_with_a_small_nozzle_moves_already_settled_powders_and_liquids():
    for material in (ID.SAND, ID.WATER, ID.MUD):
        means = []
        for blowing in (False, True):
            world = World(64)
            for x in range(64):
                world.set(45 * 64 + x, ID.STONE)
            world.paint(24, 43, material, 3)
            for _ in range(120):
                world.step()
            for _ in range(150):
                if blowing:
                    world.paint(18, 43, ID.WIND, 3, 10, False, 1, 0)
                world.step()
            assert count(world, material) == 9
            means.append(mean_x(world, material, 9))
        assert means[1] > means[0] + 8, ELEMENTS[material].name


def test_upper_wind_strengths_retain_distinct_pressure_above_the_old_ceiling_and_stay_bounded():
    weak, strong = World(24), World(24)
    for _ in range(30):
        weak.paint(12, 12, ID.WIND, 1, 5)
        strong.paint(12, 12, ID.WIND, 1, 10)
    center = 12 * 24 + 11
    assert weak.pressure[center] > 6
    assert strong.pressure[center] == weak.pressure[center] * 2
    strong.pressurize(center, 1000)
    assert strong.pressure[center] == MAX_PRESSURE
    for _ in range(100):
        strong.airflow()
    assert np.all(np.isfinite(strong.pressure) & (np.abs(strong.pressure) <= MAX_PRESSURE))
    assert np.all(np.isfinite(strong.wind_x) & (np.abs(strong.wind_x) <= MAX_AIR_SPEED))


def test_phase_lock_preserves_material_and_temperature_through_heat_reactions_and_movement():
    for id, temperature in [(ID.WATER, 200), (ID.VAPOR, 0), (ID.ICE, 80), (ID.LAVA, 400), (ID.OIL, 600),
                            (ID.FIRE, 650), (ID.MUD, 200), (ID.SAND, 600)]:
        world = World(12)
        world.set(65, id, temperature, True)
        world.charge[65] = 2
        for _ in range(650):
            world.step()
        index = index_of(world.cells, id)
        assert index >= 0, ELEMENTS[id].name
        assert world.phase_locked[index] == 1
        assert world.heat[index] == temperature
        assert glyph_variant(world.state, index) == 4
    world = World(12)
    world.set(65, ID.LAVA, 1100, True); world.set(66, ID.WATER, 20, True)
    world.thermal_pair(65, 66); world.contact(65, 66)
    assert world.heat[65] == 1100; assert world.heat[66] == 20
    assert world.cells[65] == ID.LAVA; assert world.cells[66] == ID.WATER
    world.set(66, ID.CRYSTAL); world.thermal_pair(65, 66)
    assert world.heat[66] > 20; assert world.heat[65] == 1100
    world.paint(5, 5, ID.EMPTY, 3)
    assert world.phase_locked[65] == 0


def test_water_cycle_repeatedly_evaporates_and_rains_without_consuming_its_heater_or_water():
    world = World(64); world.scene('water-cycle')
    water, lava = count(world, ID.WATER), count(world, ID.LAVA)
    # Kernels cannot be intercepted as the JavaScript test does, so count net
    # per-tick changes: a lower bound on boiling and condensation events.
    boiled = condensed = 0
    vapor = count(world, ID.VAPOR)
    for _ in range(1800):
        world.step()
        change = count(world, ID.VAPOR) - vapor; vapor += change
        boiled += max(0, change); condensed += max(0, -change)
    assert boiled > water and condensed > water
    assert count(world, ID.WATER) + count(world, ID.VAPOR) == water
    assert count(world, ID.LAVA) == lava
    assert np.any((world.cells == ID.CRYSTAL) & (world.heat > 100))
    assert np.all(world.heat[world.cells == ID.LAVA] == 1100)
    margin = max(1, math.floor(world.size * .025))
    for i in np.flatnonzero((world.cells == ID.WATER) | (world.cells == ID.VAPOR)):
        x, y = i % world.size, i // world.size
        assert margin < x < world.size - margin - 1 and margin < y < math.floor(world.size * .8), \
            'water and vapor remain inside the basin chamber'


def test_scene_chambers_seal_diagonal_corners_at_every_supported_scale():
    for n in (24, 32, 64, 208):
        for scene in ('water-cycle', 'convection'):
            w = World(n); w.scene(scene)
            walls = blocked_mask(w)
            seen = np.zeros(w.length, bool); queue = [0]; seen[0] = True
            for i in queue:
                x, y = i % n, i // n
                assert w.cells[i] not in (ID.WATER, ID.VAPOR, ID.LAVA, ID.NITROGEN), f'{scene} reservoir is sealed at {n}'
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        px, py = x + dx, y + dy; j = py * n + px
                        if px < 0 or py < 0 or px >= n or py >= n or seen[j] or walls[j]:
                            continue
                        seen[j] = True; queue.append(j)
            assert count(w, ID.LAVA) > 0
            if scene == 'convection':
                assert count(w, ID.NITROGEN) > 0; assert count(w, ID.ICE) == 0


def test_test_tube_holders_admit_lava_and_conduct_heat_through_intact_crystal():
    for size in (64, 96):
        world = World(size); world.scene('test-tubes')
        center, bottom = math.floor(size * .2), math.floor(size * .66)
        assert world.cells[(bottom + 1) * size + center] == ID.EMPTY
        crystal = count(world, ID.CRYSTAL)
        half, gap = max(2, math.floor(size * .055)), max(2, math.floor(size * .05))
        for y in range(bottom - half, bottom + gap + 2):
            for x in range(center - half - gap + 1, center + half + gap):
                if not world.cells[y * size + x]:
                    world.set(y * size + x, ID.LAVA, 1100, True)
        for _ in range(350):
            world.step()
        assert count(world, ID.CRYSTAL) == crystal
        assert world.heat[bottom * size + center] > 100
        assert count(world, ID.VAPOR) > 0


def test_bounded_brush_non_overwriting_paint_and_complete_metadata_cleanup():
    world = World(20)
    world.paint(0, 0, ID.SPARK, 3)
    initial = count(world, ID.SPARK)
    world.paint(0, 0, ID.STONE, 3)
    assert count(world, ID.SPARK) == initial
    world.paint(0, 0, ID.EMPTY, 3)
    assert count(world, ID.SPARK) == 0
    assert not world.charge.any()
    assert not world.life.any()
    assert np.all(world.roots == -1)


def test_gravity_accelerates_gradually_scaffold_stays_fixed():
    world = World(20)
    world.set(50, ID.SAND); world.set(310, ID.STONE); world.set(210, ID.VAPOR)
    world.step()
    assert world.cells[50] == ID.SAND
    assert abs(world.vy[50] - .045) < .00001
    assert world.cells[310] == ID.STONE
    assert world.cells[210] == ID.VAPOR
    for _ in range(15):
        world.step()
    assert index_of(world.cells, ID.SAND) > 50
    assert world.cells[310] == ID.STONE


def test_airborne_matter_retains_sideways_momentum_and_cannot_tunnel_through_walls():
    for id in (ID.SAND, ID.WATER, ID.OIL):
        world = World(32)
        world.set(10 * 32 + 10, id); world.vx[330] = 2
        for _ in range(8):
            world.step()
        i = index_of(world.cells, id)
        assert i % 32 > 17, ELEMENTS[id].name
        assert world.vx[i] > .5
        world.clear(); world.set(10 * 32 + 10, id); world.vx[330] = 3
        for y in range(32):
            world.set(y * 32 + 11, ID.STONE)
        for _ in range(30):
            world.step()
        assert index_of(world.cells, id) % 32 < 11


def test_vapor_diffuses_sideways_and_hot_gas_expands_more_strongly_without_racing_upward():
    spreads = []
    for temperature in (40, 400):
        world = World(64); world.paint(32, 32, ID.VAPOR, 7, 1, True)
        world.heat[world.cells != 0] = temperature
        population = count(world, ID.VAPOR)
        for _ in range(90):
            world.step()
        vapor = np.flatnonzero(world.cells == ID.VAPOR)
        variance = float(np.sum((vapor % 64 - 32) ** 2)); height = float(np.sum(vapor // 64))
        assert count(world, ID.VAPOR) == population
        assert variance / population > 20
        assert height / population > 8, 'Gas should diffuse, not instantly collect at the roof'
        spreads.append(variance / population)
    assert spreads[1] > spreads[0]


def test_phase_changes_preserve_momentum_and_replacement_clears_fractional_travel():
    world = World(16); world.set(40, ID.WATER, 120)
    world.vx[40] = 1.5; world.vy[40] = -.5; world.travel_x[40] = .4
    world.transform(40, ID.VAPOR, 120)
    assert world.vx[40] == 1.5; assert world.vy[40] == -.5
    world.set(40, ID.EMPTY)
    assert world.vx[40] == 0; assert world.travel_x[40] == 0


def test_sand_sinks_through_oil_without_losing_particles():
    world = World(16)
    for i in range(world.length):
        world.set(i, ID.OIL)
    world.set(24, ID.SAND)
    for _ in range(32):
        world.step()
    assert count(world, ID.SAND) == 1
    assert count(world, ID.OIL) == 255
    assert index_of(world.cells, ID.SAND) >= 224


def test_condensation_is_probabilistic_with_a_shorter_half_life_at_lower_temperatures():
    assert condensation_chance(20) > condensation_chance(60)
    assert condensation_chance(60) > condensation_chance(90)
    assert condensation_chance(110) == 0
    world = World(24)
    for i in range(200):
        world.set(i, ID.VAPOR, 20)
    for _ in range(20):
        world.step()
    assert count(world, ID.WATER) > 10
    assert count(world, ID.VAPOR) > 10
    assert count(world, ID.VAPOR) + count(world, ID.WATER) == 200


def test_water_boils_freezes_and_ice_melts_according_to_temperature():
    world = World(20)
    world.set(100, ID.WATER, 130); world.set(200, ID.WATER, -10); world.set(300, ID.ICE, 10)
    world.step()
    assert count(world, ID.VAPOR) == 1
    assert count(world, ID.ICE) == 1
    assert count(world, ID.WATER) == 1


def test_fuel_ignites_gradually_sand_fuses_and_sparks_expire():
    world = World(20)
    world.set(10, ID.OIL, 250); world.set(100, ID.SAND, 500); world.set(300, ID.SPARK)
    world.step()
    assert count(world, ID.FIRE) == 0
    assert count(world, ID.CRYSTAL) == 1
    for _ in range(40):
        world.step()
    assert count(world, ID.SPARK) == 0
    for _ in range(240):
        world.step()
    assert count(world, ID.FIRE) > 0


def test_thermal_and_electrical_conductivity_are_independent():
    world = World(20)
    world.set(200, ID.STONE, 100); world.set(201, ID.STONE, 20)
    world.charge[200] = 1
    world.step()
    assert world.heat[201] > 20
    assert world.charge[201] == 0
    assert ELEMENTS[ID.ICE].thermal > ELEMENTS[ID.ICE].electrical * 10


def test_visible_charge_front_reverses_and_cannot_cross_an_insulating_gap():
    world = World(32)
    start = 16 * 32 + 5
    for j in range(20):
        world.set(start + j, ID.CRYSTAL)
    world.set(start + 21, ID.CRYSTAL)
    world.charge[start] = 1
    far_peak = return_peak = 0; negative = False
    for tick in range(240):
        world.electricity()
        far_peak = max(far_peak, abs(world.charge[start + 18]))
        if tick > 20:
            return_peak = max(return_peak, abs(world.charge[start]))
        negative = negative or bool(np.any(world.charge < -.02))
        assert world.charge[start + 21] == 0
    assert far_peak > .08, f'front peak {far_peak}'
    assert return_peak > .05, f'reflected peak {return_peak}'
    assert negative


def test_spark_contact_injects_one_bounded_pulse_and_heats_fuel_without_instant_ignition():
    world = World(20)
    world.set(180, ID.SPARK); world.set(181, ID.CRYSTAL)
    world.contact(180, 181)
    first_pulse = world.charge[181]
    world.contact(180, 181)
    assert world.charge[181] == first_pulse
    assert first_pulse > 0
    world.clear()
    for y in range(10, 20):
        for x in range(20):
            world.set(y * 20 + x, ID.OIL)
    world.set(190, ID.SPARK); world.step()
    assert count(world, ID.FIRE) == 0
    assert np.any(world.burn > 0)


def test_lava_quenches_in_water_and_solidifies_on_cooling_sand_mixes_into_mud():
    world = World(20)
    world.set(200, ID.LAVA); world.set(201, ID.WATER); world.contact(200, 201)
    assert world.cells[200] == ID.STONE
    assert world.cells[201] == ID.VAPOR
    world.set(300, ID.LAVA, 400); world.set(350, ID.MUD, 150); world.step()
    assert count(world, ID.LAVA) == 0; assert count(world, ID.MUD) == 0
    world.set(100, ID.SAND); world.set(101, ID.WATER)
    world.fixed_random = 0; world.contact(100, 101)
    assert world.cells[100] == ID.MUD; assert world.cells[101] == ID.EMPTY


def test_fire_emits_rising_wind_currents_push_vapor_and_decay_behind_solid_barriers():
    world = World(24)
    world.set(300, ID.FIRE); world.step()
    assert np.any(world.wind_y < -.03)
    assert np.any(world.pressure > 0)
    assert count(world, ID.WIND) == 0
    world.clear(); world.set(300, ID.VAPOR); world.gust(300, 12, 0)
    world.fixed_random = .5; world.step()
    assert world.vx[300] > .02, 'Airflow accelerates vapor rather than teleporting it'
    world.clear()
    for y in range(24):
        world.set(y * 24 + 12, ID.STONE)
    world.gust(12 * 24 + 11, 3, 0)
    for _ in range(20):
        world.airflow()
    for y in range(24):
        assert world.wind_x[y * 24 + 13] == 0


def test_spark_brush_emits_radially_rather_than_rising_as_a_gas():
    world = World(32)
    world.paint(16, 16, ID.SPARK, 7)
    assert world.vx[16 * 32 + 13] < 0; assert world.vx[16 * 32 + 19] > 0
    assert world.vy[13 * 32 + 16] < 0; assert world.vy[19 * 32 + 16] > 0
    for _ in range(5):
        world.step()
    sparks = np.flatnonzero(world.cells == ID.SPARK) // 32
    assert np.any(sparks > 20)
    assert np.any(sparks < 12)


def test_wind_brush_adds_a_directional_jet_and_balanced_pressure_without_replacing_particles():
    world = World(32)
    world.set(16 * 32 + 16, ID.WATER)
    world.paint(16, 16, ID.WIND, 3)
    assert np.count_nonzero(world.cells) == 1
    assert world.cells[16 * 32 + 16] == ID.WATER
    assert np.any(world.pressure > 0)
    assert np.any(world.pressure < 0)
    assert abs(np.sum(world.pressure)) < .00001
    assert world.wind_x[16 * 32 + 16] > .2
    assert not world.wind_y.any()
    for _ in range(8):
        world.airflow()
    assert np.any(world.pressure < -.001), 'Pressure pulse must also produce rarefaction'


def test_wind_remains_after_release_and_higher_settings_reduce_damping():
    weak, strong = World(24), World(24)
    weak.wind_strength = 10; strong.wind_strength = 100
    for y in range(10, 14):
        for x in range(10, 14):
            weak.pressurize(y * 24 + x, 4); strong.pressurize(y * 24 + x, 4)

    def energy(world):
        return float(np.sum(world.pressure ** 2 + world.wind_x ** 2 + world.wind_y ** 2))
    initial_weak, initial_strong = energy(weak), energy(strong)
    for _ in range(40):
        weak.airflow(); strong.airflow()
    assert energy(strong) / initial_strong > energy(weak) / initial_weak
    assert energy(strong) < initial_strong
    for _ in range(600):
        weak.airflow(); strong.airflow()
    assert energy(strong) > .1, 'Circulation must not vanish within seconds'
    assert energy(strong) > energy(weak)


def test_wind_strength_scales_momentum_unforced_pressure_waves_remain_approximately_radial():
    weak, strong = World(64), World(64)
    weak.paint(32, 32, ID.WIND, 3, .2); strong.paint(32, 32, ID.WIND, 3, 2)
    center = 32 * 64 + 32
    assert abs(strong.wind_x[center] / weak.wind_x[center] - 10) < .001
    radial = World(64)
    for dy in range(-6, 7):
        for dx in range(-6, 7):
            if dx * dx + dy * dy <= 36:
                radial.pressurize((32 + dy) * 64 + 32 + dx, .6 * math.exp(-(dx * dx + dy * dy) / (36 * .3)))
    for _ in range(8):
        radial.airflow()
    # (5,0) and (3,4) are the same radius but different orientations.
    axial, diagonal = radial.pressure[32 * 64 + 37], radial.pressure[36 * 64 + 35]
    assert axial > .01 and diagonal > .01
    assert abs(axial - diagonal) / max(axial, diagonal) < .12


def test_all_material_palette_colors_have_strong_contrast_against_both_field_backgrounds():
    def luminance(hex_color):
        channels = [int(hex_color[k:k + 2], 16) / 255 for k in (1, 3, 5)]
        linear = [value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4 for value in channels]
        return linear[0] * .2126 + linear[1] * .7152 + linear[2] * .0722
    # Stone's glyph is a solid block, a graphical object rather than text, so it
    # needs WCAG's 3:1 non-text contrast; every other glyph needs 4.5:1.
    colors = [(element.name, element.light, element.dark) for element in ELEMENTS]
    colors += [('Antigrav', ANTIGRAV_COLOR['light'], ANTIGRAV_COLOR['dark']), ('Feesh', FEESH_COLOR['light'], FEESH_COLOR['dark'])]
    for name, light, dark in colors:
        minimum = 3 if name == 'Stone' else 4.5
        assert (luminance('#f5f4f0') + .05) / (luminance(light) + .05) >= minimum, f'{name} light'
        assert (luminance(dark) + .05) / (luminance('#080909') + .05) >= minimum, f'{name} dark'


def test_pressure_deflects_around_a_finite_obstacle_and_develops_a_rotating_wake():
    world = World(32)
    for y in range(10, 22):
        world.set(y * 32 + 16, ID.STONE)
    for y in range(8, 24):
        for x in range(8, 12):
            world.pressurize(y * 32 + x, 4)
    transverse = curl = behind = 0
    for _ in range(80):
        world.airflow()
        transverse = max(transverse, abs(world.wind_y[10 * 32 + 15]))
        curl = max(curl, float(np.max(np.abs(world.curl))))
        behind = max(behind, abs(world.pressure[9 * 32 + 18]))
    assert transverse > .01; assert curl > .01; assert behind > .01


def test_conductivity_changes_wave_travel_time_and_does_not_instantly_saturate_a_conductor():
    def arrival(id):
        world = World(32); start = 16 * 32 + 5
        for j in range(20):
            world.set(start + j, id)
        world.charge[start] = 1
        for t in range(400):
            world.electricity()
            if abs(world.charge[start + 18]) > .08:
                return t
        return math.inf
    fast, slow = arrival(ID.CRYSTAL), arrival(ID.MUD)
    assert 40 < fast < 120; assert fast * 2 < slow < 350


def test_thermal_conductivity_controls_fuel_ignition_time():
    def ignition(id):
        world = World(20)
        world.set(210, id, 250)
        for t in range(600):
            world.step()
            if count(world, ID.FIRE):
                return t
        return math.inf
    seed_time, oil_time = ignition(ID.SEED), ignition(ID.OIL)
    assert seed_time > 30 and seed_time < oil_time < 600


def test_seeds_require_sand_or_mud_plus_water_before_rooting():
    world = World(20)
    world.set(210, ID.SEED); world.set(230, ID.STONE); world.set(209, ID.WATER)
    assert world.grow(210, 10, 10) is False
    assert world.cells[209] == ID.WATER
    world.set(230, ID.SAND); world.set(209, ID.EMPTY)
    assert world.grow(210, 10, 10) is False
    world.set(209, ID.WATER)
    assert world.grow(210, 10, 10) is True
    assert world.roots[210] == 210; assert world.cells[209] == ID.EMPTY


def test_watered_roots_produce_upward_branches_and_stop_extending_when_the_supply_is_exhausted():
    world = World(32)
    for y in range(26, 32):
        for x in range(32):
            world.set(y * 32 + x, ID.SAND)
    root = 25 * 32 + 16
    world.set(root, ID.SEED)
    world.set(root - 1, ID.WATER); world.set(root + 1, ID.WATER)
    for _ in range(1200):
        world.step()
    assert count(world, ID.SEED) > 4
    assert np.any(np.flatnonzero(world.cells == ID.SEED) // 32 < 23)
    assert np.any(world.branch != 0)
    before = count(world, ID.SEED)
    world.moisture.fill(0)
    for i in np.flatnonzero((world.cells == ID.WATER) | (world.cells == ID.MUD)):
        world.set(i, ID.SAND)
    for _ in range(100):
        world.step()
    assert count(world, ID.SEED) == before


def test_glyph_weight_distinguishes_vapor_temperature_stem_maturity_and_charge():
    world = World(20)
    world.set(0, ID.VAPOR, 120); assert glyph_variant(world.state, 0) == 0
    world.heat[0] = 40; assert glyph_variant(world.state, 0) == 2
    world.set(1, ID.SEED); world.roots[1] = 1; world.life[1] = 2
    assert glyph_variant(world.state, 1) == 2
    world.set(2, ID.CRYSTAL); world.charge[2] = -.4
    assert glyph_variant(world.state, 2) == 3


def test_deterministic_scenes_and_finite_bounded_fields_under_dense_mixed_load():
    first, second = World(32), World(32)
    first.scene(); second.scene()
    for _ in range(100):
        first.step(); second.step()
    assert np.array_equal(first.cells, second.cells)
    for i in range(first.length):
        first.set(i, i % len(ELEMENTS))
    for _ in range(300):
        first.step()
    assert np.all(first.cells < len(ELEMENTS))
    assert np.all(np.isfinite(first.heat))
    assert np.all(np.isfinite(first.charge) & (np.abs(first.charge) <= 3))
    assert np.all(np.isfinite(first.wind_x) & (np.abs(first.wind_x) <= MAX_AIR_SPEED))
    assert len({element.symbol for element in ELEMENTS}) == len(ELEMENTS)


def test_hot_lava_melts_metal_that_conduction_alone_would_keep_solid_stone_and_locked_metal_are_distinct():
    n = 32; world = World(n, 5)
    for x in range(8, 24):
        world.set(28 * n + x, ID.METAL)
    world.paint(16, 24, ID.LAVA, 7)
    for _ in range(600):
        world.step()
    assert count(world, ID.METAL) < 16
    locked = World(8, 5)
    locked.set(0, ID.METAL, 20, True); locked.set(1, ID.LAVA, 1100, True)
    for _ in range(200):
        locked.step()
    assert locked.cells[0] == ID.METAL
    assert element_symbol(ID.METAL, True) != element_symbol(ID.STONE)
    assert ELEMENTS[ID.METAL].thermal > ELEMENTS[ID.STONE].thermal and ELEMENTS[ID.METAL].electrical > .5


def test_grav_lifts_resting_sand_slightly_above_ordinary_gravity_antigrav_repels():
    n = 32
    for antigrav in (False, True):
        world = World(n, 5)
        for x in range(n):
            for y in range(29, n):
                world.set(y * n + x, ID.SAND)
        world.set(20 * n + 16, ID.GRAV, 20, False, antigrav)
        for _ in range(300):
            world.step()
        lifted = count_in(world, ID.SAND, 0, 29 * n)
        assert abs(world.gravity_y[26 * n + 16] - (GRAV_STRENGTH if antigrav else -GRAV_STRENGTH)) < 1e-6
        if antigrav:
            assert lifted == 0
        else:
            assert lifted > 0
    assert .045 < GRAV_STRENGTH < .09
    world = World(8, 5)
    world.set(10, ID.GRAV); world.step()
    world.set(10, ID.EMPTY); world.step()
    assert not world.gravity_x.any() and not world.gravity_y.any()


def count_in(world, id, start, end):
    return int(np.count_nonzero(world.cells[start:end] == id))


def test_bacteria_follow_life_rules_whether_or_not_locked_eat_plants_and_locks_isolate_them():
    n = 16

    def generation(world):
        for _ in range(12):
            world.step()

    def cells(world):
        return tuple(np.flatnonzero(world.cells == ID.BACTERIUM))
    for locked in (False, True):
        world = World(n, 5)
        for x in (5, 6, 7):
            world.set(5 * n + x, ID.BACTERIUM, 20, locked)
        start = cells(world)
        generation(world); middle = cells(world)
        generation(world)
        assert middle != start
        assert cells(world) == start
        assert np.all(world.phase_locked[world.cells == ID.BACTERIUM] == int(locked))
    eating = World(n, 5)
    for x in (5, 6, 7):
        eating.set(5 * n + x, ID.BACTERIUM)
    eating.set(5 * n + 8, ID.SEED)
    for x in (7, 8, 9):
        eating.set(6 * n + x, ID.STONE)
    generation(eating)
    assert eating.cells[5 * n + 8] == ID.BACTERIUM
    guarded = World(n, 5)
    for x in (5, 6, 7):
        guarded.set(5 * n + x, ID.BACTERIUM, 20, True)
    guarded.set(5 * n + 8, ID.SEED)
    for x in (7, 8, 9):
        guarded.set(6 * n + x, ID.STONE)
    generation(guarded)
    assert guarded.cells[5 * n + 8] == ID.SEED
    heat = World(n, 5)
    for locked in (False, True):
        y = 10 if locked else 4
        # A stable block isolates thermal immunity from oscillator births being
        # obstructed by lava whose movement depends on buoyancy.
        for x in (5, 6):
            for row in (y - 1, y):
                heat.set(row * n + x, ID.BACTERIUM, 20, locked)
        for x in (5, 6, 7):
            heat.set((y + 1) * n + x, ID.LAVA, 1100, True)
    generation(heat); generation(heat)
    assert np.all(heat.phase_locked[heat.cells == ID.BACTERIUM] != 0)
    assert count(heat, ID.BACTERIUM) > 0


def test_air_carries_heat_exchanges_with_reservoirs_and_resets_independently_of_particles():
    w = World(24); i = 12 * 24 + 12
    w.set(i, ID.ICE, -25, True)
    for _ in range(80):
        w.step()
    assert w.air_heat[i - 1] < 15, 'ice chills adjacent air'
    assert w.heat[i] == -25
    w.set(i, ID.EMPTY)
    assert w.air_heat[i - 1] < 15, 'erasing does not erase the thermal field'
    w.clear(); w.set(i, ID.LAVA, 1100, True); w.air_thermal()
    assert w.air_heat[i] > 20
    assert w.heat[i] == 1100
    w.clear(); w.zero_gravity = True
    w.air_heat[i] = 200; w.wind_x.fill(1); w.airflow()
    assert w.air_heat[i + 1] > 20, 'flow advects heat'
    w.clear(); w.air_heat.fill(0); w.airflow()
    assert not w.wind_y.any(), 'zero-g disables thermal lift'
    w.zero_gravity = False; w.airflow()
    assert w.wind_y[i] > 0, 'cold air sinks'
    w.clear(); w.air_heat.fill(100); w.airflow()
    assert w.wind_y[i] < 0, 'hot air rises'
    w.clear(); assert np.all(w.air_heat == 20)


def test_warm_liquid_rises_through_cold_liquid_with_direction_aware_density_displacement():
    w = World(16); i = 8 * 16 + 8
    w.tick = 1
    w.set(i, ID.WATER, 90, True); w.set(i - 16, ID.WATER, 10, True)
    assert w.density(i) < w.density(i - 16)
    assert w.move(i, 8, 7, True)
    assert w.heat[i - 16] == 90
    w.tick += 1
    assert w.move(i - 16, 8, 8, True) is False, 'warm water cannot sink through cold water'
    for j in (i - 1, i + 1, i - 16, i + 16):
        w.set(j, ID.WATER, 10, True)
    for x in range(7, 10):
        w.set(10 * 16 + x, ID.STONE); w.set(9 * 16 + x, ID.WATER, 10, True)
    w.set(i, ID.WATER, 90, True); w.transport_particle(i, 8, 8)
    assert w.vy[index_of(w.heat, 90)] < 0, 'immersed warm water accelerates upward'


def test_convection_scene_circulates_locked_vapor_without_consuming_reservoirs():
    w = World(32); w.scene('convection')
    tracked = (ID.VAPOR, ID.LAVA, ID.NITROGEN)
    initial = [count(w, id) for id in tracked]
    rising = falling = 0
    for t in range(1600):
        w.step()
        if t > 800:
            vapor = np.flatnonzero(w.cells == ID.VAPOR)
            left = vapor % 32 < 16
            rising += float(np.sum(w.vy[vapor[left]])); falling += float(np.sum(w.vy[vapor[~left]]))
    assert rising < 0 and falling > 0, 'vapor traces a rising hot limb and descending cool limb'
    assert [count(w, id) for id in tracked] == initial
    for id, temperature in ((ID.VAPOR, 20), (ID.LAVA, 1100), (ID.NITROGEN, -200)):
        present = w.cells == id
        assert np.all(w.phase_locked[present] != 0)
        assert np.all(w.heat[present] == temperature)
    assert np.all(np.isfinite(w.air_heat))


def test_ignited_gunpowder_chain_detonates_into_a_bounded_blast_of_pressure_wind_fire_and_debris():
    n = 48; world = World(n, 5)
    for x in range(n):
        for y in range(44, n):
            world.set(y * n + x, ID.SAND)
    for x in range(18, 30):
        for y in range(40, 44):
            world.set(y * n + x, ID.GUNPOWDER, 20, True)
    assert not world.phase_locked.any()
    for _ in range(30):
        world.step()
    assert count(world, ID.GUNPOWDER) == 48
    world.set(39 * n + 24, ID.SPARK)
    world.vx[39 * n + 24] = 0; world.vy[39 * n + 24] = 1
    peak_pressure = peak_wind = 0; saw_fire = False
    for _ in range(20):
        world.step()
        peak_pressure = max(peak_pressure, float(np.max(world.pressure)))
        peak_wind = max(peak_wind, float(np.max(np.abs(world.wind_x))))
        saw_fire = saw_fire or count(world, ID.FIRE) > 10
    assert count(world, ID.GUNPOWDER) == 0
    assert saw_fire and 40 < peak_pressure <= MAX_PRESSURE and 4 < peak_wind <= MAX_AIR_SPEED
    assert count_in(world, ID.SAND, 0, 40 * n) > 0
    heated = World(16, 5)
    heated.set(8 * 16 + 8, ID.GUNPOWDER, 250)
    heated.step()
    assert heated.cells[8 * 16 + 8] == ID.FIRE


def test_zero_g_removes_weight_settling_buoyancy_and_convection_but_keeps_grav_sources():
    n = 32

    def draft(zero_gravity):
        world = World(n, 5)
        world.zero_gravity = zero_gravity
        world.set(10 * n + 8, ID.SAND)
        world.set(16 * n + 24, ID.FIRE, 650, True)
        # Sum vertical airflow in the column above the fire once the flow develops.
        lift = 0
        for t in range(120):
            world.step()
            if t >= 60:
                lift += sum(world.wind_y[y * n + 24] for y in range(11, 16))
        return world, lift
    weightless, weightless_lift = draft(True)
    normal, normal_lift = draft(False)
    assert weightless.cells[10 * n + 8] == ID.SAND, 'sand floats in place'
    assert normal.cells[10 * n + 8] != ID.SAND, 'sand falls with gravity'
    assert normal_lift < -5 and weightless_lift > normal_lift / 4, f'fire draft {normal_lift:.2f} vs {weightless_lift:.2f}'

    # Gas agitation is random, so compare net lift over several seeds.
    def lift(zero_gravity):
        total = 0
        for seed in (9, 10, 11):
            gas = World(n, seed)
            gas.zero_gravity = zero_gravity
            for x in range(12, 20):
                gas.set(16 * n + x, ID.VAPOR, 90)
            for _ in range(60):
                gas.step()
                total += float(np.sum(gas.vy[gas.cells == ID.VAPOR]))
        return total
    buoyant, drifting = lift(False), lift(True)
    assert buoyant < -40 and drifting > buoyant / 4, f'vapor lift {buoyant:.2f} vs {drifting:.2f}'
    pulled = World(n, 5)
    pulled.zero_gravity = True
    pulled.set(16 * n + 16, ID.GRAV); pulled.set(16 * n + 10, ID.SAND)
    for _ in range(80):
        pulled.step()
    assert pulled.cells[16 * n + 10] == ID.EMPTY, 'grav still attracts'
    assert NORMAL_GRAVITY < GRAV_STRENGTH


def test_boids_flock_in_air_feesh_fall_inert_until_water_then_school_heat_kills_both():
    n = 64

    # Mean cosine between each boid's heading and its neighbors' within 6 cells.
    def alignment(world):
        boids = np.flatnonzero(world.cells == ID.BOID)
        x, y = boids % n, boids // n
        vx, vy = world.vx[boids], world.vy[boids]
        near = np.hypot(x[:, None] - x[None, :], y[:, None] - y[None, :]) <= 6
        np.fill_diagonal(near, False)
        speed = np.hypot(vx, vy)
        cosine = (vx[:, None] * vx[None, :] + vy[:, None] * vy[None, :]) / (speed[:, None] * speed[None, :])
        return float(np.sum(cosine[near]) / np.count_nonzero(near))
    birds = World(n, 5)
    for k in range(40):
        birds.set(((k * 37) % 40 + 10) * n + (k * 23) % 44 + 10, ID.BOID)
    initial = alignment(birds)
    aligned = 0
    for t in range(1, 601):
        birds.step()
        if t > 300 and t % 30 == 0:
            aligned += alignment(birds) / 10
    assert count(birds, ID.BOID) == 40
    assert aligned > .55 and aligned > initial + .3, f'local alignment {initial:.2f} -> {aligned:.2f}'

    pond = World(n, 4)
    for x in range(8, 56):
        pond.set(60 * n + x, ID.STONE)
        for y in range(44, 60):
            pond.set(y * n + x, ID.WATER)
    for y in range(30, 61):
        pond.set(y * n + 7, ID.STONE); pond.set(y * n + 56, ID.STONE)
    for k in range(24):
        pond.set((20 + k % 4) * n + 20 + k, ID.BOID, 20, False, True)
    water = count(pond, ID.WATER)
    for _ in range(300):
        pond.step()
    fish = np.flatnonzero(pond.cells == ID.BOID)
    assert len(fish) == 24
    assert all(pond.polarity[i] < 0 and pond.submerged(i, i % n, i // n) for i in fish), 'every feesh is in the pond'
    assert count(pond, ID.WATER) == water, 'swimming exchanges places with water'
    assert np.any(np.abs(pond.vx[fish]) + np.abs(pond.vy[fish]) > .2), 'feesh swim'

    beach = World(16, 4)
    for x in range(16):
        beach.set(15 * 16 + x, ID.SAND)
    beach.set(5 * 16 + 8, ID.BOID, 20, False, True)
    for _ in range(120):
        beach.step()
    stranded = index_of(beach.cells, ID.BOID)
    for _ in range(60):
        beach.step()
    assert stranded // 16 == 14, 'a feesh out of water falls to the ground'
    assert index_of(beach.cells, ID.BOID) == stranded, 'and stays inert there'

    hot = World(16, 4)
    hot.set(8 * 16 + 8, ID.BOID, 120)
    hot.step()
    assert count(hot, ID.BOID) == 0


def test_tick_speed_scales_the_tick_rate_holds_it_at_lower_frame_rates_and_drops_stalls():
    def rate(speed, frame_ms, seconds=2):
        clock = Clock(); ticks = 0
        for _ in range(round(seconds * 1000 / frame_ms)):
            ticks += ticks_due(clock, frame_ms, speed)
        return ticks / seconds
    for speed in (.5, .75, 1, 1.5, 2, 3, 4, 6, 8):
        assert abs(rate(speed, 1000 / 60) - TICK_RATE * speed) <= 1, f'{speed}x at 60 fps'
        assert abs(rate(speed, 1000 / 30) - TICK_RATE * speed) <= 1, f'{speed}x at 30 fps'
    clock = Clock()
    assert ticks_due(clock, 1000, 8) <= 16, 'a one-second stall is bounded'
    assert clock.accumulator <= 1000 / TICK_RATE / 8, 'and leaves no backlog'


def test_blob_contours_close_around_regions_join_diagonals_and_reverse_around_holes():
    n = 8; keys = (n + 2) ** 2 * 2
    next_key = np.full(keys, -1, np.int64); starts = np.zeros(keys, np.int64)
    points = np.zeros(keys * 2); ends = np.zeros(keys, np.int64)

    def trace(cells):
        groups = np.zeros(n * n, np.uint8)
        for x, y in cells:
            groups[y * n + x] = 1
        xs, ys = [x for x, _ in cells], [y for _, y in cells]
        contours = trace_contours(groups, n, 0, min(xs), min(ys), max(xs), max(ys), next_key, starts, points, ends)
        assert np.all(next_key == -1), 'buffers are restored'
        areas = []
        for k in range(contours):
            first = ends[k - 1] if k else 0
            outline = points[first * 2:ends[k] * 2].reshape(-1, 2)
            following = np.roll(outline, -1, axis=0)
            areas.append(float(np.sum(outline[:, 0] * following[:, 1] - following[:, 0] * outline[:, 1])) / 2)
        return areas
    assert trace([(3, 3)]) == [.5]
    assert trace([(3, 3), (4, 3), (3, 4), (4, 4)]) == [3.5]
    assert trace([(3, 3), (4, 4)]) == [1.5], 'diagonal neighbors form one blob'
    assert len(trace([(1, 1), (2, 2), (3, 3), (4, 4), (5, 5)])) == 1, 'a diagonal staircase is one blob'
    assert trace([(0, 0), (1, 0), (0, 1)]) == [2.5]
    ring = [(x, y) for y in range(2, 6) for x in range(2, 6) if x in (2, 5) or y in (2, 5)]
    assert trace(ring) == [15.5, -3.5]
