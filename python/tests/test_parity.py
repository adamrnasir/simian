"""Cross-checks the port against the web engine in web/engine.mjs.

The JavaScript engine stores fields in Float32Array; this port stores float64.
With the JavaScript storage widened to Float64Array, the two engines follow the
same rules in the same order and produce identical grids tick for tick, so any
rule change synced from the site without a matching port change fails here.
Temperatures may differ in the last binary digit (about 1e-14 relative after
300 ticks of the mixed grid), so they are compared with a tolerance.
"""
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from simian.engine import ELEMENTS, World

WEB = Path(__file__).resolve().parents[2] / 'web'
NODE = shutil.which('node')
TICKS = 300

DRIVER = """
import { World, ELEMENTS } from './engine.mjs';
const [setup, size, ticks] = [process.argv[2], Number(process.argv[3]), Number(process.argv[4])];
const w = new World(size);
if (setup === 'mixed') for (let i = 0; i < w.length; i++) w.set(i, i % ELEMENTS.length, undefined, i % 3 === 0, i % 2 === 0);
else w.scene(setup);
const cells = [];
for (let t = 0; t < ticks; t++) { w.step(); cells.push(Buffer.from(w.cells).toString('hex')); }
console.log(JSON.stringify({ cells, heat: Array.from(w.heat), seed: w.seed >>> 0 }));
"""


@pytest.fixture(scope='module')
def web_engine(tmp_path_factory):
    if not NODE or not (WEB / 'engine.mjs').exists():
        pytest.skip('requires node and web/engine.mjs')
    directory = tmp_path_factory.mktemp('web')
    engine = (WEB / 'engine.mjs').read_text().replace('Float32Array', 'Float64Array')
    (directory / 'engine.mjs').write_text(engine)
    shutil.copy(WEB / 'gravity.mjs', directory / 'gravity.mjs')
    (directory / 'driver.mjs').write_text(DRIVER)
    return directory / 'driver.mjs'


@pytest.mark.parametrize('setup, size', [('estuary', 64), ('water-cycle', 48), ('convection', 48), ('test-tubes', 48), ('mixed', 32)])
def test_matches_the_web_engine_tick_for_tick(web_engine, setup, size):
    result = subprocess.run([NODE, str(web_engine), setup, str(size), str(TICKS)], capture_output=True, text=True, check=True)
    expected = json.loads(result.stdout)
    world = World(size)
    if setup == 'mixed':
        for i in range(world.length):
            world.set(i, i % len(ELEMENTS), None, i % 3 == 0, i % 2 == 0)
    else:
        world.scene(setup)
    for tick, cells in enumerate(expected['cells'], 1):
        world.step()
        assert world.cells.tobytes().hex() == cells, f'grids diverge at tick {tick}'
    np.testing.assert_allclose(world.heat, expected['heat'], rtol=1e-9, atol=1e-9)
    assert world.seed == expected['seed']
