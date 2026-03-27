"""Yield Curve Construction & Analytics Engine.

Provides curve fitting (Nelson-Siegel), interpolation, spread analytics,
and scenario-shift functions. All functions are pure computation — no
database access. They operate on lists of tenors and rates.
"""

from __future__ import annotations

import math


# ---------------------------------------------------------------------------
# Standard tenors (years)
# ---------------------------------------------------------------------------

STANDARD_TENORS: list[float] = [
    0.083,  # 1 month
    0.25,   # 3 month
    0.5,    # 6 month
    1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 20.0, 30.0,
]


# ---------------------------------------------------------------------------
# Nelson-Siegel model
# ---------------------------------------------------------------------------

def _nelson_siegel_rate(t: float, beta0: float, beta1: float, beta2: float, tau: float) -> float:
    """Evaluate the Nelson-Siegel model at tenor t."""
    if t <= 0 or tau <= 0:
        return beta0 + beta1
    x = t / tau
    exp_x = math.exp(-x)
    factor = (1 - exp_x) / x
    return beta0 + beta1 * factor + beta2 * (factor - exp_x)


def nelson_siegel_fit(
    tenors: list[float],
    rates: list[float],
    *,
    tau_range: tuple[float, float] = (0.5, 5.0),
    tau_steps: int = 20,
) -> dict:
    """Fit Nelson-Siegel parameters to observed yields.

    Uses grid search over tau + closed-form OLS for betas.
    No scipy dependency.

    Parameters
    ----------
    tenors : list[float]
        Maturities in years.
    rates : list[float]
        Observed par/zero yields (decimal, e.g. 0.045 for 4.5%).
    tau_range : tuple
        (min_tau, max_tau) for grid search.
    tau_steps : int
        Number of tau values to try.

    Returns
    -------
    dict
        {beta0, beta1, beta2, tau, fit_error, fitted_rates: {tenor: rate}}
    """
    if len(tenors) < 3 or len(tenors) != len(rates):
        raise ValueError("Need at least 3 tenor-rate pairs of equal length")

    best_params: dict | None = None
    best_rmse = float("inf")

    tau_min, tau_max = tau_range
    for step in range(tau_steps + 1):
        tau = tau_min + (tau_max - tau_min) * step / tau_steps
        if tau <= 0:
            continue

        # Build design matrix for OLS: y = X @ [b0, b1, b2]
        n = len(tenors)
        X = []
        for t in tenors:
            if t <= 0:
                X.append([1.0, 1.0, 0.0])
            else:
                x = t / tau
                exp_x = math.exp(-x)
                f = (1 - exp_x) / x
                X.append([1.0, f, f - exp_x])

        # OLS via normal equations: (X'X)^-1 X'y
        # For 3x3, solve directly
        betas = _ols_3x3(X, rates)
        if betas is None:
            continue
        b0, b1, b2 = betas

        # Compute RMSE
        sse = 0.0
        for i, t in enumerate(tenors):
            fitted = _nelson_siegel_rate(t, b0, b1, b2, tau)
            sse += (rates[i] - fitted) ** 2
        rmse = math.sqrt(sse / n)

        if rmse < best_rmse:
            best_rmse = rmse
            best_params = {"beta0": b0, "beta1": b1, "beta2": b2, "tau": tau}

    if best_params is None:
        raise ValueError("Nelson-Siegel fit failed to converge")

    # Build fitted rates at standard tenors + input tenors
    fitted_rates = {}
    for t in sorted(set(STANDARD_TENORS) | set(tenors)):
        fitted_rates[t] = round(
            _nelson_siegel_rate(
                t, best_params["beta0"], best_params["beta1"],
                best_params["beta2"], best_params["tau"]
            ),
            8,
        )

    return {
        "beta0": round(best_params["beta0"], 6),
        "beta1": round(best_params["beta1"], 6),
        "beta2": round(best_params["beta2"], 6),
        "tau": round(best_params["tau"], 6),
        "fit_error": round(best_rmse, 8),
        "fitted_rates": fitted_rates,
    }


def _ols_3x3(X: list[list[float]], y: list[float]) -> list[float] | None:
    """Solve 3-parameter OLS via normal equations (X'X)^-1 X'y."""
    n = len(y)
    # X'X (3x3)
    xtx = [[0.0] * 3 for _ in range(3)]
    xty = [0.0] * 3
    for i in range(n):
        for j in range(3):
            xty[j] += X[i][j] * y[i]
            for k in range(3):
                xtx[j][k] += X[i][j] * X[i][k]

    # Invert 3x3 via cofactors
    a = xtx
    det = (
        a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1])
        - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
        + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0])
    )
    if abs(det) < 1e-15:
        return None

    inv = [[0.0] * 3 for _ in range(3)]
    inv[0][0] = (a[1][1] * a[2][2] - a[1][2] * a[2][1]) / det
    inv[0][1] = (a[0][2] * a[2][1] - a[0][1] * a[2][2]) / det
    inv[0][2] = (a[0][1] * a[1][2] - a[0][2] * a[1][1]) / det
    inv[1][0] = (a[1][2] * a[2][0] - a[1][0] * a[2][2]) / det
    inv[1][1] = (a[0][0] * a[2][2] - a[0][2] * a[2][0]) / det
    inv[1][2] = (a[0][2] * a[1][0] - a[0][0] * a[1][2]) / det
    inv[2][0] = (a[1][0] * a[2][1] - a[1][1] * a[2][0]) / det
    inv[2][1] = (a[0][1] * a[2][0] - a[0][0] * a[2][1]) / det
    inv[2][2] = (a[0][0] * a[1][1] - a[0][1] * a[1][0]) / det

    result = [0.0] * 3
    for j in range(3):
        for k in range(3):
            result[j] += inv[j][k] * xty[k]
    return result


# ---------------------------------------------------------------------------
# Interpolation
# ---------------------------------------------------------------------------

def interpolate_rate(
    tenors: list[float],
    rates: list[float],
    target_tenor: float,
    method: str = "LINEAR",
) -> float:
    """Interpolate a rate at an arbitrary tenor.

    Parameters
    ----------
    tenors : sorted list of tenors
    rates : matching rates
    target_tenor : the tenor to interpolate at
    method : "LINEAR" or "CUBIC_SPLINE"

    Returns
    -------
    float
        Interpolated rate.
    """
    if not tenors or len(tenors) != len(rates):
        raise ValueError("tenors and rates must be non-empty and equal length")

    if target_tenor <= tenors[0]:
        return rates[0]
    if target_tenor >= tenors[-1]:
        return rates[-1]

    if method == "CUBIC_SPLINE" and len(tenors) >= 4:
        return _cubic_spline_interp(tenors, rates, target_tenor)

    # Default: linear interpolation
    for i in range(len(tenors) - 1):
        if tenors[i] <= target_tenor <= tenors[i + 1]:
            w = (target_tenor - tenors[i]) / (tenors[i + 1] - tenors[i])
            return rates[i] + w * (rates[i + 1] - rates[i])

    return rates[-1]


def _cubic_spline_interp(tenors: list[float], rates: list[float], t: float) -> float:
    """Natural cubic spline interpolation (pure Python)."""
    n = len(tenors)
    h = [tenors[i + 1] - tenors[i] for i in range(n - 1)]
    alpha = [0.0] * n
    for i in range(1, n - 1):
        alpha[i] = (3 / h[i] * (rates[i + 1] - rates[i]) -
                     3 / h[i - 1] * (rates[i] - rates[i - 1]))

    # Solve tridiagonal system for c coefficients
    l = [0.0] * n
    mu = [0.0] * n
    z = [0.0] * n
    l[0] = 1.0
    for i in range(1, n - 1):
        l[i] = 2 * (tenors[i + 1] - tenors[i - 1]) - h[i - 1] * mu[i - 1]
        mu[i] = h[i] / l[i]
        z[i] = (alpha[i] - h[i - 1] * z[i - 1]) / l[i]
    l[n - 1] = 1.0

    c = [0.0] * n
    b = [0.0] * (n - 1)
    d = [0.0] * (n - 1)
    for j in range(n - 2, -1, -1):
        c[j] = z[j] - mu[j] * c[j + 1]
        b[j] = (rates[j + 1] - rates[j]) / h[j] - h[j] * (c[j + 1] + 2 * c[j]) / 3
        d[j] = (c[j + 1] - c[j]) / (3 * h[j])

    # Find interval
    idx = 0
    for i in range(n - 1):
        if tenors[i] <= t <= tenors[i + 1]:
            idx = i
            break

    dx = t - tenors[idx]
    return rates[idx] + b[idx] * dx + c[idx] * dx**2 + d[idx] * dx**3


# ---------------------------------------------------------------------------
# Curve Analytics
# ---------------------------------------------------------------------------

def compute_curve_analytics(
    tenors: list[float],
    rates: list[float],
    real_tenors: list[float] | None = None,
    real_rates: list[float] | None = None,
) -> dict:
    """Compute yield curve shape metrics.

    Returns dict with:
      spread_2s10s, spread_3m10y, steepness, curvature,
      breakeven_5y, breakeven_10y, is_inverted
    """
    tenor_rate = dict(zip(tenors, rates))

    # Spreads
    rate_2y = _lookup_or_interp(tenors, rates, 2.0)
    rate_10y = _lookup_or_interp(tenors, rates, 10.0)
    rate_3m = _lookup_or_interp(tenors, rates, 0.25)
    rate_5y = _lookup_or_interp(tenors, rates, 5.0)
    rate_30y = _lookup_or_interp(tenors, rates, 30.0)

    spread_2s10s = _safe_spread(rate_10y, rate_2y)
    spread_3m10y = _safe_spread(rate_10y, rate_3m)

    # Steepness: linear regression slope across all tenors
    steepness = _compute_slope(tenors, rates) if len(tenors) >= 2 else None

    # Curvature: butterfly = 2 * 5Y - 2Y - 10Y
    curvature = None
    if rate_2y is not None and rate_5y is not None and rate_10y is not None:
        curvature = round(2 * rate_5y - rate_2y - rate_10y, 4)

    # Inversion: any key spread negative?
    is_inverted = False
    if spread_2s10s is not None and spread_2s10s < 0:
        is_inverted = True
    if spread_3m10y is not None and spread_3m10y < 0:
        is_inverted = True

    # Breakeven inflation
    breakeven_5y = None
    breakeven_10y = None
    if real_tenors and real_rates:
        nominal_5y = _lookup_or_interp(tenors, rates, 5.0)
        real_5y = _lookup_or_interp(real_tenors, real_rates, 5.0)
        if nominal_5y is not None and real_5y is not None:
            breakeven_5y = round(nominal_5y - real_5y, 4)

        nominal_10y = _lookup_or_interp(tenors, rates, 10.0)
        real_10y = _lookup_or_interp(real_tenors, real_rates, 10.0)
        if nominal_10y is not None and real_10y is not None:
            breakeven_10y = round(nominal_10y - real_10y, 4)

    return {
        "spread_2s10s": spread_2s10s,
        "spread_3m10y": spread_3m10y,
        "steepness": steepness,
        "curvature": curvature,
        "breakeven_5y": breakeven_5y,
        "breakeven_10y": breakeven_10y,
        "is_inverted": is_inverted,
    }


def _lookup_or_interp(tenors: list[float], rates: list[float], target: float) -> float | None:
    """Look up a rate by tenor, interpolating if necessary."""
    if not tenors:
        return None
    try:
        return interpolate_rate(tenors, rates, target)
    except (ValueError, IndexError):
        return None


def _safe_spread(long_rate: float | None, short_rate: float | None) -> float | None:
    if long_rate is None or short_rate is None:
        return None
    return round(long_rate - short_rate, 4)


def _compute_slope(tenors: list[float], rates: list[float]) -> float | None:
    """Simple OLS slope of rates on tenors."""
    n = len(tenors)
    if n < 2:
        return None
    mean_t = sum(tenors) / n
    mean_r = sum(rates) / n
    num = sum((tenors[i] - mean_t) * (rates[i] - mean_r) for i in range(n))
    den = sum((tenors[i] - mean_t) ** 2 for i in range(n))
    if abs(den) < 1e-15:
        return None
    return round(num / den, 4)


# ---------------------------------------------------------------------------
# Curve Scenario Shifts
# ---------------------------------------------------------------------------

def shift_curve(
    tenors: list[float],
    rates: list[float],
    shift_type: str,
    shift_bps: float = 100.0,
    custom_shifts: dict[float, float] | None = None,
) -> list[dict]:
    """Apply a scenario shift to a yield curve.

    Parameters
    ----------
    tenors, rates : the original curve
    shift_type : PARALLEL, STEEPENER, FLATTENER, CUSTOM
    shift_bps : magnitude in basis points (for non-custom shifts)
    custom_shifts : {tenor: bps} for CUSTOM shifts

    Returns
    -------
    list[dict]
        [{tenor_years, original_rate, shifted_rate, shift_bps}]
    """
    result = []
    for i, t in enumerate(tenors):
        if shift_type == "PARALLEL":
            delta = shift_bps / 10000
        elif shift_type == "STEEPENER":
            # Short end down, long end up, pivot at 5Y
            factor = (t - 5.0) / 25.0
            delta = factor * shift_bps / 10000
        elif shift_type == "FLATTENER":
            factor = (5.0 - t) / 25.0
            delta = factor * shift_bps / 10000
        elif shift_type == "CUSTOM" and custom_shifts:
            delta = custom_shifts.get(t, 0.0) / 10000
        else:
            delta = 0.0

        result.append({
            "tenor_years": t,
            "original_rate": rates[i],
            "shifted_rate": round(rates[i] + delta, 6),
            "shift_bps": round(delta * 10000, 2),
        })
    return result


# ---------------------------------------------------------------------------
# Breakeven Inflation
# ---------------------------------------------------------------------------

def compute_breakeven_inflation(
    nominal_tenors: list[float],
    nominal_rates: list[float],
    real_tenors: list[float],
    real_rates: list[float],
) -> dict[float, float]:
    """Compute breakeven inflation rates at each real tenor.

    Breakeven = nominal rate - real rate at matching tenor.
    """
    result = {}
    for t, real_r in zip(real_tenors, real_rates):
        nominal_r = _lookup_or_interp(nominal_tenors, nominal_rates, t)
        if nominal_r is not None:
            result[t] = round(nominal_r - real_r, 6)
    return result


# ---------------------------------------------------------------------------
# D11 FI Supplement: Additional spread & curve analytics
# ---------------------------------------------------------------------------


def compute_butterfly_spread(rate_2y: float, rate_5y: float, rate_10y: float) -> float:
    """Compute butterfly spread: 2 * 5Y - 2Y - 10Y."""
    return 2.0 * rate_5y - rate_2y - rate_10y


def compute_spread_5s30s(rate_5y: float, rate_30y: float) -> float:
    """Compute 5s30s spread."""
    return rate_30y - rate_5y


def nelson_siegel_svensson_evaluate(t: float, beta0: float, beta1: float, beta2: float,
                                     beta3: float, lambda1: float, lambda2: float) -> float:
    """Evaluate the Nelson-Siegel-Svensson model at tenor t."""
    if t <= 0:
        return beta0 + beta1

    exp1 = math.exp(-t / lambda1) if lambda1 > 0 else 0.0
    exp2 = math.exp(-t / lambda2) if lambda2 > 0 else 0.0

    term1 = beta0
    term2 = beta1 * ((1 - exp1) / (t / lambda1)) if lambda1 > 0 else 0.0
    term3 = beta2 * ((1 - exp1) / (t / lambda1) - exp1) if lambda1 > 0 else 0.0
    term4 = beta3 * ((1 - exp2) / (t / lambda2) - exp2) if lambda2 > 0 else 0.0

    return term1 + term2 + term3 + term4


def nelson_siegel_svensson_fit(tenors: list[float], rates: list[float]) -> dict:
    """Fit the 6-parameter Nelson-Siegel-Svensson model via grid search + OLS.

    Returns dict with beta0, beta1, beta2, beta3, lambda1, lambda2, fit_error.
    """
    if len(tenors) < 4:
        return {"beta0": 0, "beta1": 0, "beta2": 0, "beta3": 0, "lambda1": 1.0, "lambda2": 5.0, "fit_error": float("inf")}

    best_params = None
    best_error = float("inf")

    # Grid search over lambda1 and lambda2
    lambda1_grid = [0.5, 1.0, 1.5, 2.0, 3.0, 5.0]
    lambda2_grid = [1.0, 2.0, 3.0, 5.0, 8.0, 10.0]

    for lam1 in lambda1_grid:
        for lam2 in lambda2_grid:
            if lam2 <= lam1:
                continue  # lambda2 should be larger than lambda1

            # Build design matrix for OLS: y = X @ [b0, b1, b2, b3]
            n = len(tenors)
            X = []
            for t in tenors:
                if t <= 0:
                    X.append([1.0, 1.0, 0.0, 0.0])
                    continue
                exp1 = math.exp(-t / lam1)
                exp2 = math.exp(-t / lam2)
                x1 = 1.0
                x2 = (1 - exp1) / (t / lam1)
                x3 = x2 - exp1
                x4 = (1 - exp2) / (t / lam2) - exp2
                X.append([x1, x2, x3, x4])

            # OLS: beta = (X'X)^-1 X'y using simple implementation
            # Compute X'X (4x4) and X'y (4x1)
            XtX = [[0.0]*4 for _ in range(4)]
            Xty = [0.0]*4
            for i in range(n):
                for j in range(4):
                    Xty[j] += X[i][j] * rates[i]
                    for k in range(4):
                        XtX[j][k] += X[i][j] * X[i][k]

            # Solve 4x4 system via Gaussian elimination
            A = [row[:] + [Xty[i]] for i, row in enumerate(XtX)]
            size = 4
            try:
                for col in range(size):
                    max_row = col
                    for row in range(col + 1, size):
                        if abs(A[row][col]) > abs(A[max_row][col]):
                            max_row = row
                    A[col], A[max_row] = A[max_row], A[col]
                    if abs(A[col][col]) < 1e-12:
                        raise ValueError("Singular")
                    for row in range(col + 1, size):
                        factor = A[row][col] / A[col][col]
                        for j in range(col, size + 1):
                            A[row][j] -= factor * A[col][j]

                betas = [0.0] * size
                for i in range(size - 1, -1, -1):
                    betas[i] = A[i][size]
                    for j in range(i + 1, size):
                        betas[i] -= A[i][j] * betas[j]
                    betas[i] /= A[i][i]
            except (ValueError, ZeroDivisionError):
                continue

            # Compute RMSE
            sse = 0.0
            for i, t in enumerate(tenors):
                fitted = nelson_siegel_svensson_evaluate(t, betas[0], betas[1], betas[2], betas[3], lam1, lam2)
                sse += (fitted - rates[i]) ** 2
            rmse = math.sqrt(sse / n)

            if rmse < best_error:
                best_error = rmse
                best_params = {
                    "beta0": round(betas[0], 6),
                    "beta1": round(betas[1], 6),
                    "beta2": round(betas[2], 6),
                    "beta3": round(betas[3], 6),
                    "lambda1": lam1,
                    "lambda2": lam2,
                    "fit_error": round(rmse, 8),
                }

    return best_params or {"beta0": 0, "beta1": 0, "beta2": 0, "beta3": 0, "lambda1": 1.0, "lambda2": 5.0, "fit_error": float("inf")}
