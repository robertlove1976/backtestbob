#!/usr/bin/env python3
import logging
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from functools import lru_cache

import pandas as pd
import duckdb
import requests
from sqlalchemy import create_engine, text

from dash import Dash, html, dcc, dash_table, Input, Output, State
import dash_bootstrap_components as dbc

# ── CONFIG & DB SETUP ─────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DB_FILE      = "stocks.db"
DUCKDB_FILE  = "analytics.duckdb"
DATA_TABLE   = "monthly_performance"
TXN_TABLE    = "transactions"

sqlite_engine = create_engine(f"sqlite:///{DB_FILE}", echo=False)

# ← your FinancialModelingPrep API key
FMP_API_KEY = "3LUYNinfxHPsRtVoxbIz4iaR0tXjpr8k"

def sql_exec(stmt, params=None):
    with sqlite_engine.begin() as conn:
        conn.execute(text(stmt), params or {})

# ── DATE HELPERS ───────────────────────────────────────────────────────────
def effective_date(sel_iso: str) -> str:
    """Greatest date ≤ sel_iso in DATA_TABLE, or the minimum date if none."""
    with duckdb.connect(DUCKDB_FILE) as con:
        q = con.execute(
            f"SELECT MAX(date) FROM {DATA_TABLE} WHERE date <= '{sel_iso}'"
        ).fetchone()[0]
        if q:
            return q
        return con.execute(f"SELECT MIN(date) FROM {DATA_TABLE}").fetchone()[0]

@lru_cache(maxsize=20)
def df_as_of(date_iso: str) -> pd.DataFrame:
    """
    For each ticker, grab the single row with the largest date <= date_iso.
    Guarantees no row with date > date_iso ever makes it through.
    """
    sql = f"""
        SELECT * FROM (
          SELECT *,
            ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY date DESC) AS rn
          FROM {DATA_TABLE}
          WHERE date <= '{date_iso}'
        )
        WHERE rn = 1
    """
    with duckdb.connect(DUCKDB_FILE) as con:
        df = con.execute(sql).df()
    df.columns = [c.lower() for c in df.columns]
    df["date"] = pd.to_datetime(df["date"]).dt.date
    # sanity check: ensure no lookahead
    assert df["date"].max() <= date.fromisoformat(date_iso), (
        f"Lookahead detected: loaded date {df['date'].max()} > backtest date {date_iso}"
    )
    return df

# ── FMP HISTORICAL PRICE LOOKUP w/ fallback ────────────────────────────────
def fetch_price_on_or_before(ticker: str, dt_iso: str) -> float:
    """
    Fetch ticker’s closing price on dt_iso; if missing (weekend/holiday),
    step back one day at a time up to 10 days.
    """
    dt = date.fromisoformat(dt_iso)
    for _ in range(10):
        try:
            resp = requests.get(
                f"https://financialmodelingprep.com/api/v3/historical-price-full/{ticker}",
                params={"from": dt.isoformat(), "to": dt.isoformat(), "apikey": FMP_API_KEY},
                timeout=5
            )
            resp.raise_for_status()
            hist = resp.json().get("historical", [])
            if hist:
                return float(hist[0]["close"])
        except Exception:
            pass
        dt -= timedelta(days=1)
    return 0.0

# ── FMP COMPANY NAME LOOKUP ────────────────────────────────────────────────
@lru_cache(maxsize=100)
def get_company_name(ticker: str) -> str:
    """Fetch the company name for a given ticker using FMP profile endpoint."""
    try:
        resp = requests.get(
            f"https://financialmodelingprep.com/api/v3/profile/{ticker}",
            params={"apikey": FMP_API_KEY},
            timeout=5
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list) and data:
            return data[0].get("companyName", "")
    except Exception:
        logger.warning(f"Could not fetch company name for {ticker}")
    return ""

# ── TOP‑N PICKERS (as-of snapshots) ────────────────────────────────────────
def pick_dcf(date_iso: str, n: int):
    df  = df_as_of(date_iso)
    top = df.sort_values("dcf_percentage", ascending=False).head(n)
    return top[["ticker","price"]].to_dict("records")

def pick_magic(date_iso: str, n: int):
    df  = df_as_of(date_iso)
    top = df.sort_values("magicformulavalue", ascending=False).head(n)
    return top[["ticker","price"]].to_dict("records")

def pick_acq(date_iso: str, n: int):
    df  = df_as_of(date_iso)
    top = df.sort_values("acquirersmultiple", ascending=True).head(n)
    return top[["ticker","price"]].to_dict("records")

def pick_comp(date_iso: str, n: int):
    df  = df_as_of(date_iso)
    top = df.sort_values("finalcompositescore", ascending=True).head(n)
    return top[["ticker","price"]].to_dict("records")

formula_map = {
    "DCF":       pick_dcf,
    "Magic":     pick_magic,
    "Acquirers": pick_acq,
    "Composite": pick_comp,
}

# ── DASH APP ───────────────────────────────────────────────────────────────
app = Dash(__name__, external_stylesheets=[dbc.themes.FLATLY], suppress_callback_exceptions=True)
app.title = "📈 Batch Backtester"

app.layout = dbc.Container(fluid=True, children=[
    html.H2("Batch Backtester"),

    dbc.Row([
        dbc.Col(dcc.RadioItems(
            id="formula",
            options=[{"label": k, "value": k} for k in formula_map],
            value="Acquirers", inline=True
        ), width=3),
        dbc.Col(dcc.Input(id="dates", placeholder="YYYY-MM-DD,YYYY-MM-DD,…"), width=5),
        dbc.Col(dcc.Dropdown(
            id="months",
            options=[{"label": f"{m}m", "value": m} for m in (1,3,6,12,24,36,48,60)],
            value=12, clearable=False
        ), width=2),
        dbc.Col(dbc.Input(id="nstocks", type="number", value=10, placeholder="No. of stocks"), width=2),
    ], className="my-2"),

    dbc.Row([
        dbc.Col(dbc.Input(id="initial-invest", type="number", value=1000, placeholder="Initial investment"), width=4),
        dbc.Col(dbc.Button("Run Batch", id="run-batch", color="primary"), width=2),
    ], className="mb-4"),

    html.H4("Batch Summary"),
    dash_table.DataTable(id="batch-summary-table", style_table={"overflowX":"auto"}, row_selectable="single"),
    dcc.Store(id="batch-details", data={}),

    html.Div(id="summary-report", className="mt-4"),

    html.H4("Drill‑down Trades"),
    html.Div(id="batch-drilldown", className="mt-2"),
])

@app.callback(
    Output("batch-summary-table","columns"),
    Output("batch-summary-table","data"),
    Output("summary-report","children"),
    Output("batch-details","data"),
    Input("run-batch","n_clicks"),
    State("formula","value"),
    State("dates","value"),
    State("months","value"),
    State("nstocks","value"),
    State("initial-invest","value"),
    prevent_initial_call=True,
)
def run_batch(_, formula, dates_str, months, nstocks, init_inv):
    dates    = [d.strip() for d in (dates_str or "").split(",") if d.strip()]
    batch_id = int(datetime.now().timestamp())
    tag_root = f"Batch_{batch_id}"

    # clear old trades for this batch
    sql_exec(f"DELETE FROM {TXN_TABLE} WHERE portfolio = :p", {"p": tag_root})

    summary = []
    details = {}
    current_capital = init_inv

    # chart data
    chart_x = []
    chart_y = []

    # start chart at first buy date
    start_point = effective_date(dates[0]) if dates else date.today().isoformat()
    chart_x.append(start_point)
    chart_y.append(current_capital)

    for dt0 in dates:
        dt    = effective_date(dt0)
        picks = formula_map[formula](dt, nstocks)
        alloc = current_capital / len(picks) if picks else 0.0

        # record buys
        for r in picks:
            price0 = r["price"]
            shares = alloc / price0 if price0 else 0.0
            tx = {
                "portfolio": tag_root,
                "date":      dt,
                "ticker":    r["ticker"],
                "type":      "buy",
                "shares":    shares,
                "price":     price0,
                "pl":        0.0,
                "invest_amt": round(shares * price0, 2),
                "tag":       f"{tag_root}_{dt}"
            }
            sql_exec(f"""
                INSERT INTO {TXN_TABLE}
                  (portfolio,date,ticker,type,shares,price,pl,invest_amt,tag)
                VALUES
                  (:portfolio,:date,:ticker,:type,
                   :shares,:price,:pl,:invest_amt,:tag)
            """, tx)

        # determine exit and clamp to today
        exit_dt = date.fromisoformat(dt) + relativedelta(months=months)
        if exit_dt > date.today():
            exit_dt = date.today()
        exit_iso = exit_dt.isoformat()

        block = []
        for r in picks:
            tkr    = r["ticker"]
            p0     = r["price"]
            p1     = fetch_price_on_or_before(tkr, exit_iso)
            shares = alloc / p0 if p0 else 0.0
            val1   = shares * p1
            ret_p  = ((p1 / p0 - 1) * 100) if p0 else 0.0
            block.append({
                "ticker":      tkr,
                "name":        get_company_name(tkr),
                "start_price": round(p0,2),
                "end_price":   round(p1,2),
                "shares":      round(shares,5),
                "value_end":   round(val1,2),
                "return_%":    round(ret_p,2),
            })

        details[f"{tag_root}_{dt}"] = block

        # update capital
        nav_end = sum(x["value_end"] for x in block)
        ret_pct = ((nav_end - current_capital) / current_capital * 100) if current_capital else 0.0
        summary.append({
            "tag":           f"{tag_root}_{dt}",
            "buy_date":      dt,
            "exit_date":     exit_iso,
            "start_capital": round(current_capital,2),
            "end_capital":   round(nav_end,2),
            "return_%":      round(ret_pct,2),
        })

        chart_x.append(exit_iso)
        chart_y.append(round(nav_end,2))
        current_capital = nav_end

    # build summary table
    df_sum = pd.DataFrame(summary).sort_values("exit_date")
    cols   = [{"name":c, "id":c} for c in df_sum.columns]

    # compound‐growth chart
    chart = dcc.Graph(figure={
        "data":[{"x": chart_x, "y": chart_y, "type":"line", "name":"Capital"}],
        "layout":{"title":"Portfolio Value Over Time","xaxis_title":"Date","yaxis_title":"Value"}
    })

    return cols, df_sum.to_dict("records"), chart, details

@app.callback(
    Output("batch-drilldown","children"),
    [ Input("batch-summary-table","selected_rows"),
      Input("batch-details","data") ],
    State("batch-summary-table","data"),
    prevent_initial_call=True,
)
def drilldown(selected, details, summary_rows):
    if not selected:
        return ""
    tag  = summary_rows[selected[0]]["tag"]
    rows = details.get(tag, [])
    if not rows:
        return html.Div(f"No detail for {tag}")
    return html.Div([
        html.H5(f"Per‑Ticker Detail for {tag}"),
        dash_table.DataTable(
            columns=[
                {"name":"Ticker",      "id":"ticker"},
                {"name":"Name",        "id":"name"},
                {"name":"Start Price", "id":"start_price"},
                {"name":"End Price",   "id":"end_price"},
                {"name":"Shares",      "id":"shares"},
                {"name":"Value End",   "id":"value_end"},
                {"name":"Return %",    "id":"return_%"},
            ],
            data=rows,
            page_size=len(rows),
            style_table={"overflowX":"auto"},
        )
    ])

if __name__ == "__main__":
    app.run(debug=True, port=8055)
