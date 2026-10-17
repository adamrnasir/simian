# SIMIAN

A collection of small experiments inspired by [Powder Game 2](https://dan-ball.jp/en/javagame/dust2/). Paint materials, wind, and gravity sources onto a grid and watch weight, viscosity, heat, airflow, electric charge, and life interact.

The original sims (`prototypes/`) were built for fun over a few hours in August 2024 in order to check out the capabilities of OpenAI models. I revisited this repo in September 2026 to adapt a version of the sim for the web using GPT-6 Astra (`web/`) which can be found on my website (https://adam-nasir.com/experiments/simian/) and again in October 2026 to back-adapt the web version into python using Opus 5.5 (`python/`).

## Electron app

Requires Node 22.12 or newer (Electron's installer needs it).

```sh
npm install
npm start
```

`main.cjs` serves `web/` from a custom `app://` scheme, since ES modules don't load from `file://` pages. `web/index.html`, `web/shell.css` (the subset of the site's stylesheet that Simian uses), and `main.cjs` are specific to this app. Every other file in `web/` is copied verbatim from the website repository, as is `tests/simian.test.mjs`. To pull in changes from the site:

```sh
npm run sync-web            # assumes ../adamrnasir.github.io
scripts/sync-web.sh <path>  # or name the site checkout
```

Run the engine tests with `npm test` (works on Node 18 and later).

## Python version

```sh
cd python
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[test]'
simian                     # or: python -m simian
```

`app.py` uses package-relative imports, so run the `simian` command or `python -m simian` rather than the file itself.

The first launch compiles the engine and takes about 30 seconds; numba caches the result, so later launches start in a couple of seconds.

| Module                                   | Ports                                                                  |
| ---------------------------------------- | ---------------------------------------------------------------------- |
| `simian/engine.py`                       | `web/engine.mjs`: elements, rules, scenes, and the `World` class       |
| `simian/gravity.py`                      | `web/gravity.mjs`: softened radial gravity with Barnes–Hut aggregation |
| `simian/raster.py`, `simian/renderer.py` | `web/renderer.mjs`: glyph atlas, tiles, blob contours, and overlays    |
| `simian/app.py`                          | `web/app.mjs`, `web/index.html`, and `web/simian.css`                  |
| `simian/clock.py`, `simian/aim.py`       | `web/clock.mjs`, `web/aim.mjs`                                         |

Kernels follow the JavaScript methods one for one, in the same evaluation order, with the same xorshift random generator. They run without numba's reference counting, which made ticks about 40 times slower when kernels pass the world's state tuple to helpers that branch. As a consequence kernels cannot allocate arrays; only `gravity()` does, and it runs with reference counting before each tick.

Run the tests with `pytest` from `python/`. `tests/test_simian.py` ports `tests/simian.test.mjs` test for test. `tests/test_parity.py` runs the web engine under Node and requires identical grids every tick for 300 ticks of each scene and of a dense grid of every element. The web engine stores fields in `Float32Array` and this port in float64, so the parity test widens the JavaScript arrays to `Float64Array`; without that change, the two versions match exactly for several hundred ticks and then diverge through rounding. The parity test is skipped when `node` isn't on the path.

Known differences from the web version: the Qt window has a desktop layout only (no stacked mobile layout), and reduced motion is read from macOS's accessibility setting at launch rather than followed live.
