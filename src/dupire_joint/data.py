from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import csv
import hashlib
import numpy as np


@dataclass
class Quotes:
    time: np.ndarray
    x: np.ndarray
    bid: np.ndarray
    ask: np.ndarray
    weight: np.ndarray | None = None

    def __post_init__(self):
        for k in ("time", "x", "bid", "ask"):
            setattr(self, k, np.asarray(getattr(self, k), dtype=np.float64).reshape(-1))
        n = len(self.time)
        if n == 0 or any(len(getattr(self,k)) != n for k in ("x","bid","ask")):
            raise ValueError("Quotes must be nonempty, with equal column lengths")
        if not all(np.isfinite(getattr(self,k)).all() for k in ("time","x","bid","ask")):
            raise ValueError("Nonfinite quote data")
        if np.any(self.time < 0) or np.any(self.x <= 0):
            raise ValueError("Require time >= 0 and normalized strike x > 0")
        # Crossed/negative quotes are retained: the feasibility diagnostic must see them.
        if self.weight is None:
            self.weight = np.maximum(np.abs(self.ask-self.bid)/2, 1e-5)
        else:
            self.weight = np.asarray(self.weight, dtype=np.float64).reshape(-1)
        if len(self.weight) != n or not np.isfinite(self.weight).all() or np.any(self.weight <= 0):
            raise ValueError("Quote weights must be finite and strictly positive")

    @classmethod
    def read(cls, path):
        with Path(path).open(newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            raise ValueError("Empty quote CSV")
        cols = {k: np.array([float(r[k]) for r in rows]) for k in ("time","x","bid","ask")}
        if "weight" in rows[0] and all(r.get("weight") for r in rows):
            cols["weight"] = np.array([float(r["weight"]) for r in rows])
        return cls(**cols)

    def write(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["time","x","bid","ask","weight"])
            writer.writerows(zip(self.time,self.x,self.bid,self.ask,self.weight))

    def digest(self):
        h = hashlib.sha256()
        for a in (self.time,self.x,self.bid,self.ask,self.weight):
            h.update(a.astype("<f8").tobytes())
        return h.hexdigest()

    @classmethod
    def from_surface(cls, times, strikes, prices, half_spread=0.0):
        t,x = np.meshgrid(times,strikes,indexing="ij")
        p = np.asarray(prices).reshape(t.shape)
        return cls(t.ravel(),x.ravel(),(p-half_spread).ravel(),(p+half_spread).ravel())


def refine_axis(axis, level):
    axis = np.unique(np.asarray(axis,dtype=float))
    if not isinstance(level, int) or level < 0 or level > 12:
        raise ValueError("Refinement level must be an integer in [0,12]")
    for _ in range(level):
        axis = np.sort(np.concatenate([axis,(axis[1:]+axis[:-1])/2]))
    if np.any(np.diff(axis) <= 0):
        raise ValueError("Grid spacing below floating-point resolution")
    return axis


@dataclass
class Grid:
    times: np.ndarray
    strikes: np.ndarray
    tail_x: float | None = None

    def __post_init__(self):
        self.times = np.asarray(self.times,dtype=float)
        self.strikes = np.asarray(self.strikes,dtype=float)
        for a,n in ((self.times,2),(self.strikes,3)):
            if a.ndim != 1 or len(a) < n or not np.isfinite(a).all() or np.any(np.diff(a)<=0):
                raise ValueError("Need >=2 increasing times and >=3 increasing strikes")
        if self.times[0] < 0 or self.strikes[0] <= 0:
            raise ValueError("Invalid grid domain")
        if self.tail_x is not None and (not np.isfinite(self.tail_x) or self.tail_x != self.strikes[-1]):
            raise ValueError("Tail anchor must be the final strike")

    @classmethod
    def from_quotes(cls, q, space_level=0, time_level=0, tail_x=None):
        x = np.unique(q.x)
        if tail_x is not None:
            if tail_x <= x[-1] or not np.isfinite(tail_x):
                raise ValueError("tail_x must exceed every observed strike")
            x = np.r_[x,tail_x]
        return cls(refine_axis(np.unique(q.time),time_level),refine_axis(x,space_level),tail_x)

    def quote_indices(self,q):
        j = np.searchsorted(self.times,q.time)
        i = np.searchsorted(self.strikes,q.x)
        if np.any(j>=len(self.times)) or np.any(i>=len(self.strikes)):
            raise ValueError("Quote outside grid")
        if not np.array_equal(self.times[j],q.time) or not np.array_equal(self.strikes[i],q.x):
            raise ValueError("Every observed node must be retained exactly; no quote interpolation")
        return j*len(self.strikes)+i

    @property
    def shape(self):
        return len(self.times),len(self.strikes)

