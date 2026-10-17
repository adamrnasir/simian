"""Port of web/gravity.mjs: softened inverse-square gravity.

Nearby sources are exact; distant groups use Barnes–Hut aggregation so dense
brushes don't require all-pairs work. Positive and negative sources have
separate centers, preserving dipoles. The quadtree lives in flat arrays so the
whole computation compiles with numba.
"""
import math

import numpy as np
from numba import njit

# Above this many sources, the field uses the quadtree approximation.
DIRECT_LIMIT = 32


@njit(cache=True)
def _build_tree(size, xs, ys, signs):
    count = len(xs)
    # A node holding two distinct integer points is wider than one cell, so
    # no path is deeper than ceil(log2(size)) + 1 nodes.
    capacity = count * (int(math.ceil(math.log2(max(size, 2)))) + 2) + 1
    left = np.empty(capacity); top = np.empty(capacity); width = np.empty(capacity)
    positive = np.zeros(capacity, np.int64); negative = np.zeros(capacity, np.int64)
    px = np.zeros(capacity); py = np.zeros(capacity); nx = np.zeros(capacity); ny = np.zeros(capacity)
    first_child = np.zeros(capacity, np.int64); child_count = np.zeros(capacity, np.int64)
    start = np.zeros(capacity, np.int64); end = np.zeros(capacity, np.int64)
    order = np.arange(count); scratch = np.empty(count, np.int64)
    left[0] = -.5; top[0] = -.5; width[0] = size; end[0] = count
    nodes = 1
    for node in range(capacity):
        if node >= nodes:
            break
        for k in range(start[node], end[node]):
            p = order[k]
            if signs[p] > 0:
                positive[node] += 1; px[node] += xs[p]; py[node] += ys[p]
            else:
                negative[node] += 1; nx[node] += xs[p]; ny[node] += ys[p]
        if positive[node]:
            px[node] /= positive[node]; py[node] /= positive[node]
        if negative[node]:
            nx[node] /= negative[node]; ny[node] /= negative[node]
        if end[node] - start[node] <= 1:
            continue
        # Stable partition into quadrants (left/right, then top/bottom).
        half = width[node] / 2
        first_child[node] = nodes
        cursor = start[node]
        for quadrant in range(4):
            group_start = cursor
            for k in range(start[node], end[node]):
                p = order[k]
                if int(xs[p] >= left[node] + half) + 2 * int(ys[p] >= top[node] + half) == quadrant:
                    scratch[cursor] = p; cursor += 1
            if cursor > group_start:
                left[nodes] = left[node] + (quadrant % 2) * half
                top[nodes] = top[node] + (quadrant >> 1) * half
                width[nodes] = half
                start[nodes] = group_start; end[nodes] = cursor
                nodes += 1; child_count[node] += 1
        order[start[node]:end[node]] = scratch[start[node]:end[node]]
    return left, top, width, positive, negative, px, py, nx, ny, first_child, child_count


@njit(cache=True)
def _pull(dx, dy, mass):
    r2 = dx * dx + dy * dy + 9
    return 5 * mass / (r2 * math.sqrt(r2))


@njit(cache=True)
def _store(field_x, field_y, i, fx, fy, limit):
    magnitude = math.hypot(fx, fy)
    scale = min(1.0, limit / (magnitude if magnitude else 1.0))
    field_x[i] = fx * scale; field_y[i] = fy * scale


@njit(cache=True)
def _direct_field(size, xs, ys, signs, field_x, field_y, limit):
    i = 0
    for y in range(size):
        for x in range(size):
            fx = 0.0; fy = 0.0
            for p in range(len(xs)):
                strength = _pull(xs[p] - x, ys[p] - y, signs[p])
                fx += (xs[p] - x) * strength; fy += (ys[p] - y) * strength
            _store(field_x, field_y, i, fx, fy, limit)
            i += 1


@njit(cache=True)
def _tree_field(size, xs, ys, signs, field_x, field_y, limit):
    left, top, width, positive, negative, px, py, nx, ny, first_child, child_count = _build_tree(size, xs, ys, signs)
    stack = np.empty(len(left), np.int64)
    i = 0
    for y in range(size):
        for x in range(size):
            fx = 0.0; fy = 0.0
            stack[0] = 0; depth = 1
            while depth:
                depth -= 1
                node = stack[depth]
                dx = x - (left[node] + width[node] / 2); dy = y - (top[node] + width[node] / 2)
                # Opening angle 0.5: never approximate a node containing the target.
                if not child_count[node] or width[node] * width[node] < .25 * (dx * dx + dy * dy):
                    if positive[node]:
                        strength = _pull(px[node] - x, py[node] - y, positive[node])
                        fx += (px[node] - x) * strength; fy += (py[node] - y) * strength
                    if negative[node]:
                        strength = _pull(nx[node] - x, ny[node] - y, -negative[node])
                        fx += (nx[node] - x) * strength; fy += (ny[node] - y) * strength
                else:
                    # Reverse order preserves the recursive visiting order.
                    for child in range(child_count[node] - 1, -1, -1):
                        stack[depth] = first_child[node] + child; depth += 1
            _store(field_x, field_y, i, fx, fy, limit)
            i += 1


@njit(cache=True)
def radial_gravity(size, xs, ys, signs, field_x, field_y, limit):
    """Fills field_x/field_y (length size²) from sources at (xs, ys) with polarity signs."""
    field_x[:] = 0; field_y[:] = 0
    if len(xs) > DIRECT_LIMIT:
        _tree_field(size, xs, ys, signs, field_x, field_y, limit)
    elif len(xs):
        _direct_field(size, xs, ys, signs, field_x, field_y, limit)
