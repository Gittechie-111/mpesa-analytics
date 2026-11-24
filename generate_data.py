#!/usr/bin/env python3
"""
Synthetic M-Pesa-style transaction data generator.

*** ALL DATA PRODUCED HERE IS SIMULATED. It is not Safaricom data. ***
The fee schedule is illustrative, not an official tariff.

What it builds
--------------
  mpesa.db        SQLite database (tables defined in schema.sql)
  data/*.csv      CSV copy of every table (handy for Power BI / pandas)

Patterns deliberately baked in (so your SQL has something to find):
  * Month-end / early-month spikes (salary period)
  * Daily peaks around morning, lunch and evening
  * Weekday vs weekend differences
  * Heavy-tailed customer activity, plus ~6% near-dormant customers
  * Customers mostly send money to a small circle of favourite contacts
  * Most cash-in/cash-out happens at agents in the customer's own county
  * Injected fraud: rapid "burst" transfers to many new recipients, and
    "takeover" events (very large night-time transfer to a brand-new recipient)
  * A few legitimate large transfers, so naive "big amount = fraud" rules
    produce false positives (realistic!)

Usage
-----
  python3 generate_data.py                      # defaults: 5,000 customers, 150k txns
  python3 generate_data.py --txns 300000 --seed 7
"""
import argparse
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

START = pd.Timestamp("2026-01-01")
END = pd.Timestamp("2026-06-30")
REG_START = pd.Timestamp("2018-01-01")
REG_END = pd.Timestamp("2025-12-31")

COUNTIES = {
    "Nairobi": 0.28, "Kiambu": 0.10, "Mombasa": 0.08, "Nakuru": 0.08,
    "Kisumu": 0.06, "Machakos": 0.06, "Uasin Gishu": 0.05, "Kakamega": 0.05,
    "Meru": 0.04, "Nyeri": 0.04, "Kisii": 0.04, "Kajiado": 0.04, "Embu": 0.04,
}
AGE_GROUPS = {"18-24": 0.22, "25-34": 0.35, "35-44": 0.22, "45-54": 0.12, "55+": 0.09}
TXN_MIX = {
    "send_money": 0.34, "withdraw": 0.18, "buy_goods": 0.20,
    "paybill": 0.12, "airtime": 0.12, "deposit": 0.04,
}
PAYBILL_CATEGORIES = [
    "Electricity", "Water", "Pay TV", "Internet", "School Fees",
    "Insurance", "Loan Repayment", "Rent", "SACCO",
]
TILL_CATEGORIES = [
    "Supermarket", "Restaurant", "Pharmacy", "Fuel Station", "Hardware",
    "Butchery", "Salon", "Electronics", "Transport",
]
# Relative traffic for hours 00..23: peaks ~7-9, 12-14 and 17-20
HOUR_WEIGHTS = [0.3, 0.2, 0.15, 0.15, 0.3, 0.8, 2.0, 4.0, 5.0, 4.5, 4.0, 4.2,
                5.0, 5.0, 4.2, 4.0, 4.5, 5.5, 6.0, 5.5, 4.0, 2.5, 1.2, 0.6]


def norm(p):
    p = np.asarray(p, dtype=float)
    return p / p.sum()


def make_customers(rng, n):
    ids = np.array([f"C{i:05d}" for i in range(1, n + 1)])
    county = rng.choice(list(COUNTIES), n, p=norm(list(COUNTIES.values())))
    age = rng.choice(list(AGE_GROUPS), n, p=norm(list(AGE_GROUPS.values())))
    acct = rng.choice(["individual", "business"], n, p=[0.88, 0.12])
    span = (REG_END - REG_START).days + 1
    reg = REG_START + pd.to_timedelta(rng.integers(0, span, n), unit="D")
    df = pd.DataFrame({
        "customer_id": ids,
        "registration_date": reg.strftime("%Y-%m-%d"),
        "county": county,
        "age_group": age,
        "account_type": acct,
    })
    # Activity level: heavy-tailed, businesses busier, ~6% nearly dormant
    weight = rng.lognormal(0, 0.9, n) * np.where(acct == "business", 3.0, 1.0)
    weight = np.where(rng.random(n) < 0.06, weight * 0.01, weight)
    return df, weight


def make_agents(rng, n):
    ids = np.array([f"A{i:04d}" for i in range(1, n + 1)])
    county = rng.choice(list(COUNTIES), n, p=norm(list(COUNTIES.values())))
    weight = rng.lognormal(0, 0.7, n)
    return pd.DataFrame({"agent_id": ids, "county": county}), weight


def make_merchants(rng):
    rows = []
    k = 1
    for kind, cats, count in (("paybill", PAYBILL_CATEGORIES, 45),
                              ("till", TILL_CATEGORIES, 90)):
        for i in range(count):
            county = "National" if kind == "paybill" else str(
                rng.choice(list(COUNTIES), p=norm(list(COUNTIES.values()))))
            rows.append((f"M{k:04d}", kind, cats[i % len(cats)], county))
            k += 1
    df = pd.DataFrame(rows, columns=["merchant_id", "merchant_kind", "category", "county"])
    # Zipf-like popularity: a few merchants take most of the traffic
    weight = 1.0 / (rng.permutation(len(df)) + 1) ** 0.8
    return df, weight


def send_fee(a):
    bins = [100, 500, 1000, 1500, 2500, 3500, 5000, 7500, 10000, 15000, 20000]
    fees = np.array([0, 7, 13, 23, 33, 53, 57, 78, 90, 100, 105, 108])
    return fees[np.searchsorted(bins, a, side="left")]


def make_fraud(rng, days, nc, cust_weight):
    """Injected fraud events. Returns a DataFrame with ts, cust_idx, amount, cp_idx, pattern."""
    rows = []
    last_day = len(days) - 2  # keep bursts inside the data window

    # Pattern 1: burst - 8-13 transfers to distinct new recipients within ~8 minutes
    for _ in range(25):
        c = int(rng.integers(0, nc))
        start = days[int(rng.integers(0, last_day))] + pd.Timedelta(seconds=int(rng.integers(0, 86400 - 600)))
        recips = rng.choice(nc, int(rng.integers(8, 14)), replace=False)
        recips = recips[recips != c]
        offsets = np.sort(rng.integers(0, 8 * 60, len(recips)))
        for r, off in zip(recips, offsets):
            rows.append((start + pd.Timedelta(seconds=int(off)), c,
                         int(rng.integers(30, 150)) * 100, int(r), "burst"))

    # Pattern 2: takeover - one very large transfer at night to a brand-new recipient
    for _ in range(40):
        c = int(rng.choice(nc, p=norm(cust_weight)))  # an established, active customer
        ts = days[int(rng.integers(0, last_day))] + pd.Timedelta(seconds=int(rng.integers(3600, 16200)))
        r = int(rng.integers(0, nc))
        if r == c:
            r = (r + 1) % nc
        rows.append((ts, c, int(rng.integers(60, 200)) * 1000, r, "takeover"))

    return pd.DataFrame(rows, columns=["ts", "cust_idx", "amount", "cp_idx", "pattern"])


def main():
    ap = argparse.ArgumentParser(description="Generate simulated M-Pesa-style data.")
    ap.add_argument("--customers", type=int, default=5000)
    ap.add_argument("--agents", type=int, default=250)
    ap.add_argument("--txns", type=int, default=150000, help="total rows incl. injected fraud")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    here = Path(__file__).resolve().parent

    customers, cust_w = make_customers(rng, args.customers)
    agents, agent_w = make_agents(rng, args.agents)
    merchants, merch_w = make_merchants(rng)

    cust_ids = customers["customer_id"].to_numpy()
    cust_county = customers["county"].to_numpy()
    acct = customers["account_type"].to_numpy()
    agent_ids = agents["agent_id"].to_numpy()
    agent_county = agents["county"].to_numpy()
    merch_ids = merchants["merchant_id"].to_numpy()
    merch_kind = merchants["merchant_kind"].to_numpy()
    nc, na = len(customers), len(agents)

    days = pd.date_range(START, END, freq="D")
    fraud = make_fraud(rng, days, nc, cust_w)
    n = args.txns - len(fraud)

    # ---- timestamps: day-of-month / weekday / hour-of-day shape -------------
    dom_d, dow_d = days.day.to_numpy(), days.dayofweek.to_numpy()
    dw = np.ones(len(days))
    dw[dom_d >= 25] *= 2.0      # month-end salary spike
    dw[dom_d <= 2] *= 1.5       # early-month spillover
    dw[dow_d == 5] *= 1.1       # Saturday
    dw[dow_d == 6] *= 0.8       # Sunday
    day_idx = rng.choice(len(days), n, p=norm(dw))
    hour = rng.choice(24, n, p=norm(HOUR_WEIGHTS))
    secs = hour * 3600 + rng.integers(0, 60, n) * 60 + rng.integers(0, 60, n)
    ts = days.to_numpy()[day_idx] + secs.astype("timedelta64[s]")
    dom = dom_d[day_idx]
    month_end = (dom >= 25) | (dom <= 2)

    # ---- who, what -----------------------------------------------------------
    cust_idx = rng.choice(nc, n, p=norm(cust_w))
    ttype = rng.choice(list(TXN_MIX), n, p=norm(list(TXN_MIX.values())))

    # ---- amounts -------------------------------------------------------------
    amount = np.zeros(n)
    params = {"send_money": (800, 1.0), "withdraw": (2000, 0.9), "buy_goods": (350, 0.9),
              "paybill": (2500, 1.0), "deposit": (3000, 1.0)}
    for t, (median, sigma) in params.items():
        m = ttype == t
        amount[m] = rng.lognormal(np.log(median), sigma, m.sum())
    m = ttype == "airtime"
    amount[m] = rng.choice([10, 20, 50, 100, 200, 500, 1000], m.sum(),
                           p=[0.08, 0.12, 0.25, 0.30, 0.12, 0.10, 0.03])
    amount[(acct[cust_idx] == "business") & (ttype != "airtime")] *= 2.0
    amount[month_end & np.isin(ttype, ["send_money", "withdraw", "paybill"])] *= 1.3
    # A handful of legitimate large transfers (rent, supplier payments, ...)
    sm = np.where(ttype == "send_money")[0]
    big = rng.choice(sm, int(len(sm) * 0.003), replace=False)
    amount[big] = rng.integers(40, 150, big.size) * 1000
    amount = np.clip(np.round(amount), 10, 250000).astype(int)
    amount = np.where(ttype == "withdraw", np.maximum(np.round(amount / 50) * 50, 50), amount).astype(int)

    status = rng.choice(["SUCCESS", "FAILED", "REVERSED"], n, p=[0.975, 0.02, 0.005])

    # ---- counterparties --------------------------------------------------------
    cp_type = np.full(n, None, dtype=object)
    cp_id = np.full(n, None, dtype=object)

    # send_money: 70% to one of the customer's 6 favourite contacts
    s = np.where(ttype == "send_money")[0]
    favourites = rng.integers(0, nc, (nc, 6))
    fav = favourites[cust_idx[s], rng.integers(0, 6, s.size)]
    rand_rec = rng.integers(0, nc, s.size)
    rec = np.where(rng.random(s.size) < 0.7, fav, rand_rec)
    selfsend = rec == cust_idx[s]
    rec[selfsend] = (rec[selfsend] + 1) % nc
    cp_id[s], cp_type[s] = cust_ids[rec], "customer"

    # withdraw / deposit: 85% at an agent in the customer's own county
    cash = np.where(np.isin(ttype, ["withdraw", "deposit"]))[0]
    for county in COUNTIES:
        sel = cash[cust_county[cust_idx[cash]] == county]
        pool = np.where(agent_county == county)[0]
        if sel.size == 0:
            continue
        if pool.size == 0:
            pool = np.arange(na)
        local = rng.choice(pool, sel.size, p=norm(agent_w[pool]))
        anywhere = rng.choice(na, sel.size, p=norm(agent_w))
        pick = np.where(rng.random(sel.size) < 0.85, local, anywhere)
        cp_id[sel], cp_type[sel] = agent_ids[pick], "agent"

    # paybill -> billers, buy_goods -> tills (popularity is heavy-tailed)
    for t, kind in (("paybill", "paybill"), ("buy_goods", "till")):
        sel = np.where(ttype == t)[0]
        pool = np.where(merch_kind == kind)[0]
        j = rng.choice(pool, sel.size, p=norm(merch_w[pool]))
        cp_id[sel], cp_type[sel] = merch_ids[j], "merchant"
    # airtime stays NULL / NULL

    base = pd.DataFrame({
        "ts": pd.to_datetime(ts), "customer_id": cust_ids[cust_idx], "txn_type": ttype,
        "amount": amount, "status": status,
        "counterparty_type": cp_type, "counterparty_id": cp_id, "pattern": None,
    })

    fr = pd.DataFrame({
        "ts": pd.to_datetime(fraud["ts"]), "customer_id": cust_ids[fraud["cust_idx"].to_numpy()],
        "txn_type": "send_money", "amount": fraud["amount"].to_numpy(), "status": "SUCCESS",
        "counterparty_type": "customer", "counterparty_id": cust_ids[fraud["cp_idx"].to_numpy()],
        "pattern": fraud["pattern"].to_numpy(),
    })

    tx = pd.concat([base, fr], ignore_index=True).sort_values("ts", kind="stable").reset_index(drop=True)
    tx["txn_id"] = [f"TX{i:07d}" for i in range(1, len(tx) + 1)]
    tx["txn_ts"] = tx["ts"].dt.strftime("%Y-%m-%d %H:%M:%S")

    fee = np.zeros(len(tx), dtype=int)
    is_send = (tx["txn_type"] == "send_money").to_numpy()
    is_wd = (tx["txn_type"] == "withdraw").to_numpy()
    amt = tx["amount"].to_numpy()
    fee[is_send] = send_fee(amt[is_send])
    fee[is_wd] = np.clip(np.round(amt[is_wd] * 0.01), 10, 108).astype(int)
    fee[(tx["status"] != "SUCCESS").to_numpy()] = 0
    tx["fee"] = fee

    truth = tx.loc[tx["pattern"].notna(), ["txn_id", "pattern"]]
    tx = tx[["txn_id", "txn_ts", "customer_id", "txn_type", "amount", "fee",
             "status", "counterparty_type", "counterparty_id"]]

    # ---- write SQLite + CSV --------------------------------------------------------
    db_path = here / "mpesa.db"
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    con.executescript((here / "schema.sql").read_text())
    tables = {"customers": customers, "agents": agents, "merchants": merchants,
              "transactions": tx, "_fraud_truth": truth}
    (here / "data").mkdir(exist_ok=True)
    for name, df in tables.items():
        df.to_sql(name, con, if_exists="append", index=False)
        df.to_csv(here / "data" / f"{name.lstrip('_')}.csv", index=False)
    con.commit()
    con.close()

    print(f"Wrote {db_path}")
    for name, df in tables.items():
        print(f"  {name:<14}{len(df):>9,} rows")
    print(f"Date range: {tx['txn_ts'].min()}  ->  {tx['txn_ts'].max()}")


if __name__ == "__main__":
    main()
