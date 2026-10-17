import { ANTIGRAV_COLOR, ELEMENTS, FEESH_COLOR, ID, PHASE_LOCKABLE, elementSymbol, World } from './engine.mjs';
import { smoothAim } from './aim.mjs';
import { ticksDue } from './clock.mjs';
import { Renderer, fieldPixels, pixelRatio } from './renderer.mjs';

const canvas = document.querySelector('#world');
const status = document.querySelector('#state');
// At 1× density the grid gives legible ~11 CSS px cells, so larger fields hold
// more cells. Ticks cost about 0.2 µs per cell under dense load: a 208-cell
// side stays under 9 ms, within a 60 Hz budget with room for drawing. A 1440p
// field is about 104 cells at 1×, which sets the 2× density maximum.
// 0.5× on a phone-sized field reaches the 24-cell floor, the smallest grid on
// which every scene fits.
const CELL_TARGET = 11, MIN_SIDE = 24, MAX_SIDE = 208, MAX_DENSITY = 2;
// Cells are whole device pixels: use the size nearest the density target and
// as many cells as fit. The renderer centers any sub-cell remainder. Halves
// round toward finer cells so adjacent steps stay distinct on 1× displays.
function sideFor(density) {
  const pixels = fieldPixels(canvas) || Math.round(700 * pixelRatio());
  const cell = Math.max(3, Math.ceil(CELL_TARGET * pixelRatio() / density - .5));
  return Math.max(MIN_SIDE, Math.min(MAX_SIDE, Math.floor(pixels / cell)));
}
let world = new World(sideFor(1));
const reduced = matchMedia('(prefers-reduced-motion: reduce)');
const cursor = { x: world.size / 2, y: Math.floor(world.size * .36), visible: false };
let selected = 1, diameter = 5, erasing = false, drawing = false, shift = false;
let paused = reduced.matches, inView = true, dirty = true;
let frame = 0, lastTime = 0, lastReadout = 0;
const clock = { accumulator: 0 };
let pointer = null;
let showWind = false;
let gravStrength = 1;
let showTemperature = false;
let showWindArrows = false, windStrength = 10;
let showGravField = false, showGravArrows = false, zeroGravity = false;
let phaseLock = false, antigrav = false, feesh = false;
// Tick speed steps are roughly logarithmic, so 1× is not crowded at one end.
const SPEEDS = [.5, .75, 1, 1.5, 2, 3, 4, 6, 8];
let speed = 1;
const windDirection = { x: 1, y: 0 };
let statsStart = 0, renderedFrames = 0, simulationSteps = 0, simulationTime = 0, drawTime = 0;
let lastInspection = 0;
let renderer;

try { renderer = new Renderer(canvas, world); }
catch (error) {
  status.textContent = error.message;
  document.querySelectorAll('.instrument-panel button, .instrument-panel input, .instrument-panel select').forEach(control => { control.disabled = true; });
}

if (renderer) {
  const coordinate = () => { document.querySelector('.field-coordinate').textContent = `${world.size} × ${world.size}`; };
  coordinate();
  const palette = document.querySelector('.element-grid');
  ELEMENTS.slice(1).forEach((element, index) => {
    const button = document.createElement('button');
    button.type = 'button'; button.className = 'element-choice';
    button.style.setProperty('--element-light', element.light);
    button.style.setProperty('--element-dark', element.dark);
    button.setAttribute('aria-label', index < 9 ? `${element.name} (${index + 1})` : element.name);
    button.title = `${element.name} · ${element.hint}`;
    const symbol = document.createElement('span'); symbol.className = 'element-symbol'; symbol.textContent = element.symbol; symbol.setAttribute('aria-hidden', 'true');
    const name = document.createElement('span'); name.className = 'element-name'; name.textContent = element.name; name.setAttribute('aria-hidden', 'true');
    button.append(symbol, name);
    button.addEventListener('click', () => select(index + 1));
    palette.append(button);
  });
  palette.append(document.querySelector('#erase'));

  function select(id) {
    selected = id; erasing = false;
    updateSelection();
  }

  // Elements with a second form: the palette name, color, and icon follow the setting.
  const BIRD_ICON = '<svg class="icon-bird" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 8.5 12 16l8-7.5"/></svg>';
  const FISH_ICON = '<svg class="icon-fish" viewBox="0 0 24 24" aria-hidden="true"><ellipse cx="13.5" cy="12" rx="6.5" ry="4"/><path d="M7.5 12 3 8v8z"/></svg>';
  const ALTERNATES = {
    [ID.GRAV]: { name: 'Antigrav', color: ANTIGRAV_COLOR, enabled: () => antigrav },
    [ID.BOID]: { name: 'Feesh', color: FEESH_COLOR, enabled: () => feesh, icons: [BIRD_ICON, FISH_ICON] }
  };

  function updateSelection() {
    [...palette.children].forEach((button, index) => {
      button.setAttribute('aria-pressed', String(!erasing && selected === index + 1));
      button.classList.toggle('phase-locked', phaseLock && PHASE_LOCKABLE.has(index + 1));
      const id = index + 1 < ELEMENTS.length ? index + 1 : ID.EMPTY;
      const symbol = button.querySelector('.element-symbol'), form = ALTERNATES[id];
      symbol.textContent = elementSymbol(id, phaseLock && PHASE_LOCKABLE.has(id));
      if (form) {
        const on = form.enabled(), name = on ? form.name : ELEMENTS[id].name;
        button.style.setProperty('--element-light', on ? form.color.light : ELEMENTS[id].light);
        button.style.setProperty('--element-dark', on ? form.color.dark : ELEMENTS[id].dark);
        if (form.icons) symbol.innerHTML = form.icons[Number(on)];
        button.querySelector('.element-name').textContent = name;
        button.setAttribute('aria-label', name);
        button.title = `${name} · ${ELEMENTS[id].hint}`;
      }
    });
    document.querySelector('#erase').setAttribute('aria-pressed', String(erasing));
    document.querySelector('#wind-settings').hidden = erasing || selected !== ID.WIND;
    document.querySelector('#grav-settings').hidden = erasing || selected !== ID.GRAV;
    document.querySelector('#antigrav').checked = antigrav;
    document.querySelector('#boid-settings').hidden = erasing || selected !== ID.BOID;
    document.querySelector('#feesh').checked = feesh;
    document.querySelector('#phase-lock').disabled = erasing || !PHASE_LOCKABLE.has(selected);
    document.querySelector('#phase-lock').checked = phaseLock;
    const element = ELEMENTS[erasing ? 0 : selected];
    document.querySelector('#element-hint').textContent = element.hint;
    document.querySelector('#element-properties').textContent = erasing ? 'erase / leave the surrounding matter intact' : selected === ID.WIND ? 'directional airflow / no particle mass' :
      `${element.state} / weight ${element.density.toFixed(2)} / viscosity ${element.viscosity.toFixed(2)} / thermal ${element.thermal.toFixed(2)} / electrical ${element.electrical.toFixed(2)} / ${element.temperature}°`;
    invalidate();
  }

  function updatePlayback() {
    const button = document.querySelector('#play');
    button.dataset.paused = String(paused);
    button.setAttribute('aria-label', paused ? 'Play' : 'Pause');
    button.title = paused ? 'Play' : 'Pause';
    status.textContent = paused ? 'Paused' : 'Running';
    clock.accumulator = 0;
    statsStart = performance.now(); renderedFrames = simulationSteps = simulationTime = drawTime = 0;
    if (paused) { document.querySelector('#fps').textContent = 'Paused'; document.querySelector('#tick-rate').textContent = '0 ticks / s'; }
    invalidate();
  }

  function invalidate() {
    dirty = true;
    if (!frame && inView && !document.hidden) { lastTime = performance.now(); frame = requestAnimationFrame(tick); }
  }

  function tick(now) {
    frame = 0;
    if (document.hidden || !inView) return;
    const elapsed = now - lastTime;
    lastTime = now;
    if (!paused) {
      const start = performance.now(), steps = ticksDue(clock, elapsed, speed);
      for (let step = 0; step < steps; step++) {
        if (drawing) paint(cursor.x, cursor.y);
        world.step();
      }
      simulationTime += performance.now() - start; simulationSteps += steps;
      dirty = true;
    } else clock.accumulator = 0;
    if (dirty) {
      const start = performance.now();
      const count = renderer.draw(cursor, diameter, overlays(), isWind() ? windDirection : null);
      drawTime += performance.now() - start; renderedFrames++;
      if (!statsStart) statsStart = now;
      if (now - lastInspection > 100 || paused) { inspect(); lastInspection = now; }
      if (now - lastReadout > 500 || paused) {
        document.querySelector('#population').textContent = `${count.toLocaleString()} particles`;
        lastReadout = now;
      }
      if (!paused && now - statsStart >= 750) {
        const seconds = (now - statsStart) / 1000;
        document.querySelector('#fps').textContent = `${Math.round(renderedFrames / seconds)} fps`;
        document.querySelector('#tick-rate').textContent = `${Math.round(simulationSteps / seconds)} ticks / s`;
        document.querySelector('#step-time').textContent = `${(simulationTime / Math.max(1, simulationSteps)).toFixed(2)} ms / tick`;
        document.querySelector('#draw-time').textContent = `${(drawTime / renderedFrames).toFixed(2)} ms / draw`;
        statsStart = now; renderedFrames = simulationSteps = simulationTime = drawTime = 0;
      }
      dirty = false;
    }
    if (!paused) frame = requestAnimationFrame(tick);
  }

  function isWind() { return selected === ID.WIND && !erasing && !shift; }
  function overlays() { return { wind: showWind, windArrows: showWindArrows, grav: showGravField, gravArrows: showGravArrows, temperature: showTemperature }; }
  function paint(x, y) {
    const alternate = selected === ID.GRAV ? antigrav : selected === ID.BOID ? feesh : false;
    world.paint(x, y, erasing || shift ? 0 : selected, diameter, windStrength, phaseLock, windDirection.x, windDirection.y, alternate);
  }
  function aim(point) {
    smoothAim(windDirection, point.x - cursor.x, point.y - cursor.y);
  }

  function inspectBoid(index) {
    if (world.polarity[index] > 0) return 'Boid';
    return world.submerged(index, index % world.size, Math.floor(index / world.size)) ? 'Feesh · swimming' : 'Feesh · stranded';
  }

  function inspect() {
    const index = Math.min(world.size - 1, Math.round(cursor.y)) * world.size + Math.min(world.size - 1, Math.round(cursor.x));
    const id = world.cells[index];
    document.querySelector('#inspected-name').textContent = !cursor.visible ? '—' : !id ? 'Air' : id === ID.SEED && world.roots[index] >= 0 ? (world.life[index] === 1 ? 'Seed · growing tip' : 'Seed · stem') : id === ID.GRAV && world.polarity[index] < 0 ? 'Grav · antigrav' : id === ID.BOID ? inspectBoid(index) : ELEMENTS[id].name;
    if (cursor.visible && id === ID.VAPOR && world.nitrogenVapor[index]) document.querySelector('#inspected-name').textContent = 'Vapor · nitrogen';
    document.querySelector('#inspected-properties').textContent = !cursor.visible ? '' :
      `${(id ? world.heat[index] : world.airHeat[index]).toFixed(0)}°${world.phaseLocked[index] ? ' / phase locked' : ''}${id ? ` / air ${world.airHeat[index].toFixed(0)}°` : ''} / charge ${world.charge[index].toFixed(2)} / pressure ${world.pressure[index].toFixed(2)} / flow ${Math.hypot(world.windX[index], world.windY[index]).toFixed(1)}`;
  }

  // Centralize screen-to-world mapping; a future transformable frame can replace
  // this mapping without changing the engine, palette, or renderer.
  function locate(event) {
    const rect = canvas.getBoundingClientRect();
    return {
      x: Math.max(-.5, Math.min(world.size - .500001, (event.clientX - rect.left) / rect.width * world.size - .5)),
      y: Math.max(-.5, Math.min(world.size - .500001, (event.clientY - rect.top) / rect.height * world.size - .5))
    };
  }

  function stroke(point) {
    const dx = point.x - cursor.x, dy = point.y - cursor.y;
    const steps = Math.max(1, Math.ceil(Math.hypot(dx, dy)));
    for (let i = 1; i <= steps; i++) paint(cursor.x + dx * i / steps, cursor.y + dy * i / steps);
  }

  canvas.addEventListener('pointerdown', event => {
    if (event.button !== 0 || pointer !== null) return;
    pointer = event.pointerId;
    canvas.setPointerCapture(pointer);
    canvas.focus({ preventScroll: true });
    Object.assign(cursor, locate(event), { visible: true });
    shift = event.shiftKey; drawing = true;
    paint(cursor.x, cursor.y); invalidate();
  });
  canvas.addEventListener('pointermove', event => {
    if (pointer !== null && event.pointerId !== pointer) return;
    const point = locate(event);
    aim(point);
    shift = event.shiftKey;
    if (drawing && (!isWind() || paused)) stroke(point);
    Object.assign(cursor, point, { visible: true }); invalidate();
  });
  function release() { drawing = false; pointer = null; shift = false; invalidate(); }
  canvas.addEventListener('pointerup', release);
  canvas.addEventListener('pointercancel', release);
  canvas.addEventListener('lostpointercapture', release);
  canvas.addEventListener('pointerleave', () => { if (!drawing) { cursor.visible = false; inspect(); invalidate(); } });
  canvas.addEventListener('focus', () => { cursor.visible = true; invalidate(); });
  canvas.addEventListener('blur', () => { cursor.visible = false; release(); });
  window.addEventListener('blur', release);

  // WebKit has no native range progress, so the track fill follows a variable.
  function syncRange(input) { input.style.setProperty('--fill', (input.value - input.min) / (input.max - input.min)); }

  function brush(value) {
    diameter = Math.max(1, Math.min(15, Math.round(value)));
    document.querySelector('#brush').value = diameter;
    syncRange(document.querySelector('#brush'));
    document.querySelector('#brush-value').textContent = diameter;
    invalidate();
  }
  canvas.addEventListener('keydown', event => {
    if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Enter', ' ', '[', ']'].includes(event.key) && !/^[1-9]$/.test(event.key)) return;
    event.preventDefault();
    shift = event.shiftKey;
    if (event.key.startsWith('Arrow')) {
      const point = { x: cursor.x, y: cursor.y };
      if (event.key === 'ArrowLeft') point.x--;
      if (event.key === 'ArrowRight') point.x++;
      if (event.key === 'ArrowUp') point.y--;
      if (event.key === 'ArrowDown') point.y++;
      point.x = Math.max(0, Math.min(world.size - 1, point.x));
      point.y = Math.max(0, Math.min(world.size - 1, point.y));
      aim(point);
      if (drawing && (!isWind() || paused)) stroke(point);
      Object.assign(cursor, point);
    } else if (event.key === 'Enter' && !event.repeat) { drawing = true; paint(cursor.x, cursor.y); }
    else if (event.key === ' ' && !event.repeat) { paused = !paused; updatePlayback(); }
    else if (event.key === '[') brush(diameter - 1);
    else if (event.key === ']') brush(diameter + 1);
    else if (/^[1-9]$/.test(event.key)) select(Number(event.key));
    invalidate();
  });
  canvas.addEventListener('keyup', event => { if (event.key === 'Enter') release(); if (event.key === 'Shift') shift = false; });

  document.querySelector('#play').addEventListener('click', () => { paused = !paused; updatePlayback(); });
  document.querySelector('#step').addEventListener('click', () => { paused = true; world.step(); updatePlayback(); });
  document.querySelector('#erase').addEventListener('click', () => { erasing = !erasing; updateSelection(); });
  document.querySelector('#wind-view').addEventListener('change', event => { showWind = event.target.checked; invalidate(); });
  document.querySelector('#temperature-view').addEventListener('change', event => {
    showTemperature = event.target.checked;
    document.querySelector('#temperature-key').hidden = !showTemperature;
    invalidate();
  });
  document.querySelector('#wind-arrows').addEventListener('change', event => { showWindArrows = event.target.checked; invalidate(); });
  document.querySelector('#zero-g').addEventListener('change', event => {
    zeroGravity = world.zeroGravity = event.target.checked;
    invalidate();
  });
  document.querySelector('#show-background').addEventListener('change', event => canvas.classList.toggle('has-background', event.target.checked));
  document.querySelector('#grav-view').addEventListener('change', event => { showGravField = event.target.checked; invalidate(); });
  document.querySelector('#grav-arrows').addEventListener('change', event => { showGravArrows = event.target.checked; invalidate(); });
  document.querySelector('#grav-strength').addEventListener('input', event => {
    gravStrength = Number(event.target.value);
    world.setGravStrength(gravStrength);
    document.querySelector('#grav-strength-value').textContent = `${gravStrength}×`;
    event.target.setAttribute('aria-valuetext', `${gravStrength}×`);
    invalidate();
  });
  document.querySelector('#wind-strength').addEventListener('input', event => {
    windStrength = Number(event.target.value);
    world.windStrength = windStrength;
    document.querySelector('#wind-strength-value').textContent = `${windStrength}×`;
  });
  document.querySelector('#phase-lock').addEventListener('change', event => {
    phaseLock = event.target.checked;
    updateSelection();
  });
  document.querySelector('#feesh').addEventListener('change', event => {
    feesh = event.target.checked;
    updateSelection();
  });
  document.querySelector('#antigrav').addEventListener('change', event => {
    antigrav = event.target.checked;
    updateSelection();
  });
  // Density is a pending setting: Load and Clear start an empty field at the
  // chosen resolution, rather than resampling the current contents.
  const density = document.querySelector('#density');
  let appliedDensity = 1;
  density.max = MAX_DENSITY;
  function showDensity() {
    document.querySelector('#density-value').textContent = `${Number(density.value)}×`;
    document.querySelector('#density-pending').hidden = Number(density.value) === appliedDensity;
  }
  function rebuild() {
    appliedDensity = Number(density.value);
    const size = sideFor(appliedDensity);
    if (size === world.size) world.clear();
    else {
      const scale = size / world.size;
      world = new World(size, world.seed);
      world.windStrength = windStrength;
      world.setGravStrength(gravStrength);
      world.zeroGravity = zeroGravity;
      cursor.x = Math.min(size - 1, cursor.x * scale); cursor.y = Math.min(size - 1, cursor.y * scale);
      coordinate();
    }
    renderer.setWorld(world);
    showDensity();
  }
  density.addEventListener('input', showDensity);
  document.querySelector('#speed').addEventListener('input', event => {
    speed = SPEEDS[Number(event.target.value)];
    document.querySelector('#speed-value').textContent = `${speed}×`;
    event.target.setAttribute('aria-valuetext', `${speed}×`);
  });
  document.querySelector('#blobs').addEventListener('change', event => {
    renderer.setBlobs(event.target.checked);
    invalidate();
  });
  document.querySelector('#show-symbols').addEventListener('change', event => { renderer.setShowSymbols(event.target.checked); invalidate(); });
  document.querySelector('#brush').addEventListener('input', event => brush(Number(event.target.value)));
  document.querySelector('#clear').addEventListener('click', () => { rebuild(); invalidate(); });
  document.querySelector('#load-scene').addEventListener('click', () => {
    const scene = document.querySelector('#scene').value;
    rebuild();
    if (scene !== 'empty') world.scene(scene);
    invalidate();
  });
  document.addEventListener('visibilitychange', () => {
    drawing = false;
    statsStart = 0; renderedFrames = simulationSteps = simulationTime = drawTime = 0;
    if (document.hidden) { cancelAnimationFrame(frame); frame = 0; }
    else { clock.accumulator = 0; invalidate(); }
  });
  new IntersectionObserver(entries => {
    inView = entries[0].isIntersecting;
    statsStart = 0; renderedFrames = simulationSteps = simulationTime = drawTime = 0;
    if (!inView) { cancelAnimationFrame(frame); frame = 0; drawing = false; }
    else { clock.accumulator = 0; invalidate(); }
  }).observe(canvas);
  // Observe the layout container: the renderer itself resizes the frame.
  new ResizeObserver(() => { renderer.resize(); invalidate(); }).observe(document.querySelector('.apparatus'));
  new MutationObserver(() => { renderer.palette(); invalidate(); }).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  reduced.addEventListener('change', () => { if (reduced.matches) { paused = true; updatePlayback(); } });
  document.querySelectorAll('input[type="range"]').forEach(input => { syncRange(input); input.addEventListener('input', () => syncRange(input)); });
  world.scene(); select(1); updatePlayback();
  renderer.draw(cursor, diameter, overlays());
}
