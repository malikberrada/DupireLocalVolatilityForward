"""Exact tensor Bernstein arithmetic; no optimization or tolerance in this module."""
from __future__ import annotations

from fractions import Fraction as F
from math import comb
import numpy as np


def rational(value):
    """A float denotes its exact binary64 value, a string an explicit rational."""
    return F(float(value)) if isinstance(value, (float, np.floating)) else F(value)


def derivative(a, axis, length, order=1):
    a = np.asarray(a, dtype=object)
    for _ in range(order):
        n = a.shape[axis] - 1
        if n == 0:
            a = np.zeros_like(a)
        else:
            a = np.diff(a, axis=axis) * (F(n) / length)
    return a


def elevate(a, axis, degree):
    a = np.moveaxis(np.asarray(a, dtype=object), axis, 0)
    n = a.shape[0] - 1
    if degree < n:
        raise ValueError("Degree reduction is not elevation")
    out = np.zeros((degree + 1,) + a.shape[1:], dtype=object)
    for k in range(degree + 1):
        for i in range(max(0, k-degree+n), min(n, k)+1):
            out[k] += a[i] * F(comb(n, i)*comb(degree-n, k-i), comb(degree, k))
    return np.moveaxis(out, 0, axis)


def times_x_squared(a, x0, x1):
    """Exact Bernstein product with x^2, increasing spatial degree by two."""
    a = np.asarray(a, dtype=object)
    n = a.shape[1] - 1
    out = np.zeros((a.shape[0], n+3) + a.shape[2:], dtype=object)
    for i in range(n+1):
        for j, b in enumerate((x0*x0, x0*x1, x1*x1)):
            out[:, i+j] += a[:, i] * b * F(comb(n, i)*comb(2, j), comb(n+2, i+j))
    return out


def basis(degree, u):
    return [F(comb(degree, i))*u**i*(1-u)**(degree-i) for i in range(degree+1)]


def evaluate(a, u, w):
    a = np.asarray(a, dtype=object)
    bt, bx = basis(a.shape[0]-1, u), basis(a.shape[1]-1, w)
    return sum((a[i, j]*bt[i]*bx[j] for i in range(len(bt)) for j in range(len(bx))),
               np.zeros(a.shape[2:], dtype=object))


def residual_polynomials(c, spec):
    """Each output must have nonnegative Bernstein coefficients.

    The trailing axis may hold an affine map: its last coordinate is constant.
    Otherwise c is a scalar polynomial and arithmetic is entirely rational.
    """
    m, n = c.shape[0]-1, c.shape[1]-1
    unit = F(1) if c.ndim == 2 else np.eye(1, c.shape[2], c.shape[2]-1, dtype=object)[0]
    one = np.ones_like(c)*unit
    x = np.array([spec["x0"]+(spec["x1"]-spec["x0"])*F(i, n)
                  for i in range(n+1)], dtype=object)
    x = x.reshape((1, n+1)+(1,)*(c.ndim-2))
    cx = derivative(c, 1, spec["x1"]-spec["x0"])
    gamma = derivative(cx, 1, spec["x1"]-spec["x0"])
    theta = elevate(derivative(c, 0, spec["t1"]-spec["t0"]), 0, m)
    x2gamma = times_x_squared(gamma, spec["x0"], spec["x1"])
    return [
        ("price_nonnegative", c),
        ("intrinsic", c-one*(1-x)),
        ("price_upper", one-c),
        ("decreasing", -cx),
        ("slope_lower", cx+np.ones_like(cx)*unit),
        ("gamma_floor", gamma-spec["gamma_floor"]*np.ones_like(gamma)*unit),
        ("local_lower", theta-(spec["vmin"]+spec["buffer"])*x2gamma/2),
        ("local_upper", (spec["vmax"]-spec["buffer"])*x2gamma/2-theta),
        ("left_origin", spec["x0"]*cx[:, 0]-c[:, 0]+one[:, 0]),
    ]
