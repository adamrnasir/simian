"""Port of web/renderer.mjs onto QPainter.

Glyphs are rasterized once per theme and cell size into an atlas; each frame
copies only changed cells into a device-pixel buffer (raster.blit_tiles), shown
1:1 rather than resampled. Blobs, overlays, and the cursor are then drawn in
device pixels, the same coordinates the canvas code uses.
"""
import numpy as np
from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QFontMetricsF, QImage, QPainter, QPainterPath, QPen

from . import raster
from .engine import (ANTIGRAV_COLOR, BOID, ELEMENTS, FEESH_COLOR, GRAV, MAX_AIR_SPEED, SAND, WATER, brush_start,
                     element_symbol)

# Over visible symbols, blobs are translucent so the glyphs stay legible.
BLOB_OVER_SYMBOLS = .4


def bird(flat):
    def draw(painter, left, top, size):
        pen = painter.pen(); pen.setWidthF(max(1.2, size * .12))
        pen.setCapStyle(Qt.RoundCap); pen.setJoinStyle(Qt.RoundJoin); painter.setPen(pen)
        wing, body = (.48, .6) if flat else (.3, .68)
        path = QPainterPath(QPointF(left + size * .14, top + size * wing))
        path.lineTo(left + size * .5, top + size * body)
        path.lineTo(left + size * .86, top + size * wing)
        painter.drawPath(path)
    return draw


def fish(facing):
    def draw(painter, left, top, size):
        x, y = left + size * (.5 + facing * .08), top + size * .5
        tail = x - facing * size * .24
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(x, y), size * .25, size * .15)
        path = QPainterPath(QPointF(tail, y))
        path.lineTo(tail - facing * size * .2, y - size * .16)
        path.lineTo(tail - facing * size * .2, y + size * .16)
        path.closeSubpath()
        painter.drawPath(path)
    return draw


def color(hex_color, alpha=1.0):
    value = QColor(hex_color); value.setAlphaF(alpha)
    return value


def image_array(image):
    """A numpy view of a 32-bit QImage's pixels (rows × columns)."""
    return np.frombuffer(image.constBits(), np.uint32).reshape(image.height(), image.bytesPerLine() // 4)[:, :image.width()]


def contour_path(outlines, unit):
    """Closed quadratic B-splines through the traced edge midpoints."""
    path = QPainterPath()
    for points in outlines:
        following = np.roll(points, -1, axis=0)
        middles = ((points + following) / 2 + .5) * unit
        corners = (points + .5) * unit
        path.moveTo(*middles[-1])
        for (cx, cy), (mx, my) in zip(corners.tolist(), middles.tolist()):
            path.quadTo(cx, cy, mx, my)
        path.closeSubpath()
    return path


class Renderer:
    def __init__(self, world):
        self.world = world
        self.show_symbols = True
        self.blobs = False
        self.dark = False
        self.available = 0
        self.mono = QFontDatabase.systemFont(QFontDatabase.FixedFont).family()
        self.resize(0)

    def resize(self, available):
        """Sizes cells to whole device pixels within `available` device pixels.
        Returns the canvas side in device pixels."""
        self.available = available
        self.cell = max(3, available // self.world.size)
        side = self.cell * self.world.size
        self.pixels = np.zeros((side, side), np.uint32)
        self.image = QImage(self.pixels.data, side, side, side * 4, QImage.Format_ARGB32_Premultiplied)
        self.previous = np.full(self.world.length, raster.STALE, np.uint8)
        self.blob_buffers = None
        self.palette()
        return side

    @property
    def side(self):
        return self.cell * self.world.size

    def set_world(self, world):
        self.world = world
        self.resize(self.available)

    def set_dark(self, dark):
        self.dark = dark
        self.palette()

    # Without symbols, each cell is a solid block of its glyph color.
    def set_show_symbols(self, show):
        self.show_symbols = show
        self.palette()

    # Blob mode draws smooth regions: translucent over the symbol tiles when
    # symbols are shown, or solid in their place. Leaving it forces every tile
    # to be redrawn into the pixel buffer.
    def set_blobs(self, on):
        self.blobs = on
        if not on:
            self.previous.fill(raster.STALE)

    def palette(self):
        dark, cell = self.dark, self.cell
        self.cursor_color = color('#e2e3dc' if dark else '#30322f')
        atlas = QImage(len(ELEMENTS) * cell, cell * 6, QImage.Format_ARGB32_Premultiplied)
        atlas.fill(Qt.transparent)
        painter = QPainter(atlas)
        painter.setRenderHint(QPainter.Antialiasing)

        # `backing` tints the cell (None for none); it defaults to the glyph color.
        def tile(id, column, row, variant, glyph, shape=None, backing=...):
            backing = glyph if backing is ... else backing
            left, top = column * cell, row * cell
            # Bake a faint material-colored backing into every glyph variant. Cached
            # cell replacement moves/removes the tint along with the particle.
            # Sand's tiny dot leaves mostly backing visible: give it a lighter bed
            # so a settled dune reads as pale sand rather than dark soil.
            if backing:
                alpha = (.30 if id == SAND else .14) if dark else (.10 if id == SAND else .16)
                painter.fillRect(QRectF(left, top, cell, cell), color(backing, alpha))
            glyph_color = color(('#fff2cf' if dark else '#b84931') if variant == 3 else glyph)
            if not self.show_symbols:
                painter.fillRect(QRectF(left, top, cell, cell), glyph_color)
                return
            painter.save()
            painter.setClipRect(QRectF(left, top, cell, cell))
            painter.setPen(QPen(glyph_color)); painter.setBrush(glyph_color)
            if shape:
                shape(painter, left, top, cell)
            else:
                self.glyph(painter, element_symbol(id, variant == 4), left, top, variant, glyph_color)
            painter.restore()

        for variant in range(5):
            for id, element in enumerate(ELEMENTS):
                if id:
                    tile(id, id, variant, variant, element.dark if dark else element.light)
        # Row 5 holds alternate forms: antigrav in Grav's column, boids in the unused columns 0–5.
        theme = 'dark' if dark else 'light'
        boid, feesh = getattr(ELEMENTS[BOID], theme), FEESH_COLOR[theme]
        tile(GRAV, GRAV, 5, 1, ANTIGRAV_COLOR[theme])
        # Birds and stranded feesh are bare glyphs; swimming feesh sit on water's tint.
        water = getattr(ELEMENTS[WATER], theme)
        tile(BOID, 0, 5, 1, boid, bird(False), None)
        tile(BOID, 1, 5, 1, boid, bird(True), None)
        tile(BOID, 2, 5, 1, feesh, fish(-1), water)
        tile(BOID, 3, 5, 1, feesh, fish(1), water)
        tile(BOID, 4, 5, 1, feesh, fish(-1), None)
        tile(BOID, 5, 5, 1, feesh, fish(1), None)
        painter.end()
        pixels = image_array(atlas)

        def cut(column, row):
            return pixels[row * cell:(row + 1) * cell, column * cell:(column + 1) * cell]
        self.atlas = np.empty((raster.TILE_COUNT, cell, cell), np.uint32)
        for variant in range(5):
            for id in range(len(ELEMENTS)):
                self.atlas[id + variant * len(ELEMENTS)] = cut(id, variant)
        self.atlas[raster.ANTIGRAV_TILE] = cut(GRAV, 5)
        for column, index in enumerate((raster.BIRD_TILE, raster.BIRD_FLAT_TILE, raster.FISH_LEFT_TILE,
                                        raster.FISH_RIGHT_TILE, raster.DRY_FISH_LEFT_TILE, raster.DRY_FISH_RIGHT_TILE)):
            self.atlas[index] = cut(column, 5)
        self.previous.fill(raster.STALE)

    def glyph(self, painter, symbol, left, top, variant, glyph_color):
        """fillText/strokeText with the canvas's centered alignment, maxWidth
        compression, and bounding-box vertical centering."""
        cell = self.cell
        weight = min(900, ((400, 500, 800, 800, 1000) if self.dark else (500, 600, 900, 900, 1000))[variant])
        font = QFont(self.mono); font.setPixelSize(max(1, round(cell * 1.5))); font.setWeight(QFont.Weight(weight))
        path = QPainterPath(); path.addText(0, 0, font, symbol)
        bounds, advance = path.boundingRect(), QFontMetricsF(font).horizontalAdvance(symbol)
        fit = min(1, cell * .96 / max(advance, bounds.height(), 1e-6))
        if fit < 1:
            font.setPixelSize(max(1, round(cell * 1.5 * fit)))
            path = QPainterPath(); path.addText(0, 0, font, symbol)
            bounds, advance = path.boundingRect(), QFontMetricsF(font).horizontalAdvance(symbol)
        squeeze = min(1, cell * .96 / advance) if advance else 1
        baseline = top + cell * .5 + (-bounds.top() - bounds.bottom()) / 2
        painter.translate(left + cell * .5 - advance * squeeze / 2, baseline)
        painter.scale(squeeze, 1)
        painter.fillPath(path, glyph_color)
        if (not self.dark and variant < 2) or variant == 4:
            pen = QPen(glyph_color, max(1, cell * .18) if variant == 4 else .45)
            pen.setJoinStyle(Qt.MiterJoin)
            painter.strokePath(path, pen)

    def draw(self, painter, cursor, diameter, overlays, direction=None):
        """Draws the field with `painter` in device pixels; returns the particle count."""
        unit, world = self.cell, self.world
        tiles = not self.blobs or self.show_symbols
        population = 0
        if tiles:
            population = raster.blit_tiles(world.state, self.atlas, self.pixels, self.previous)
            painter.drawImage(0, 0, self.image)
        if self.blobs:
            count = self.draw_blobs(painter, BLOB_OVER_SYMBOLS if tiles else 1)
            if not tiles:
                population = count
        if overlays.get('temperature'):
            self.present_field(painter, raster.temperature_pixels(world, self.dark))
        if overlays.get('wind') or overlays.get('wind_arrows'):
            self.draw_wind(painter, overlays.get('wind'), overlays.get('wind_arrows'))
        if overlays.get('grav') or overlays.get('grav_arrows'):
            self.draw_grav(painter, overlays.get('grav'), overlays.get('grav_arrows'))
        if cursor.visible:
            painter.save()
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setOpacity(.55); painter.setPen(QPen(self.cursor_color, 1)); painter.setBrush(Qt.NoBrush)
            cx = (brush_start(cursor.x, diameter) + diameter / 2) * unit
            cy = (brush_start(cursor.y, diameter) + diameter / 2) * unit
            path = QPainterPath()
            path.addEllipse(QPointF(cx, cy), diameter / 2 * unit, diameter / 2 * unit)
            if direction:
                length = (diameter / 2 + 3) * unit
                dx, dy = direction.x, direction.y
                ex, ey = cx + dx * length, cy + dy * length
                path.moveTo(cx, cy); path.lineTo(ex, ey)
                path.moveTo(ex - dx * unit - dy * unit * .5, ey - dy * unit + dx * unit * .5)
                path.lineTo(ex, ey); path.lineTo(ex - dx * unit + dy * unit * .5, ey - dy * unit - dx * unit * .5)
            painter.drawPath(path)
            painter.restore()
        return population

    def outlines(self, groups, group, bounds):
        n, buffers = self.world.size, self.blob_buffers
        contours = raster.trace_contours(groups, n, group, *bounds, buffers['next'], buffers['starts'],
                                         buffers['points'], buffers['ends'])
        points, ends, start = buffers['points'], buffers['ends'], 0
        for k in range(contours):
            yield points[start * 2:ends[k] * 2].reshape(-1, 2)
            start = ends[k]

    def draw_blobs(self, painter, alpha):
        """Groups cells by element (antigrav and feesh apart) and draws each
        group's contours as closed quadratic B-splines through the edge midpoints.
        Independently smoothed neighbors would leave slivers at corners and
        junctions, so each group is first stroked wide in its own color, clipped
        to the smoothed outline of all matter: gaps between blobs fill in, but no
        blob grows into empty space. Fills then go on top, keeping the shared
        boundaries where they were. The layer is composited once at `alpha`."""
        world, n, unit = self.world, self.world.size, self.cell
        keys = (n + 2) * (n + 2) * 2
        if not self.blob_buffers or len(self.blob_buffers['next']) != keys:
            self.blob_buffers = {'next': np.full(keys, -1, np.int64), 'starts': np.zeros(keys, np.int64),
                                 'points': np.zeros(keys * 2), 'ends': np.zeros(keys, np.int64)}
        cells = world.cells.astype(np.int64)
        alternate = ((cells == GRAV) | (cells == BOID)) & (world.polarity < 0)
        groups = np.where(cells != 0, cells * 2 + alternate, 0).astype(np.uint8)
        occupied = np.flatnonzero(groups)
        layer = QImage(self.side, self.side, QImage.Format_ARGB32_Premultiplied)
        layer.fill(Qt.transparent)
        if len(occupied):
            xs, ys = occupied % n, occupied // n
            theme = 'dark' if self.dark else 'light'
            shapes = []
            for group in np.unique(groups[occupied]):
                members = groups[occupied] == group
                id = int(group) >> 1
                colors = (ANTIGRAV_COLOR if id == GRAV else FEESH_COLOR) if group & 1 else ELEMENTS[id]._asdict()
                bounds = (int(xs[members].min()), int(ys[members].min()), int(xs[members].max()), int(ys[members].max()))
                shapes.append((color(colors[theme]), contour_path(self.outlines(groups, int(group), bounds), unit)))
            union = contour_path(self.outlines(groups, 0, (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))), unit)
            canvas = QPainter(layer)
            canvas.setRenderHint(QPainter.Antialiasing)
            canvas.setClipPath(union)
            for shape_color, path in shapes:
                pen = QPen(shape_color, unit); pen.setJoinStyle(Qt.RoundJoin)
                canvas.strokePath(path, pen)
            canvas.setClipping(False)
            for shape_color, path in shapes:
                canvas.fillPath(path, shape_color)
            canvas.end()
        painter.setOpacity(alpha)
        painter.drawImage(0, 0, layer)
        painter.setOpacity(1)
        return len(occupied)

    def present_field(self, painter, pixels):
        """Scales a cell-resolution RGBA buffer smoothly over the field."""
        n = self.world.size
        image = QImage(np.ascontiguousarray(pixels).data, n, n, n * 4, QImage.Format_RGBA8888)
        painter.save()
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.drawImage(QRectF(0, 0, self.side, self.side), image)
        painter.restore()

    def draw_wind(self, painter, show_pressure, show_arrows):
        world = self.world
        if show_pressure:
            self.present_field(painter, raster.pressure_pixels(world, self.dark))
        if show_arrows:
            def scale(speed):
                return np.where(speed < .025, 0, np.log1p(speed * 4) / np.log1p(np.sqrt(2) * MAX_AIR_SPEED * 4))
            self.draw_arrows(painter, world.wind_x, world.wind_y, '#a8e8d9' if self.dark else '#32746b',
                             scale, raster.blocked_mask(world))

    # Shows the net pull on powders and liquids: grav sources plus ordinary
    # gravity (absent in zero-g). Gas feels buoyancy instead and is not shown.
    def draw_grav(self, painter, show_field, show_arrows):
        world = self.world
        # The overlay may be shown while paused, before the next tick refreshes the
        # field. Recomputing is idempotent and skipped when no source changed.
        net_x, net_y, peak = raster.net_gravity(world)
        if show_field:
            self.present_field(painter, raster.gravity_pixels(world, net_x, net_y, peak, self.dark))
        if show_arrows:
            theme = 'dark' if self.dark else 'light'
            self.draw_arrows(painter, net_x, net_y, ANTIGRAV_COLOR[theme],
                             lambda speed: np.where(speed < .004, 0, np.minimum(1, speed / peak)), world.cells == GRAV)

    def draw_arrows(self, painter, field_x, field_y, arrow_color, scale, skip):
        """Draws a sparse arrow grid; `scale` maps magnitudes to 0–1 lengths."""
        n, unit, stride = self.world.size, self.cell, 4
        y, x = np.mgrid[1:n:stride, 1:n:stride]
        index = (y * n + x).ravel(); x = x.ravel(); y = y.ravel()
        vx, vy = field_x[index], field_y[index]
        speed = np.hypot(vx, vy); amount = scale(speed)
        keep = ~skip[index] & (amount > 0)
        x, y, vx, vy, speed, amount = x[keep], y[keep], vx[keep], vy[keep], speed[keep], amount[keep]
        cx, cy = (x + .5) * unit, (y + .5) * unit
        length = unit * 3 * amount; dx, dy = vx / speed, vy / speed
        head = np.minimum(unit * .5, length * .4)
        ex, ey = cx + dx * length, cy + dy * length
        # Shaft and both barbs as separate segments: batched lines draw far faster
        # than stroking one path with hundreds of subpaths.
        barbs = [(ex - dx * head - dy * head * .8, ey - dy * head + dx * head * .8),
                 (ex - dx * head + dy * head * .8, ey - dy * head - dx * head * .8)]
        segments = np.stack([np.stack([cx, cy, ex, ey], 1)] + [np.stack([bx, by, ex, ey], 1) for bx, by in barbs], 1)
        lines = [QLineF(*segment) for segment in segments.reshape(-1, 4).tolist()]
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setOpacity(.45); painter.setPen(QPen(QColor(arrow_color), max(1, unit / 8)))
        painter.drawLines(lines)
        painter.restore()
