"""Hi-C contact maps in cooler's HDF5 format (.cool and .mcool), read and written with h5py alone, and the maths the
live session uses on them: balancing (ICE), distance decay, compartments (first eigenvector) and insulation.

Layout (cooler format version 3; an .mcool holds one of these under resolutions/<bin size>/):
  chroms/name, chroms/length
  bins/chrom, bins/start, bins/end, bins/weight (balancing weight; NaN for masked bins)
  pixels/bin1_id, pixels/bin2_id, pixels/count     upper triangle only, sorted by bin1 then bin2
  indexes/chrom_offset (first bin of each chromosome), indexes/bin1_offset (first pixel of each bin1)
Keeping to h5py means no extra dependency; files written here open in cooler and HiGlass as well.
"""
from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np


# ---------------------------------------------------------------- reading
class Cool:
    """One resolution of a .cool or .mcool file."""

    def __init__(self, path, res: int | None = None):
        self.path = str(path)
        with h5py.File(self.path, "r") as f:
            self.group = f"resolutions/{res}" if "resolutions" in f else "/"
            if "resolutions" in f and res is None:
                raise ValueError("Choose a resolution for a multi-resolution (.mcool) file.")
            if self.group not in f:
                raise ValueError(f"{Path(self.path).name} has no {res:,} bp resolution.")
            g = f[self.group]
            self.res = int(g.attrs.get("bin-size"))
            names = g["chroms/name"][:]
            self.chroms = [n.decode() if isinstance(n, bytes) else str(n) for n in names]
            self.lengths = [int(x) for x in g["chroms/length"][:]]
            self.chrom_offset = g["indexes/chrom_offset"][:].astype(int)
            self.bin1_offset = g["indexes/bin1_offset"][:]
            self.weight = g["bins/weight"][:] if "weight" in g["bins"] else None
            self.nbins = len(self.bin1_offset) - 1

    def chrom_bins(self, chrom: str) -> tuple[int, int]:
        i = self.chroms.index(chrom)
        return int(self.chrom_offset[i]), int(self.chrom_offset[i + 1])

    def pixels(self, lo: int, hi: int):
        """Pixels whose first bin is in [lo, hi): bin1, bin2, count."""
        with h5py.File(self.path, "r") as f:
            g = f[self.group]
            a, b = int(self.bin1_offset[lo]), int(self.bin1_offset[hi])
            return g["pixels/bin1_id"][a:b], g["pixels/bin2_id"][a:b], g["pixels/count"][a:b]

    def matrix(self, lo: int, hi: int, balanced: bool = True) -> np.ndarray:
        """The square map of bins [lo, hi) (symmetric). Balanced maps have NaN in masked rows and columns."""
        b1, b2, c = self.pixels(lo, hi)
        keep = b2 < hi
        b1, b2, c = b1[keep] - lo, b2[keep] - lo, c[keep].astype(float)
        n = hi - lo
        m = np.zeros((n, n))
        m[b1, b2] = c
        m[b2, b1] = c
        if balanced and self.weight is not None:
            w = self.weight[lo:hi]
            m = m * w[:, None] * w[None, :]
        return m

    def band(self, lo: int, hi: int, width: int, balanced: bool = True) -> np.ndarray:
        """B[i, d] = the contact between bins lo + i and lo + i + d, for d up to width (NaN past the end or where
        a bin is masked). Enough for insulation without building a whole chromosome's map."""
        b1, b2, c = self.pixels(lo, hi)
        d = b2 - b1
        keep = (b2 < hi) & (d <= width)
        n = hi - lo
        out = np.zeros((n, width + 1))
        out[b1[keep] - lo, d[keep]] = c[keep]
        idx = np.arange(n)[:, None] + np.arange(width + 1)[None, :]
        out[idx >= n] = np.nan
        if balanced and self.weight is not None:
            w = np.concatenate([self.weight[lo:hi], np.full(width + 1, np.nan)])
            out = out * w[:n, None] * w[np.minimum(idx, n + width)]
        return out

    def decay(self, chrom: str, balanced: bool = True) -> tuple[np.ndarray, np.ndarray]:
        """Average contact at each distance along a chromosome (bins masked by balancing left out), from pixels."""
        lo, hi = self.chrom_bins(chrom)
        n = hi - lo
        b1, b2, c = self.pixels(lo, hi)
        keep = b2 < hi
        b1, b2, c = b1[keep] - lo, b2[keep] - lo, c[keep].astype(float)
        w = self.weight[lo:hi] if balanced and self.weight is not None else np.ones(n)
        v = c * w[b1] * w[b2]
        ok = np.isfinite(v)
        sums = np.bincount((b2 - b1)[ok], v[ok], n)
        valid = np.isfinite(w).astype(float)
        pairs = np.correlate(valid, valid, "full")[n - 1:]      # pairs[d]: bins i with i and i + d both usable
        with np.errstate(divide="ignore", invalid="ignore"):
            mean = sums / pairs
        d = np.arange(n)
        sel = (d >= 1) & (pairs > 0)
        return d[sel] * self.res, mean[sel]

    def totals(self) -> dict:
        """Contacts within chromosomes (cis), between them (trans), and cis split at 20 kb (short/long range)."""
        out = {"cis": 0, "trans": 0, "short": 0, "long": 0}
        chrom_of = np.repeat(np.arange(len(self.chroms)), np.diff(self.chrom_offset))
        # Intent: read the pixels in slices of bins, so a large genome never has to fit in memory at once.
        for a in range(0, self.nbins, 4000):
            b1, b2, c = self.pixels(a, min(self.nbins, a + 4000))
            cis = chrom_of[b1] == chrom_of[b2]
            far = (b2 - b1) * self.res >= 20_000
            out["cis"] += int(c[cis].sum())
            out["trans"] += int(c[~cis].sum())
            out["long"] += int(c[cis & far].sum())
            out["short"] += int(c[cis & ~far].sum())
        return out


def resolutions(path) -> list[int]:
    with h5py.File(str(path), "r") as f:
        if "resolutions" in f:
            return sorted(int(r) for r in f["resolutions"])
        return [int(f.attrs.get("bin-size"))]


# ---------------------------------------------------------------- writing (demo stand-in and tests)
def _write_group(g, chroms: list[tuple[str, int]], res: int, b1, b2, counts, weight=None):
    names = [c for c, _ in chroms]
    g.attrs.update({"format": "HDF5::Cooler", "format-version": 3, "bin-type": "fixed", "bin-size": res,
                    "storage-mode": "symmetric-upper", "generated-by": "everyome demo", "metadata": "{}"})
    g.create_dataset("chroms/name", data=np.array(names, dtype=f"S{max(len(n) for n in names)}"))
    g.create_dataset("chroms/length", data=np.array([n for _, n in chroms], dtype=np.int32))
    starts, cidx, offs = [], [], [0]
    for i, (_, n) in enumerate(chroms):
        s = np.arange(0, n, res)
        starts.append(s)
        cidx.append(np.full(len(s), i))
        offs.append(offs[-1] + len(s))
    starts = np.concatenate(starts)
    lens = np.repeat([n for _, n in chroms], np.diff(offs))
    enum = h5py.enum_dtype({n: i for i, n in enumerate(names)}, basetype="i4")
    g.create_dataset("bins/chrom", data=np.concatenate(cidx).astype(np.int32), dtype=enum)
    g.create_dataset("bins/start", data=starts.astype(np.int32))
    g.create_dataset("bins/end", data=np.minimum(starts + res, lens).astype(np.int32))
    if weight is not None:
        g.create_dataset("bins/weight", data=weight)
    order = np.lexsort((b2, b1))
    b1, b2, counts = b1[order], b2[order], counts[order]
    g.create_dataset("pixels/bin1_id", data=b1.astype(np.int64))
    g.create_dataset("pixels/bin2_id", data=b2.astype(np.int64))
    g.create_dataset("pixels/count", data=counts.astype(np.int32))
    nb = offs[-1]
    g.create_dataset("indexes/chrom_offset", data=np.array(offs, dtype=np.int64))
    g.create_dataset("indexes/bin1_offset", data=np.searchsorted(b1, np.arange(nb + 1)).astype(np.int64))
    g.attrs.update({"nbins": nb, "nchroms": len(chroms), "nnz": len(b1)})


def coarsen(chroms, res: int, factor: int, b1, b2, counts):
    """Pixels at res × factor from pixels at res (bins numbered per chromosome, as cooler does)."""
    offs = np.concatenate([[0], np.cumsum([-(-n // res) for _, n in chroms])])
    new_offs = np.concatenate([[0], np.cumsum([-(-n // (res * factor)) for _, n in chroms])])
    ci1, ci2 = np.searchsorted(offs, b1, "right") - 1, np.searchsorted(offs, b2, "right") - 1
    n1 = new_offs[ci1] + (b1 - offs[ci1]) // factor
    n2 = new_offs[ci2] + (b2 - offs[ci2]) // factor
    key = n1.astype(np.int64) * (new_offs[-1] + 1) + n2
    u, inv = np.unique(key, return_inverse=True)
    summed = np.bincount(inv, weights=counts)
    return u // (new_offs[-1] + 1), u % (new_offs[-1] + 1), summed


def write_cool(path, chroms, res, b1, b2, counts, balance: bool = True):
    with h5py.File(str(path), "w") as f:
        _write_group(f, chroms, res, b1, b2, counts, ice(b1, b2, counts, sum(-(-n // res) for _, n in chroms)) if balance else None)


def write_mcool(path, chroms, base: int, factors: list[int], b1, b2, counts):
    """A multi-resolution file, as `cooler zoomify --balance` writes it."""
    with h5py.File(str(path), "w") as f:
        f.attrs.update({"format": "HDF5::MCOOL", "format-version": 2})
        for k in factors:
            x1, x2, c = (b1, b2, counts) if k == 1 else coarsen(chroms, base, k, b1, b2, counts)
            res = base * k
            nb = sum(-(-n // res) for _, n in chroms)
            _write_group(f.create_group(f"resolutions/{res}"), chroms, res, x1, x2, c, ice(x1, x2, c, nb))


# ---------------------------------------------------------------- maths
def ice(b1, b2, counts, nbins: int, iters: int = 200, low_share: float = 0.02) -> np.ndarray:
    """Iterative correction (Imakaev et al. 2012), as cooler balance: weights giving every bin the same total.
    The diagonal is ignored and the 2% of bins with the fewest contacts are masked (NaN)."""
    keep = b1 != b2
    b1, b2, c = b1[keep], b2[keep], np.asarray(counts, float)[keep]
    marg = np.bincount(b1, c, nbins) + np.bincount(b2, c, nbins)
    w = np.ones(nbins)
    nz = marg > 0
    cut = np.quantile(marg[nz], low_share) if nz.any() else 0
    w[(marg <= cut) | ~nz] = 0
    for _ in range(iters):
        cc = c * w[b1] * w[b2]
        m = np.bincount(b1, cc, nbins) + np.bincount(b2, cc, nbins)
        mean = m[w > 0].mean() if (w > 0).any() else 1
        step = np.where(w > 0, m / mean, 1)
        w = np.where(w > 0, w / np.where(step > 0, step, 1), 0)
        if np.abs(step[w > 0] - 1).max(initial=0) < 1e-5:
            break
    # Intent: scale so the average balanced bin total is 1 (cooler's convention), and mask unused bins.
    cc = c * w[b1] * w[b2]
    tot = (np.bincount(b1, cc, nbins) + np.bincount(b2, cc, nbins))[w > 0].mean() if (w > 0).any() else 1
    w = w / np.sqrt(tot or 1)
    return np.where(w > 0, w, np.nan)


def observed_expected(m: np.ndarray) -> np.ndarray:
    """Each contact divided by the average at its distance, so distance no longer dominates."""
    oe = np.full_like(m, np.nan)
    for k in range(len(m)):
        v = np.diagonal(m, k)
        mu = np.nanmean(v) if np.isfinite(v).any() else np.nan
        idx = np.arange(len(m) - k)
        oe[idx, idx + k] = oe[idx + k, idx] = v / mu if mu and np.isfinite(mu) else np.nan
    return oe


def eigenvector(m: np.ndarray, phase: np.ndarray | None = None) -> np.ndarray:
    """First eigenvector of the correlation of the observed/expected map (as cooltools eigs-cis). The sign is set so
    it rises with `phase` (GC content) when given: positive = A (open), negative = B (closed)."""
    oe = observed_expected(m)
    good = np.isfinite(oe).sum(axis=1) > len(m) / 2
    x = oe[np.ix_(good, good)]
    x = np.where(np.isfinite(x), x, 1.0)
    x = np.log2(np.clip(x, 1e-3, None))
    c = np.corrcoef(x)
    c = np.where(np.isfinite(c), c, 0)
    vals, vecs = np.linalg.eigh(c)
    e = vecs[:, -1] * np.sqrt(max(vals[-1], 0))
    out = np.full(len(m), np.nan)
    out[good] = e
    if phase is not None:
        ok = np.isfinite(out) & np.isfinite(phase)
        if ok.sum() > 2 and np.corrcoef(out[ok], phase[ok])[0, 1] < 0:
            out = -out
    return out


def insulation(band: np.ndarray, window: int) -> np.ndarray:
    """Diamond insulation (Crane et al. 2015): for each bin, the average contact between the `window` bins before it
    and the `window` bins after it, as log2 of the chromosome's median. Troughs mark boundaries between domains.
    `band` is a band of the map (Cool.band) at least 2 × window wide."""
    n = len(band)
    tot, num = np.zeros(n), np.zeros(n)
    for p in range(1, window + 1):
        for q in range(1, window + 1):
            v = np.full(n, np.nan)
            v[p:] = band[:n - p, p + q]          # the pixel (i - p, i + q) for each bin i
            v[n - q:] = np.nan
            ok = np.isfinite(v)
            tot[ok] += v[ok]
            num[ok] += 1
    s = np.where(num > 0.5 * window * window, tot / np.maximum(num, 1), np.nan)
    s[:window], s[n - window:] = np.nan, np.nan
    pos = s[np.isfinite(s) & (s > 0)]
    med = np.median(pos) if len(pos) else 1.0
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.log2(s / med)


def boundaries(score: np.ndarray, min_strength: float) -> list[tuple[int, float]]:
    """Troughs of the insulation score whose depth (rise to the lower neighbouring peak) is at least min_strength."""
    out, n = [], len(score)
    for i in range(1, n - 1):
        v = score[i]
        if not np.isfinite(v) or not (v < score[i - 1] or not np.isfinite(score[i - 1])) or not (v <= score[i + 1] or not np.isfinite(score[i + 1])):
            continue
        left = np.nanmax(score[max(0, i - 10):i]) if i else np.nan
        right = np.nanmax(score[i + 1:i + 11])
        depth = min(left, right) - v
        if np.isfinite(depth) and depth >= min_strength:
            out.append((i, float(depth)))
    return out
