"""Port of web/app.mjs, web/index.html, and web/simian.css onto Qt widgets."""
import math
import subprocess
import sys
import time
from types import SimpleNamespace

import numpy as np
from PySide6.QtCore import QEvent, QPointF, QRectF, QSettings, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QFontMetricsF, QGuiApplication, QImage, QPainter,
                           QPainterPath, QPen, QPixmap, QRadialGradient)
from PySide6.QtWidgets import QAbstractButton, QApplication, QComboBox, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .aim import Direction, smooth_aim
from .clock import Clock, ticks_due
from .engine import (ANTIGRAV_COLOR, BOID, ELEMENTS, EMPTY, FEESH_COLOR, GRAV, PHASE_LOCKABLE, SEED, VAPOR, WIND,
                     World, element_symbol)
from .renderer import Renderer

# At 1× density the grid gives legible ~11 CSS px cells, so larger fields hold
# more cells. A 208-cell side keeps a tick within a 60 Hz budget; 0.5× on the
# smallest field reaches the 24-cell floor, on which every scene fits.
CELL_TARGET, MIN_SIDE, MAX_SIDE = 11, 24, 208
# Tick speed steps are roughly logarithmic, so 1× is not crowded at one end.
SPEEDS = (.5, .75, 1, 1.5, 2, 3, 4, 6, 8)
SCENES = (('estuary', 'Estuary'), ('water-cycle', 'Water cycle'), ('convection', 'Vapor convection'),
          ('test-tubes', 'Test tubes'), ('empty', 'Empty chamber'))
SANS = 'Helvetica Neue'
MONO = None  # The system fixed-width family, resolved once Qt is running.


def css_color(value):
    """#rrggbb or #rrggbbaa (CSS order) as a QColor."""
    result = QColor(value[:7])
    if len(value) == 9:
        result.setAlpha(int(value[7:], 16))
    return result


class Theme:
    """The site's color tokens (web/shell.css) for the current theme."""
    background: QColor; text: QColor; muted: QColor; accent: QColor; rule: QColor
    wash_one: QColor; wash_two: QColor; line: QColor
    grain: float
    dark: bool

    LIGHT = dict(background='#f5f4f0', text='#30322f', muted='#70736b', accent='#859079', rule='#393e3024',
                 wash_one='#dfdbe02b', wash_two='#e6ddca38', grain=.09)
    DARK = dict(background='#080909', text='#e2e3dc', muted='#a4a79d', accent='#a4af98', rule='#d6dcc624',
                wash_one='#46404b0c', wash_two='#53533c08', grain=.085)

    def __init__(self):
        self.apply(False)

    def apply(self, dark):
        self.dark = dark
        for name, value in (self.DARK if dark else self.LIGHT).items():
            setattr(self, name, css_color(value) if isinstance(value, str) else value)
        # color-mix(in oklch, var(--text) N%, transparent)
        self.line = self.mix(.3)

    def mix(self, alpha):
        value = QColor(self.text); value.setAlphaF(alpha)
        return value

    def element(self, colors):
        return css_color(colors['dark' if self.dark else 'light'])


theme = Theme()


def font(size, family: str | None = SANS, weight=QFont.Normal, spacing=0.0):
    """A pixel-sized font; `family=None` selects the system monospace family."""
    result = QFont(family or MONO); result.setPixelSize(max(1, round(size))); result.setWeight(weight)
    if spacing:
        result.setLetterSpacing(QFont.AbsoluteSpacing, spacing)
    return result


def prefers_reduced_motion():
    if sys.platform != 'darwin':
        return False
    try:
        result = subprocess.run(['defaults', 'read', 'com.apple.universalaccess', 'reduceMotion'],
                                capture_output=True, text=True, timeout=2)
        return result.stdout.strip() == '1'
    except (OSError, subprocess.SubprocessError):
        return False


class Button(QAbstractButton):
    """A painted control with hover tracking."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_Hover, True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.TabFocus)

    def hovered(self):
        return self.underMouse() and self.isEnabled()


class TextButton(Button):
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.setText(text)
        self.setFont(font(13))

    def sizeHint(self):
        return QSize(math.ceil(QFontMetricsF(self.font()).horizontalAdvance(self.text())), 28)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(theme.accent if self.hovered() else theme.text)
        painter.setFont(self.font())
        painter.drawText(self.rect(), Qt.AlignVCenter | Qt.AlignLeft, self.text())


class PlayButton(Button):
    """Both icons share one fixed-width box, so Step never shifts on toggle."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.paused = False
        self.setFixedSize(18, 28)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen); painter.setBrush(theme.accent if self.hovered() else theme.text)
        scale = 13 / 16
        painter.translate((self.width() - 13) / 2, (self.height() - 13) / 2); painter.scale(scale, scale)
        path = QPainterPath()
        if self.paused:
            path.moveTo(4.5, 2.5); path.lineTo(4.5, 13.5); path.lineTo(13.5, 8); path.closeSubpath()
        else:
            path.addRect(4, 3, 3, 10); path.addRect(9, 3, 3, 10)
        painter.drawPath(path)


class ThemeToggle(Button):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(32, 36)
        self.setToolTip('Dark mode')

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        tone = theme.text if self.hovered() else theme.muted
        center, radius = QPointF(self.width() / 2, self.height() / 2), 19 * 8 / 24
        painter.setPen(QPen(tone, 19 / 24)); painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(center, radius, radius)
        half = QPainterPath(); half.moveTo(center.x(), center.y() - radius)
        half.arcTo(QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2), 90, -180)
        half.closeSubpath()
        painter.fillPath(half, tone)


class CheckBox(Button):
    """An outlined square that fills with an inset square when on."""

    def __init__(self, text, caveat='', size=13, gap=10, checked=False, parent=None):
        super().__init__(parent)
        self.setCheckable(True); self.setChecked(checked)
        self.setText(text)
        self.caveat, self.gap = caveat, gap
        self.setFont(font(size))
        self.toggled.connect(self.update)

    def label_width(self):
        return 14 + self.gap + QFontMetricsF(self.font()).horizontalAdvance(self.text())

    def wrapped(self):
        """A caveat that does not fit flows onto its own line, like inline text."""
        return bool(self.caveat) and self.label_width() + 4 + QFontMetricsF(font(11)).horizontalAdvance(self.caveat) > self.width()

    def sizeHint(self):
        return QSize(math.ceil(self.label_width()), 40 if self.wrapped() else 24)

    def resizeEvent(self, event):
        self.setFixedHeight(40 if self.wrapped() else 24)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if not self.isEnabled():
            painter.setOpacity(.4)
        line = 24
        box = QRectF(.5, (line - 14) / 2 + .5, 13, 13)
        on = self.isChecked()
        painter.setPen(QPen(theme.text if on or self.hovered() else theme.line, 1))
        painter.setBrush(theme.text if on else Qt.NoBrush)
        painter.drawRoundedRect(box, 3, 3)
        if on:
            painter.setPen(Qt.NoPen); painter.setBrush(theme.background)
            painter.drawRect(box.adjusted(3.5, 3.5, -3.5, -3.5))
            painter.setBrush(theme.text)
            painter.drawRect(box.adjusted(6.5, 6.5, -6.5, -6.5))
        painter.setPen(theme.text); painter.setFont(self.font())
        left = 14 + self.gap
        painter.drawText(QRectF(left, 0, self.width() - left, line), Qt.AlignVCenter | Qt.AlignLeft, self.text())
        if self.caveat:
            wrapped = self.wrapped()
            caveat_left = left if wrapped else self.label_width() + 4
            painter.setPen(theme.muted); painter.setOpacity(painter.opacity() * .75); painter.setFont(font(11))
            area = QRectF(caveat_left, line - 6 if wrapped else 0, self.width() - caveat_left, line if not wrapped else 18)
            painter.drawText(area, Qt.AlignVCenter | Qt.AlignLeft, self.caveat)


class Slider(QWidget):
    """Name, track, and value on one line; a thin track fills to the thumb. The
    value column has a fixed width, so the track never resizes as it changes.
    Narrow panels move the track to its own line."""
    changed = Signal(float)

    def __init__(self, name, minimum, maximum, step, value, describe, parent=None):
        super().__init__(parent)
        self.name, self.minimum, self.maximum, self.step = name, minimum, maximum, step
        self.value, self.describe = value, describe
        self.dragging = False
        self.setFocusPolicy(Qt.TabFocus)
        self.setAttribute(Qt.WA_Hover, True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFont(font(13))
        self.setMinimumHeight(24)

    def stacked(self):
        return self.width() < 220

    def sizeHint(self):
        return QSize(200, 46 if self.stacked() else 24)

    def resizeEvent(self, event):
        self.setFixedHeight(46 if self.stacked() else 24)

    def track(self):
        """Returns (left, right, y) of the thumb's travel."""
        if self.stacked():
            return 6, self.width() - 6, 35
        label = QFontMetricsF(self.font()).horizontalAdvance(self.name)
        value_width = QFontMetricsF(font(11, None)).horizontalAdvance('0' * 5)
        return label + 12 + 6, self.width() - value_width - 12 - 6, self.height() / 2

    def fraction(self):
        return (self.value - self.minimum) / (self.maximum - self.minimum)

    def set_value(self, value, notify=True):
        value = round((value - self.minimum) / self.step) * self.step + self.minimum
        value = round(max(self.minimum, min(self.maximum, value)), 6)
        if value == self.value:
            return
        self.value = value
        self.update()
        if notify:
            self.changed.emit(value)

    def seek(self, x):
        left, right, _ = self.track()
        self.set_value(self.minimum + (x - left) / max(1, right - left) * (self.maximum - self.minimum))

    def mousePressEvent(self, event):
        left, right, _ = self.track()
        if left - 8 <= event.position().x() <= right + 8:
            self.dragging = True
            self.seek(event.position().x())

    def mouseMoveEvent(self, event):
        if self.dragging:
            self.seek(event.position().x())

    def mouseReleaseEvent(self, event):
        self.dragging = False

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Left, Qt.Key_Down):
            self.set_value(self.value - self.step)
        elif event.key() in (Qt.Key_Right, Qt.Key_Up):
            self.set_value(self.value + self.step)
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        left, right, y = self.track()
        label_rect = QRectF(0, 0, self.width(), 24 if self.stacked() else self.height())
        painter.setPen(theme.text); painter.setFont(self.font())
        painter.drawText(label_rect, Qt.AlignVCenter | Qt.AlignLeft, self.name)
        painter.setPen(theme.muted); painter.setFont(font(11, None))
        painter.drawText(label_rect, Qt.AlignVCenter | Qt.AlignRight, self.describe(self.value))
        thumb = left + (right - left) * self.fraction()
        painter.setPen(QPen(theme.line, 2, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(QPointF(left - 6, y), QPointF(right + 6, y))
        painter.setPen(QPen(theme.text, 2, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(QPointF(left - 6, y), QPointF(thumb, y))
        radius = 6 * (1.15 if self.underMouse() or self.dragging else 1) - .75
        if self.hasFocus():
            glow = QColor(theme.accent); glow.setAlphaF(.4)
            painter.setPen(Qt.NoPen); painter.setBrush(glow)
            painter.drawEllipse(QPointF(thumb, y), radius + 3.75, radius + 3.75)
        painter.setPen(QPen(theme.text, 1.5)); painter.setBrush(theme.background)
        painter.drawEllipse(QPointF(thumb, y), radius, radius)


class SceneSelect(QComboBox):
    """Underlined, with a small chevron."""

    def __init__(self, parent=None):
        super().__init__(parent)
        for value, label in SCENES:
            self.addItem(label, value)
        self.setFont(font(13))
        self.setAttribute(Qt.WA_Hover, True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(28)
        self.setAttribute(Qt.WA_LayoutUsesWidgetRect)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(theme.text); painter.setFont(self.font())
        painter.drawText(QRectF(0, 0, self.width() - 20, self.height()), Qt.AlignVCenter | Qt.AlignLeft, self.currentText())
        painter.setPen(QPen(theme.text if self.underMouse() else theme.line, 1))
        painter.drawLine(QPointF(0, self.height() - .5), QPointF(self.width(), self.height() - .5))
        painter.setPen(QPen(theme.muted, 1.2))
        x, y = self.width() - 9, self.height() * .55
        painter.drawPolyline([QPointF(x - 3, y - 1.5), QPointF(x, y + 1.5), QPointF(x + 3, y - 1.5)])


class ElementButton(Button):
    """A palette entry: the element's glyph (or boid icon) above its name."""

    def __init__(self, id, parent=None):
        super().__init__(parent)
        self.id = id
        self.setCheckable(True)
        self.name = ELEMENTS[id].name
        self.colors = ELEMENTS[id]._asdict()
        self.symbol = ELEMENTS[id].symbol
        self.icon_shape = 'bird' if id == BOID else None
        self.locked_style = False
        self.compact = False

    def configure(self, name, colors, symbol, icon_shape, locked_style):
        self.name, self.colors, self.symbol = name, colors, symbol
        self.icon_shape, self.locked_style = icon_shape, locked_style
        self.setToolTip(f'{name} · {ELEMENTS[self.id].hint}')
        self.setAccessibleName(name)
        self.update()

    def sizeHint(self):
        return QSize(56, 52 if self.compact else 60)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        tone = theme.element(self.colors)
        if self.isChecked() or self.hovered():
            painter.setPen(Qt.NoPen); painter.setBrush(theme.mix(.08 if self.isChecked() else .05))
            painter.drawRoundedRect(QRectF(self.rect()), 6, 6)
        column = self.width()
        size = min(30, column * .5)
        name_size = min(11, column / (6.2 if self.name == 'Liquid N₂' else 5.6))
        gap = 4 if self.compact else 6
        total = size + gap + name_size * 1.2
        top = (self.height() - total) / 2
        center = self.width() / 2
        if self.icon_shape:
            painter.save()
            painter.translate(center - size / 2, top); painter.scale(size / 24, size / 24)
            if self.icon_shape == 'bird':
                pen = QPen(tone, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                painter.setPen(pen); painter.setBrush(Qt.NoBrush)
                painter.drawPolyline([QPointF(4, 8.5), QPointF(12, 16), QPointF(20, 8.5)])
            else:
                painter.setPen(Qt.NoPen); painter.setBrush(tone)
                painter.drawEllipse(QPointF(13.5, 12), 6.5, 4)
                tail = QPainterPath(); tail.moveTo(7.5, 12); tail.lineTo(3, 8); tail.lineTo(3, 16); tail.closeSubpath()
                painter.drawPath(tail)
            painter.restore()
        else:
            glyph = font(size, None, QFont.Black if self.locked_style else QFont.Normal)
            path = QPainterPath(); path.addText(0, 0, glyph, self.symbol)
            bounds = path.boundingRect()
            advance = QFontMetricsF(glyph).horizontalAdvance(self.symbol)
            painter.translate(center - advance / 2, top + size / 2 - (bounds.top() + bounds.bottom()) / 2)
            painter.fillPath(path, tone)
            if self.locked_style:
                painter.strokePath(path, QPen(tone, .7))
            painter.resetTransform()
        painter.setPen(theme.text); painter.setFont(font(name_size, spacing=-.01 * name_size))
        name_top = top + size + gap
        painter.drawText(QRectF(0, name_top, self.width(), name_size * 1.4), Qt.AlignHCenter | Qt.AlignTop, self.name)
        if self.isChecked():
            painter.setPen(QPen(tone, 1))
            painter.drawLine(QPointF(center - 8, self.height() - 3.5), QPointF(center + 8, self.height() - 3.5))


class Section(QWidget):
    """A group of controls under a rule."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.body = QVBoxLayout(self)

    def set_rhythm(self, row, group):
        self.body.setContentsMargins(0, group, 0, 0)
        self.body.setSpacing(row)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(QRectF(0, 0, self.width(), 1), theme.rule)


class FieldView(QWidget):
    """The square field frame. The canvas is a whole number of device pixels per
    cell, centered in the frame on a device-pixel boundary."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)
        self.setAccessibleName('Particle field. Arrow keys move the brush; Enter places particles. '
                               'Hold Enter to paint. Shift erases.')

    def ratio(self):
        return min(self.devicePixelRatioF() or 1, 3)

    def available(self):
        return math.floor(self.width() * self.ratio())

    def canvas_rect(self):
        """The canvas in logical coordinates."""
        ratio, side = self.ratio(), self.app.renderer.side
        offset = math.floor((self.available() - side) / 2) / ratio
        return QRectF(offset, offset, side / ratio, side / ratio)

    def resizeEvent(self, event):
        self.app.renderer.resize(self.available())

    def paintEvent(self, event):
        self.app.draw(self)

    def mousePressEvent(self, event):
        self.app.pointer_down(event)

    def mouseMoveEvent(self, event):
        self.app.pointer_move(event)

    def mouseReleaseEvent(self, event):
        self.app.release()

    def leaveEvent(self, event):
        self.app.pointer_leave()

    def focusInEvent(self, event):
        self.app.cursor.visible = True
        self.app.invalidate()

    def focusOutEvent(self, event):
        self.app.cursor.visible = False
        self.app.release()

    def keyPressEvent(self, event):
        if not self.app.key_down(event):
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not event.isAutoRepeat():
            self.app.release()
        if event.key() == Qt.Key_Shift:
            self.app.shift = False


class Simian(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Simian')
        self.setMinimumSize(900, 720)
        self.settings = QSettings('Adam Nasir', 'Simian')
        saved = self.settings.value('theme')
        self.saved_theme = saved if saved in ('light', 'dark') else None
        hints = QGuiApplication.styleHints()
        theme.apply(self.saved_theme == 'dark' if self.saved_theme else hints.colorScheme() == Qt.ColorScheme.Dark)
        hints.colorSchemeChanged.connect(self.system_theme_changed)
        self.grain = self.make_grain()

        self.world = World(MIN_SIDE)
        self.renderer = Renderer(self.world)
        self.renderer.dark = theme.dark
        self.cursor = SimpleNamespace(x=0.0, y=0.0, visible=False)
        self.selected, self.diameter = 1, 5
        self.erasing = self.drawing = self.shift = self.grabbed = False
        self.paused = prefers_reduced_motion()
        self.dirty = True
        self.clock = Clock()
        self.overlays = dict(wind=False, wind_arrows=False, grav=False, grav_arrows=False, temperature=False)
        self.wind_strength, self.grav_strength, self.zero_gravity = 10, 1.0, False
        self.phase_lock = self.antigrav = self.feesh = False
        self.show_background = False
        self.speed = 1
        self.wind_direction = Direction(1, 0)
        self.applied_density = 1.0
        self.last_time = time.perf_counter()
        self.stats_start = 0.0
        self.rendered_frames = self.simulation_steps = 0
        self.simulation_time = self.draw_time = 0.0
        self.last_inspection = self.last_readout = 0.0
        self.readout_values = dict(fps='— fps', tick='— ms / tick', draw='— ms / draw', rate='— ticks / s')
        self.backdrop = None
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.setInterval(8)
        self.timer.timeout.connect(self.tick)

        self.build()
        self.resize(1440, 920)
        self.layout_window()
        self.world = World(self.side_for(1))
        self.renderer.set_world(self.world)
        self.cursor.x, self.cursor.y = self.world.size / 2, math.floor(self.world.size * .36)
        self.world.scene()
        self.select(1)
        self.update_playback()

    # Construction --------------------------------------------------------

    def label(self, text, size=13, family=SANS, role='text', wrap=False, spacing=0.0, weight=QFont.Normal):
        widget = QLabel(text, self)
        widget.setFont(font(size, family, weight, spacing))
        widget.setProperty('role', role)
        widget.setWordWrap(wrap)
        return widget

    def build(self):
        self.title = self.label('Simian', 30, weight=QFont.Light, spacing=-.045 * 30)
        self.title.setAlignment(Qt.AlignCenter)
        self.toggle = ThemeToggle(self)
        self.toggle.clicked.connect(self.toggle_theme)
        self.field = FieldView(self)
        self.coordinate = self.label('', 9, None, 'muted')
        self.corners = [self.label('+', 13, None, 'muted', weight=QFont.Light) for _ in range(4)]
        self.sections = []
        self.build_controls()
        self.build_elements()
        self.apply_theme()

    def section(self, panel_layout, title=None):
        section = Section(self)
        self.sections.append(section)
        if title:
            section.body.addWidget(self.label(title, 11, role='muted'))
        panel_layout.addWidget(section)
        return section.body

    def panel(self, title):
        panel = QWidget(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        heading = self.label(title.upper(), 10, role='muted', spacing=.8, weight=QFont.Medium)
        layout.addWidget(heading)
        return panel, layout

    def build_controls(self):
        self.controls, layout = self.panel('Controls')
        self.panel_layouts = [layout]
        group = QWidget(self.controls)
        group_layout = QVBoxLayout(group); group_layout.setContentsMargins(0, 0, 0, 0)
        self.group_layouts = [group_layout]
        playback = QHBoxLayout(); playback.setSpacing(20); playback.setContentsMargins(0, 0, 0, 0)
        self.play = PlayButton(); self.play.clicked.connect(self.toggle_pause)
        step = TextButton('Step'); step.clicked.connect(self.step_once)
        playback.addWidget(self.play); playback.addWidget(step); playback.addStretch()
        group_layout.addLayout(playback)
        self.speed_slider = Slider('Tick speed', 0, 8, 1, 2, lambda value: f'{SPEEDS[int(value)]:g}×')
        self.speed_slider.changed.connect(self.set_speed)
        group_layout.addWidget(self.speed_slider)
        layout.addWidget(group)

        brush = self.section(layout, 'Brush')
        self.brush_slider = Slider('Diameter', 1, 15, 1, 5, lambda value: f'{value:g}')
        self.brush_slider.changed.connect(self.brush)
        brush.addWidget(self.brush_slider)

        canvas = self.section(layout, 'Canvas')
        self.show_symbols = CheckBox('Show symbols', checked=True)
        self.show_symbols.toggled.connect(lambda on: (self.renderer.set_show_symbols(on), self.invalidate()))
        blobs = CheckBox('Blob mode', '(High performance impact!)')
        blobs.toggled.connect(lambda on: (self.renderer.set_blobs(on), self.invalidate()))
        background = CheckBox('Show background')
        background.toggled.connect(self.set_background)
        self.density = Slider('Grid density', .5, 2, .25, 1, lambda value: f'{value:g}×')
        self.density.changed.connect(self.show_density)
        self.density_pending = self.label('Applies on Load or Clear', 10, None, 'muted')
        self.density_pending.hide()
        zero_g = CheckBox('Zero-g')
        zero_g.toggled.connect(self.set_zero_gravity)
        for widget in (self.show_symbols, blobs, background, self.density, self.density_pending, zero_g):
            canvas.addWidget(widget)

        fields = self.section(layout, 'Fields')
        grid = QGridLayout(); grid.setContentsMargins(0, 0, 0, 0); grid.setHorizontalSpacing(6); grid.setVerticalSpacing(0)
        grid.setColumnStretch(0, 1); grid.setColumnMinimumWidth(1, 48); grid.setColumnMinimumWidth(2, 58)
        for row, (name, keys) in enumerate((('Gravity', ('grav', 'grav_arrows')), ('Wind', ('wind', 'wind_arrows')),
                                            ('Temperature', ('temperature',)))):
            grid.addWidget(self.label(name, 11), row, 0)
            for column, key in enumerate(keys, 1):
                box = CheckBox('Field' if column == 1 else 'Arrows', size=11, gap=5)
                box.toggled.connect(lambda on, key=key: self.set_overlay(key, on))
                grid.addWidget(box, row, column)
        fields.addLayout(grid)
        self.temperature_key = self.label('Blue · cold / clear · 20° / red · hot\nParticle temperature; air in empty cells.',
                                          10, None, 'muted', wrap=True)
        self.temperature_key.hide()
        fields.addWidget(self.temperature_key)

        scene = self.section(layout, 'Scene')
        self.scene_select = SceneSelect()
        scene.addWidget(self.scene_select)
        actions = QHBoxLayout(); actions.setSpacing(20); actions.setContentsMargins(0, 0, 0, 0)
        load = TextButton('Load ↗︎'); load.clicked.connect(self.load_scene)
        clear = TextButton('Clear'); clear.clicked.connect(lambda: (self.rebuild(), self.invalidate()))
        actions.addWidget(load); actions.addWidget(clear); actions.addStretch()
        scene.addLayout(actions)

        layout.addStretch(1)
        footer = QVBoxLayout(); footer.setSpacing(4); footer.setContentsMargins(0, 0, 0, 0)
        self.telemetry = self.label('', 10, None, 'muted', wrap=True)
        self.readout = self.label('', 10, None, 'muted', wrap=True)
        footer.addWidget(self.telemetry); footer.addWidget(self.readout)
        layout.addLayout(footer)
        inspector = self.section(layout)
        inspector.setSpacing(2)
        self.inspector_section = self.sections[-1]
        self.inspected_name = self.label('—', 13)
        self.inspected_properties = self.label('', 10, None, 'muted', wrap=True)
        self.inspected_properties.setMinimumHeight(30)
        inspector.addWidget(self.inspected_name); inspector.addWidget(self.inspected_properties)

    def build_elements(self):
        self.elements, layout = self.panel('Elements')
        self.panel_layouts.append(layout)
        self.palette_grid = QGridLayout(); self.palette_grid.setSpacing(4); self.palette_grid.setContentsMargins(0, 0, 0, 0)
        self.element_buttons = []
        for id in list(range(1, len(ELEMENTS))) + [EMPTY]:
            button = ElementButton(id)
            button.clicked.connect(lambda checked=False, id=id: self.toggle_erase() if id == EMPTY else self.select(id))
            index = len(self.element_buttons)
            self.palette_grid.addWidget(button, index // 4, index % 4)
            self.element_buttons.append(button)
        for column in range(4):
            self.palette_grid.setColumnStretch(column, 1)
        layout.addLayout(self.palette_grid)

        settings = self.section(layout)
        self.settings_section = self.sections[-1]
        self.phase_lock_box = CheckBox('Phase lock')
        self.phase_lock_box.toggled.connect(self.set_phase_lock)
        self.feesh_box = CheckBox('Feesh')
        self.feesh_box.toggled.connect(self.set_feesh)
        self.antigrav_box = CheckBox('Antigrav')
        self.antigrav_box.toggled.connect(self.set_antigrav)
        self.grav_slider = Slider('Strength', 0, 3, .1, 1, lambda value: f'{value:g}×')
        self.grav_slider.changed.connect(self.set_grav_strength)
        self.wind_slider = Slider('Wind strength', 10, 100, 1, 10, lambda value: f'{value:g}×')
        self.wind_slider.changed.connect(self.set_wind_strength)
        for widget in (self.phase_lock_box, self.feesh_box, self.antigrav_box, self.grav_slider, self.wind_slider):
            settings.addWidget(widget)
        settings.addStretch(1)
        layout.addWidget(self.settings_section, 1)

        note = self.section(layout)
        self.element_hint = self.label('', 12, wrap=True)
        self.element_properties = self.label('', 10, None, 'muted', wrap=True)
        note.addWidget(self.element_hint); note.addWidget(self.element_properties)

    # Appearance ----------------------------------------------------------

    @staticmethod
    def make_grain():
        """Gray noise with varying opacity, standing in for the site's grain.svg."""
        noise = np.random.default_rng(7).normal(128, 32, (2, 180, 180)).clip(0, 255).astype(np.uint32)
        pixels = noise[0] << 24 | noise[1] << 16 | noise[1] << 8 | noise[1]
        image = QImage(pixels.data, 180, 180, 180 * 4, QImage.Format_ARGB32)
        return QPixmap.fromImage(image.copy())

    def apply_theme(self):
        def hex_color(value):
            return value.name(QColor.HexArgb)
        self.setStyleSheet(
            f'QLabel {{ color: {hex_color(theme.text)}; background: transparent; }}'
            f'QLabel[role="muted"] {{ color: {hex_color(theme.muted)}; }}'
            f'QComboBox QAbstractItemView {{ background: {hex_color(theme.background)}; color: {hex_color(theme.text)};'
            f' selection-background-color: {hex_color(theme.mix(.08))}; selection-color: {hex_color(theme.text)}; }}')
        self.renderer.set_dark(theme.dark)
        self.backdrop = None
        self.update()
        for child in self.findChildren(QWidget):
            child.update()

    def toggle_theme(self):
        self.saved_theme = 'light' if theme.dark else 'dark'
        self.settings.setValue('theme', self.saved_theme)
        theme.apply(self.saved_theme == 'dark')
        self.apply_theme()
        self.invalidate()

    def system_theme_changed(self, scheme):
        if not self.saved_theme:
            theme.apply(scheme == Qt.ColorScheme.Dark)
            self.apply_theme()
            self.invalidate()

    def paintEvent(self, event):
        # The field repaints every frame over this backdrop, so it is cached.
        ratio = self.devicePixelRatioF()
        if not self.backdrop or self.backdrop.size() != self.size() * ratio:
            self.backdrop = QPixmap(self.size() * ratio)
            self.backdrop.setDevicePixelRatio(ratio)
            painter = QPainter(self.backdrop)
            painter.fillRect(self.rect(), theme.background)
            for color, (fx, fy) in ((theme.wash_one, (.14, .43)), (theme.wash_two, (.85, .65))):
                center = QPointF(self.width() * fx, self.height() * fy)
                gradient = QRadialGradient(center, max(self.width(), self.height()) * .55)
                clear = QColor(color); clear.setAlpha(0)
                gradient.setColorAt(0, color); gradient.setColorAt(1, clear)
                painter.fillRect(self.rect(), gradient)
            painter.setOpacity(theme.grain)
            painter.drawTiledPixmap(self.rect(), self.grain)
            painter.end()
        # Painting is clipped to the update region, so only that part is copied.
        QPainter(self).drawPixmap(0, 0, self.backdrop)

    # Layout --------------------------------------------------------------

    def layout_window(self):
        """The CSS grid: a square field filling the available height, narrowing
        only to keep minimum-width side panels that sit against it."""
        width, height = self.width(), self.height()
        padding = 76 if width > 900 else 36
        inner = width - 2 * padding
        heading_top, heading_height = 36, 30
        top = heading_top + heading_height + 24
        apparatus_height = max(590, height - top - 34)
        panel_min, gap = (200, 36) if width > 1100 else (176, 24)
        frame = max(120, min(apparatus_height - 24, inner - 2 * (panel_min + gap)))
        column = (inner - frame - 2 * gap) / 2
        panel_width = round(min(column, 264))
        page = min(inner, 1280 if width >= 1600 else 1200)
        page_left = (width - page) / 2
        self.title.setGeometry(round(page_left), heading_top - 4, round(page), heading_height + 8)
        self.toggle.move(round(page_left + page - self.toggle.width()), heading_top - 3)
        frame_left = round(padding + column + gap)
        self.field.setGeometry(frame_left, top, round(frame), round(frame))
        self.controls.setGeometry(round(padding + column - panel_width), top, panel_width, apparatus_height)
        self.elements.setGeometry(round(frame_left + frame + gap), top, panel_width, apparatus_height)
        self.coordinate.adjustSize()
        self.coordinate.move(frame_left, round(top + frame + 24 - self.coordinate.height()))
        for corner, (x, y) in zip(self.corners, ((0, 0), (1, 0), (0, 1), (1, 1))):
            corner.adjustSize()
            corner.move(round(frame_left - 12 + x * (frame + 24 - corner.width())),
                        round(top - 12 + y * (frame + 24 - corner.height())))
        # Shorter windows keep the type size but tighten the rhythm.
        short = height <= 860
        row, group = (6, 12) if short else (8, 16)
        for layout in self.panel_layouts:
            layout.setSpacing(group)
        for layout in self.group_layouts:
            layout.setSpacing(row)
        for section in self.sections:
            section.set_rhythm(row, group)
        self.settings_section.setMinimumHeight(84 if short else 96)
        self.inspector_section.setMinimumHeight(60 if short else 76)
        columns = (panel_width - 12) / 4
        for button in self.element_buttons:
            button.compact = short
            button.setMinimumHeight(52 if short else 60)
            button.setMinimumWidth(math.floor(columns))
        self.backdrop = None

    def resizeEvent(self, event):
        self.layout_window()
        self.invalidate()

    def side_for(self, density):
        """Cells are whole device pixels: the size nearest the density target, as
        many as fit. Halves round toward finer cells."""
        ratio = self.field.ratio()
        pixels = self.field.available() or round(700 * ratio)
        cell = max(3, math.ceil(CELL_TARGET * ratio / density - .5))
        return max(MIN_SIDE, min(MAX_SIDE, pixels // cell))

    # Selection and settings ----------------------------------------------

    def alternates(self):
        """Elements with a second form: the palette name, color, and icon follow the setting."""
        return {GRAV: ('Antigrav', ANTIGRAV_COLOR, self.antigrav, None),
                BOID: ('Feesh', FEESH_COLOR, self.feesh, ('bird', 'fish'))}

    def select(self, id):
        self.selected, self.erasing = id, False
        self.update_selection()

    def toggle_erase(self):
        self.erasing = not self.erasing
        self.update_selection()

    def update_selection(self):
        alternates = self.alternates()
        for button in self.element_buttons:
            id = button.id
            button.setChecked(self.erasing if id == EMPTY else not self.erasing and self.selected == id)
            locked = self.phase_lock and id in PHASE_LOCKABLE
            name, colors, icon = ELEMENTS[id].name, ELEMENTS[id]._asdict(), 'bird' if id == BOID else None
            if id in alternates:
                alt_name, alt_colors, on, icons = alternates[id]
                if on:
                    name, colors = alt_name, alt_colors
                if icons:
                    icon = icons[int(on)]
            button.configure(name, colors, element_symbol(id, locked), icon, locked)
        tool = EMPTY if self.erasing else self.selected
        self.wind_slider.setVisible(tool == WIND)
        self.antigrav_box.setVisible(tool == GRAV); self.grav_slider.setVisible(tool == GRAV)
        self.feesh_box.setVisible(tool == BOID)
        self.phase_lock_box.setEnabled(tool in PHASE_LOCKABLE)
        element = ELEMENTS[tool]
        self.element_hint.setText(f'<div style="line-height:160%">{element.hint}</div>')
        if self.erasing:
            properties = 'erase / leave the surrounding matter intact'
        elif tool == WIND:
            properties = 'directional airflow / no particle mass'
        else:
            properties = (f'{element.state} / weight {element.density:.2f} / viscosity {element.viscosity:.2f} / '
                          f'thermal {element.thermal:.2f} / electrical {element.electrical:.2f} / {element.temperature}°')
        properties = ' / '.join(part.replace(' ', '\u00a0') for part in properties.split(' / '))
        self.element_properties.setText(f'<div style="line-height:170%">{properties}</div>')
        self.invalidate()

    def set_phase_lock(self, on):
        self.phase_lock = on
        self.update_selection()

    def set_feesh(self, on):
        self.feesh = on
        self.update_selection()

    def set_antigrav(self, on):
        self.antigrav = on
        self.update_selection()

    def set_grav_strength(self, value):
        self.grav_strength = value
        self.world.set_grav_strength(value)
        self.invalidate()

    def set_wind_strength(self, value):
        self.wind_strength = value
        self.world.wind_strength = value

    def set_zero_gravity(self, on):
        self.zero_gravity = self.world.zero_gravity = on
        self.invalidate()

    def set_background(self, on):
        self.show_background = on
        self.invalidate()

    def set_overlay(self, key, on):
        self.overlays[key] = on
        if key == 'temperature':
            self.temperature_key.setVisible(on)
        self.invalidate()

    def set_speed(self, value):
        self.speed = SPEEDS[int(value)]

    def brush(self, value):
        self.diameter = max(1, min(15, round(value)))
        self.brush_slider.set_value(self.diameter, notify=False)
        self.invalidate()

    # Density is a pending setting: Load and Clear start an empty field at the
    # chosen resolution, rather than resampling the current contents.
    def show_density(self, value=None):
        self.density_pending.setVisible(self.density.value != self.applied_density)

    def rebuild(self):
        self.applied_density = self.density.value
        size = self.side_for(self.applied_density)
        if size == self.world.size:
            self.world.clear()
        else:
            scale = size / self.world.size
            self.world = World(size, self.world.seed)
            self.world.wind_strength = self.wind_strength
            self.world.set_grav_strength(self.grav_strength)
            self.world.zero_gravity = self.zero_gravity
            self.cursor.x = min(size - 1, self.cursor.x * scale); self.cursor.y = min(size - 1, self.cursor.y * scale)
        self.renderer.set_world(self.world)
        self.show_density()

    def load_scene(self):
        scene = self.scene_select.currentData()
        self.rebuild()
        if scene != 'empty':
            self.world.scene(scene)
        self.invalidate()

    # Playback ------------------------------------------------------------

    def toggle_pause(self):
        self.paused = not self.paused
        self.update_playback()

    def step_once(self):
        self.paused = True
        self.world.step()
        self.update_playback()

    def reset_stats(self):
        self.stats_start = time.perf_counter()
        self.rendered_frames = self.simulation_steps = 0
        self.simulation_time = self.draw_time = 0.0

    def update_playback(self):
        self.play.paused = self.paused
        self.play.setToolTip('Play' if self.paused else 'Pause')
        self.play.update()
        self.clock.accumulator = 0
        self.reset_stats()
        if self.paused:
            self.readout_values.update(fps='Paused', rate='0 ticks / s')
        self.show_readout()
        self.invalidate()

    def show_readout(self):
        values = self.readout_values
        self.readout.setText(' '.join(value.replace(' ', ' ') for value in values.values()))

    def invalidate(self):
        self.dirty = True
        if not self.timer.isActive() and self.isVisible() and not self.isMinimized():
            self.last_time = time.perf_counter()
            self.timer.start()

    def tick(self):
        now = time.perf_counter()
        elapsed = (now - self.last_time) * 1000
        self.last_time = now
        if not self.paused:
            start = time.perf_counter()
            steps = ticks_due(self.clock, elapsed, self.speed)
            for _ in range(steps):
                if self.drawing:
                    self.paint(self.cursor.x, self.cursor.y)
                self.world.step()
            self.simulation_time += (time.perf_counter() - start) * 1000
            self.simulation_steps += steps
            self.dirty = True
        else:
            self.clock.accumulator = 0
        if self.dirty:
            self.field.update()
        if self.paused:
            self.timer.stop()

    def draw(self, field):
        start = time.perf_counter()
        painter = QPainter(field)
        canvas = field.canvas_rect()
        if self.show_background:
            painter.fillRect(canvas, theme.mix(.05))
        ratio = field.ratio()
        painter.translate(canvas.topLeft())
        painter.scale(1 / ratio, 1 / ratio)
        count = self.renderer.draw(painter, self.cursor, self.diameter, self.overlays,
                                   self.wind_direction if self.is_wind() else None)
        painter.end()
        now = time.perf_counter()
        self.draw_time += (now - start) * 1000
        self.rendered_frames += 1
        self.dirty = False
        if now - self.last_inspection > .1 or self.paused:
            self.inspect(); self.last_inspection = now
        if now - self.last_readout > .5 or self.paused:
            self.telemetry.setText(f'{count:,} particles {"Paused" if self.paused else "Running"}')
            self.last_readout = now
        if not self.paused and now - self.stats_start >= .75:
            seconds = now - self.stats_start
            self.readout_values = dict(
                fps=f'{round(self.rendered_frames / seconds)} fps',
                tick=f'{self.simulation_time / max(1, self.simulation_steps):.2f} ms / tick',
                draw=f'{self.draw_time / self.rendered_frames:.2f} ms / draw',
                rate=f'{round(self.simulation_steps / seconds)} ticks / s')
            self.show_readout()
            self.reset_stats()
        coordinate = f'{self.world.size} × {self.world.size}'
        if self.coordinate.text() != coordinate:
            self.coordinate.setText(coordinate); self.coordinate.adjustSize()

    # Painting and inspection ---------------------------------------------

    def is_wind(self):
        return self.selected == WIND and not self.erasing and not self.shift

    def paint(self, x, y):
        alternate = self.antigrav if self.selected == GRAV else self.feesh if self.selected == BOID else False
        tool = EMPTY if self.erasing or self.shift else self.selected
        self.world.paint(x, y, tool, self.diameter, self.wind_strength, self.phase_lock,
                         self.wind_direction.x, self.wind_direction.y, alternate)

    def aim(self, point):
        smooth_aim(self.wind_direction, point[0] - self.cursor.x, point[1] - self.cursor.y)

    def inspect(self):
        world, cursor = self.world, self.cursor
        index = min(world.size - 1, round(cursor.y)) * world.size + min(world.size - 1, round(cursor.x))
        id = int(world.cells[index])
        if not cursor.visible:
            self.inspected_name.setText('—'); self.inspected_properties.setText('')
            return
        if not id:
            name = 'Air'
        elif id == SEED and world.roots[index] >= 0:
            name = 'Seed · growing tip' if world.life[index] == 1 else 'Seed · stem'
        elif id == GRAV and world.polarity[index] < 0:
            name = 'Grav · antigrav'
        elif id == BOID:
            if world.polarity[index] > 0:
                name = 'Boid'
            else:
                wet = world.submerged(index, index % world.size, index // world.size)
                name = 'Feesh · swimming' if wet else 'Feesh · stranded'
        elif id == VAPOR and world.nitrogen_vapor[index]:
            name = 'Vapor · nitrogen'
        else:
            name = ELEMENTS[id].name
        self.inspected_name.setText(name)
        temperature = world.heat[index] if id else world.air_heat[index]
        details = [f'{temperature:.0f}°' + (' / phase locked' if world.phase_locked[index] else '')]
        if id:
            details.append(f'air {world.air_heat[index]:.0f}°')
        details += [f'charge {world.charge[index]:.2f}', f'pressure {world.pressure[index]:.2f}',
                    f'flow {math.hypot(world.wind_x[index], world.wind_y[index]):.1f}']
        details = ' / '.join(part.replace(' ', '\u00a0') for part in details)
        self.inspected_properties.setText(f'<div style="line-height:160%">{details}</div>')

    # Centralize screen-to-world mapping; a future transformable frame can replace
    # this mapping without changing the engine, palette, or renderer.
    def locate(self, position):
        rect, n = self.field.canvas_rect(), self.world.size
        return (max(-.5, min(n - .500001, (position.x() - rect.left()) / rect.width() * n - .5)),
                max(-.5, min(n - .500001, (position.y() - rect.top()) / rect.height() * n - .5)))

    def stroke(self, point):
        dx, dy = point[0] - self.cursor.x, point[1] - self.cursor.y
        steps = max(1, math.ceil(math.hypot(dx, dy)))
        for i in range(1, steps + 1):
            self.paint(self.cursor.x + dx * i / steps, self.cursor.y + dy * i / steps)

    def pointer_down(self, event):
        if event.button() != Qt.LeftButton or self.grabbed:
            return
        self.grabbed = True
        self.field.setFocus()
        self.cursor.x, self.cursor.y = self.locate(event.position()); self.cursor.visible = True
        self.shift = bool(event.modifiers() & Qt.ShiftModifier); self.drawing = True
        self.paint(self.cursor.x, self.cursor.y)
        self.invalidate()

    def pointer_move(self, event):
        point = self.locate(event.position())
        self.aim(point)
        self.shift = bool(event.modifiers() & Qt.ShiftModifier)
        if self.drawing and (not self.is_wind() or self.paused):
            self.stroke(point)
        self.cursor.x, self.cursor.y = point; self.cursor.visible = True
        self.invalidate()

    def pointer_leave(self):
        if not self.drawing:
            self.cursor.visible = False
            self.inspect()
            self.invalidate()

    def release(self):
        self.drawing = self.grabbed = self.shift = False
        self.invalidate()

    def key_down(self, event):
        key, text = event.key(), event.text()
        arrows = {Qt.Key_Left: (-1, 0), Qt.Key_Right: (1, 0), Qt.Key_Up: (0, -1), Qt.Key_Down: (0, 1)}
        self.shift = bool(event.modifiers() & Qt.ShiftModifier)
        if key in arrows:
            n = self.world.size
            point = (max(0, min(n - 1, self.cursor.x + arrows[key][0])), max(0, min(n - 1, self.cursor.y + arrows[key][1])))
            self.aim(point)
            if self.drawing and (not self.is_wind() or self.paused):
                self.stroke(point)
            self.cursor.x, self.cursor.y = point
        elif key in (Qt.Key_Return, Qt.Key_Enter):
            if not event.isAutoRepeat():
                self.drawing = True
                self.paint(self.cursor.x, self.cursor.y)
        elif key == Qt.Key_Space:
            if not event.isAutoRepeat():
                self.toggle_pause()
        elif text == '[':
            self.brush(self.diameter - 1)
        elif text == ']':
            self.brush(self.diameter + 1)
        elif text and text in '123456789':
            self.select(int(text))
        else:
            return False
        self.invalidate()
        return True

    # Lifecycle: hidden or minimized windows suspend the loop -------------

    def changeEvent(self, event):
        if event.type() != QEvent.WindowStateChange:
            pass
        elif self.isMinimized():
            self.timer.stop(); self.drawing = False
        else:
            self.clock.accumulator = 0
            self.reset_stats()
            self.invalidate()
        super().changeEvent(event)

    def showEvent(self, event):
        self.invalidate()

    def hideEvent(self, event):
        self.timer.stop()
        self.drawing = False


def main():
    global MONO
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName('Simian')
    MONO = QFontDatabase.systemFont(QFontDatabase.FixedFont).family()
    window = Simian()
    window.show()
    return app.exec()

