"""D11.3+D11.4 Bond analytics: YTM, duration, convexity, G-spread, VWAP, liquidity."""


def compute_ytm(
    price: float,
    coupon_rate: float,
    face_value: float,
    years_to_maturity: float,
    frequency: int = 2,
    max_iterations: int = 100,
    tolerance: float = 1e-8,
) -> float:
    """Yield to maturity via Newton-Raphson. Price as % of par (e.g., 98.5)."""
    if years_to_maturity <= 0:
        return 0.0
    if frequency == 0:
        # Zero coupon / T-Bill
        if price <= 0:
            return 0.0
        return (face_value / price) ** (1.0 / years_to_maturity) - 1.0

    coupon = coupon_rate * face_value / frequency
    n_periods = int(round(years_to_maturity * frequency))
    if n_periods < 1:
        n_periods = 1

    # Initial guess
    ytm = coupon_rate if coupon_rate > 0 else 0.05

    for _ in range(max_iterations):
        y = ytm / frequency
        if y <= -1.0:
            y = 0.001

        pv = 0.0
        dpv = 0.0
        for t in range(1, n_periods + 1):
            df = (1 + y) ** (-t)
            pv += coupon * df
            dpv += -t * coupon * df / (1 + y)
        pv += face_value * (1 + y) ** (-n_periods)
        dpv += -n_periods * face_value * (1 + y) ** (-n_periods) / (1 + y)
        dpv /= frequency

        diff = pv - price
        if abs(diff) < tolerance:
            return ytm
        if abs(dpv) < 1e-15:
            break
        ytm -= diff / dpv

    return ytm


def compute_ytw(
    price: float,
    coupon_rate: float,
    face_value: float,
    years_to_maturity: float,
    call_schedule: list[dict] | None = None,
    frequency: int = 2,
) -> float:
    """Yield to worst = min(YTM, all YTC)."""
    ytm = compute_ytm(price, coupon_rate, face_value, years_to_maturity, frequency)
    if not call_schedule:
        return ytm

    worst = ytm
    for call in call_schedule:
        call_years = call.get("years_to_call", 0)
        call_price = call.get("call_price", face_value)
        if call_years > 0:
            ytc = compute_ytm(price, coupon_rate, call_price, call_years, frequency)
            worst = min(worst, ytc)
    return worst


def compute_modified_duration(
    ytm: float,
    coupon_rate: float,
    years_to_maturity: float,
    frequency: int = 2,
) -> float:
    """Modified duration."""
    if years_to_maturity <= 0 or frequency == 0:
        return years_to_maturity

    y = ytm / frequency
    coupon = coupon_rate / frequency
    n = int(round(years_to_maturity * frequency))
    if n < 1:
        return years_to_maturity

    if abs(y) < 1e-10:
        # Approximate for zero yield
        mac = sum(t * coupon for t in range(1, n + 1)) + n * 1.0
        mac /= sum(coupon for _ in range(1, n + 1)) + 1.0
        mac /= frequency
        return mac

    num = 0.0
    denom = 0.0
    for t in range(1, n + 1):
        df = (1 + y) ** (-t)
        cf = coupon if t < n else coupon + 1.0
        num += (t / frequency) * cf * df
        denom += cf * df

    mac_duration = num / denom if denom > 0 else 0.0
    mod_duration = mac_duration / (1 + y)
    return mod_duration


def compute_macaulay_duration(
    ytm: float,
    coupon_rate: float,
    years_to_maturity: float,
    frequency: int = 2,
) -> float:
    """Macaulay duration."""
    if years_to_maturity <= 0 or frequency == 0:
        return years_to_maturity

    y = ytm / frequency
    coupon = coupon_rate / frequency
    n = int(round(years_to_maturity * frequency))
    if n < 1:
        return years_to_maturity

    num = 0.0
    denom = 0.0
    for t in range(1, n + 1):
        df = (1 + y) ** (-t)
        cf = coupon if t < n else coupon + 1.0
        num += (t / frequency) * cf * df
        denom += cf * df

    return num / denom if denom > 0 else 0.0


def compute_convexity(
    ytm: float,
    coupon_rate: float,
    years_to_maturity: float,
    frequency: int = 2,
) -> float:
    """Bond convexity."""
    if years_to_maturity <= 0 or frequency == 0:
        return years_to_maturity**2

    y = ytm / frequency
    coupon = coupon_rate / frequency
    n = int(round(years_to_maturity * frequency))
    if n < 1:
        return 0.0

    num = 0.0
    denom = 0.0
    for t in range(1, n + 1):
        df = (1 + y) ** (-t)
        cf = coupon if t < n else coupon + 1.0
        num += t * (t + 1) * cf * df
        denom += cf * df

    return (num / (denom * frequency**2 * (1 + y) ** 2)) if denom > 0 else 0.0


def compute_g_spread(bond_ytm: float, treasury_yield: float) -> int:
    """G-spread in basis points."""
    return round((bond_ytm - treasury_yield) * 10000)


def compute_vwap(trades: list[dict]) -> float:
    """Volume-weighted average price from trade list. Each dict has 'price' and 'quantity'."""
    total_pq = 0.0
    total_q = 0.0
    for t in trades:
        p = t.get("price", 0)
        q = t.get("quantity", 0)
        if p > 0 and q > 0:
            total_pq += p * q
            total_q += q
    return total_pq / total_q if total_q > 0 else 0.0


def compute_liquidity_score(trade_count: int, volume: float) -> int:
    """Liquidity score 0-100 based on trade activity."""
    if trade_count >= 10 and volume >= 10_000_000:
        return min(100, 80 + min(20, trade_count // 5))
    elif 3 <= trade_count <= 9:
        base = 50 + (trade_count - 3) * 4
        if volume >= 1_000_000:
            base += 5
        return min(79, base)
    elif 1 <= trade_count <= 2:
        return 20 + trade_count * 10
    else:
        return 0
