#!/usr/bin/env python3
import logging, requests, pandas as pd, duckdb, re, sys, json
from datetime import date
from dateutil.relativedelta import relativedelta

# ─── Logging Configuration ───
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# ─── Configuration Constants ───
DUCKDB_FILE   = "analytics.duckdb"
TRADE_TABLE   = "fmp_house_trades"
PRICE_TABLE   = "fmp_price_history"
DETAIL_TABLE  = "fmp_member_details"
PROG_TABLE    = "fmp_progress"
PAGE_LIMIT    = 500
FMP_API_KEY   = "3LUYNinfxHPsRtVoxbIz4iaR0tXjpr8k"

# ─── DuckDB helper ───
def get_duck_connection():
    return duckdb.connect(DUCKDB_FILE)

# ─── Utility: parse amount strings ───
def parse_amount(val):
    if isinstance(val, str):
        nums = re.findall(r"\$?([\d,]+)", val)
        if nums:
            ints = [int(n.replace(',', '')) for n in nums]
            return sum(ints) / len(ints)
    try:
        return float(val)
    except:
        return 0.0

# ─── Progress table helpers ───
def init_progress():
    with get_duck_connection() as con:
        existing = [t[0] for t in con.execute("SHOW TABLES").fetchall()]
        if PROG_TABLE not in existing:
            con.execute(f"CREATE TABLE {PROG_TABLE} (task VARCHAR PRIMARY KEY, last_key VARCHAR)")
            logger.info(f"Created progress table {PROG_TABLE}")

def get_progress(task):
    with get_duck_connection() as con:
        res = con.execute(f"SELECT last_key FROM {PROG_TABLE} WHERE task = ?", (task,)).fetchone()
    return res[0] if res else None

def set_progress(task, key):
    with get_duck_connection() as con:
        if get_progress(task):
            con.execute(f"UPDATE {PROG_TABLE} SET last_key = ? WHERE task = ?", (key, task))
        else:
            con.execute(f"INSERT INTO {PROG_TABLE}(task, last_key) VALUES(?,?)", (task, key))

# ─── Helper: create price table ───
def create_price_table(con):
    con.execute(
        f"CREATE TABLE {PRICE_TABLE}(symbol VARCHAR, priceDate DATE, open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume BIGINT, PRIMARY KEY(symbol, priceDate))"
    )
    logger.info(f"Created price history table {PRICE_TABLE}")

# ─── Fetch trades ───
def fetch_all_fmp_trades(limit=PAGE_LIMIT):
    key = FMP_API_KEY
    trades, page = [], 0
    while True:
        url = f"https://financialmodelingprep.com/stable/house-latest?page={page}&limit={limit}&apikey={key}"
        r = requests.get(url, timeout=10)
        if r.status_code == 400:
            logger.debug(f"End of pages at {page}")
            break
        if r.status_code == 401:
            logger.error('Unauthorized: check embedded FMP_API_KEY')
            sys.exit(1)
        r.raise_for_status()
        batch = r.json() or []
        logger.debug(f"Page {page}: {len(batch)} records")
        if not batch:
            break
        trades.extend(batch)
        page += 1
    logger.info(f"Fetched total {len(trades)} trades")
    return pd.DataFrame(trades)

# ─── Initialize / append tables ───
def initialize_tables():
    df = fetch_all_fmp_trades()
    with get_duck_connection() as con:
        existing = [t[0] for t in con.execute("SHOW TABLES").fetchall()]
        if TRADE_TABLE not in existing:
            con.register('df_all', df)
            con.execute(f"CREATE TABLE {TRADE_TABLE} AS SELECT * FROM df_all")
            logger.info(f"Created {TRADE_TABLE} ({len(df)} rows)")
        else:
            logger.debug(f"Table {TRADE_TABLE} exists")
        if PRICE_TABLE not in existing:
            create_price_table(con)
        else:
            cols = con.execute(f"PRAGMA table_info({PRICE_TABLE})").fetchall()
            if len(cols) != 7:
                logger.warning(f"{PRICE_TABLE} schema mismatch ({len(cols)} cols), recreating table")
                con.execute(f"DROP TABLE {PRICE_TABLE}")
                create_price_table(con)
        if DETAIL_TABLE not in existing:
            con.execute(
                f"CREATE TABLE {DETAIL_TABLE}(member VARCHAR PRIMARY KEY, detail JSON)"
            )
            logger.info(f"Created detail table {DETAIL_TABLE}")
    init_progress()

# ─── Load new trades ───
def load_new_trades():
    df = fetch_all_fmp_trades()
    if df.empty:
        logger.warning("No trades fetched")
        return
    df['transactionDate'] = pd.to_datetime(df['transactionDate']).dt.date
    with get_duck_connection() as con:
        max_raw = con.execute(f"SELECT MAX(transactionDate) FROM {TRADE_TABLE}").fetchone()[0]
    if isinstance(max_raw, str):
        max_raw = date.fromisoformat(max_raw)
    df_new = df[df['transactionDate'] > max_raw] if max_raw else df
    logger.info(f"Appending {len(df_new)} new rows to {TRADE_TABLE}")
    if not df_new.empty:
        with get_duck_connection() as con:
            con.register('df_new', df_new)
            con.execute(f"INSERT INTO {TRADE_TABLE} SELECT * FROM df_new")

# ─── Update member details ───
def update_all_member_details():
    key = FMP_API_KEY
    with get_duck_connection() as con:
        members = con.execute(
            f"SELECT DISTINCT firstName, lastName FROM {TRADE_TABLE}"
        ).df()
    last = get_progress('members')
    for _, row in members.iterrows():
        fullname = f"{row['firstName']} {row['lastName']}"
        if last and fullname <= last:
            continue
        try:
            r = requests.get(
                f"https://financialmodelingprep.com/api/v3/government-trading/members/{fullname}",
                params={"apikey":key}, timeout=10
            )
            r.raise_for_status()
            detail = json.dumps(r.json())
            with get_duck_connection() as con:
                con.execute(f"INSERT INTO {DETAIL_TABLE}(member, detail) VALUES(?,?)", (fullname, detail))
            logger.info(f"Inserted details for {fullname}")
        except Exception as e:
            logger.warning(f"Error fetching details for {fullname}: {e}")
        set_progress('members', fullname)

# ─── Update price history ───
def update_price_history_for_member(fullname):
    key = FMP_API_KEY
    fn, ln = fullname.split(' ',1)
    with get_duck_connection() as con:
        rows = con.execute(
            f"SELECT symbol, MIN(transactionDate) FROM {TRADE_TABLE} WHERE firstName=? AND lastName=? GROUP BY symbol", (fn,ln)
        ).fetchall()
    for sym, start_raw in rows:
        start_date = date.fromisoformat(start_raw) if isinstance(start_raw, str) else start_raw
        with get_duck_connection() as con:
            res = con.execute(
                f"SELECT MAX(priceDate) FROM {PRICE_TABLE} WHERE symbol = ? AND priceDate >= ?", (sym, start_date)
            ).fetchone()[0]
        fetch_from = date.fromisoformat(res) if res and isinstance(res, str) else res or start_date
        params = {'from': fetch_from.isoformat(), 'to': date.today().isoformat(), 'apikey': key}
        try:
            r = requests.get(f"https://financialmodelingprep.com/api/v3/historical-price-full/{sym}", params=params, timeout=10)
            r.raise_for_status()
            bars = r.json().get('historical', [])
            with get_duck_connection() as con:
                for b in bars:
                    con.execute(
                        f"INSERT INTO {PRICE_TABLE} VALUES(?,?,?,?,?,?,?) ON CONFLICT DO NOTHING",
                        (sym, b['date'], b['open'], b['high'], b['low'], b['close'], b['volume'])
                    )
            logger.info(f"Cached {len(bars)} bars for {sym} (member {fullname})")
        except Exception as e:
            logger.warning(f"Error fetching history for {sym}@{fullname}: {e}")

def update_all_price_history():
    with get_duck_connection() as con:
        members = [f"{r[0]} {r[1]}" for r in con.execute(
            f"SELECT DISTINCT firstName, lastName FROM {TRADE_TABLE}"
        ).fetchall()]
    last = get_progress('prices')
    for fullname in members:
        if last and fullname <= last:
            continue
        logger.info(f"Updating prices for {fullname}")
        update_price_history_for_member(fullname)
        set_progress('prices', fullname)
        logger.info(f"Completed price history for {fullname}")

# ─── Compute portfolio summary ───
def compute_portfolio_summary():
    ...

# ─── Dash App and Callbacks ───
from dash import Dash, html, dcc, dash_table, Input, Output, State
import plotly.express as px

app = Dash(__name__)

app.layout = html.Div([
    html.H1("Congressional Trades Dashboard"),
    html.Button("Delete All Trades", id='delete-trades-btn', n_clicks=0, style={'margin-bottom':'20px'}),
    html.Div([
        html.Label("Select Member:"),
        dcc.Dropdown(id='member-dropdown', placeholder="Choose a member...")
    ], style={'width':'300px','margin-bottom':'20px'}),
    html.H2("All Members"),
    dash_table.DataTable(
        id='owner-table',
        columns=[{"name":"Member","id":"member"}],
        page_size=10,
        style_table={'overflowX':'auto'}
    ),
    html.H2("Trades"),
    dash_table.DataTable(
        id='trades-table',
        columns=[
            {"name": "Buy Date",    "id": "buy_date"},
            {"name": "Ticker",      "id": "symbol"},
            {"name": "Type",        "id": "type"},
            {"name": "Shares",      "id": "amount"},
            {"name": "Buy Price",   "id": "buy_price"},
            {"name": "Asset",       "id": "assetDescription"},
        ],
        page_size=10,
        style_table={'overflowX': 'auto'}
    ),
    html.H2("Performance (Holding-Period Returns)"),
    dcc.Graph(id='performance-chart')
])

@app.callback(
    Output('owner-table', 'data'),
    Output('member-dropdown', 'options'),
    Input('delete-trades-btn', 'n_clicks')
)
def delete_all_and_reload(n_clicks):
    if n_clicks > 0:
        with get_duck_connection() as con:
            con.execute(f"DELETE FROM {TRADE_TABLE}")
        init_progress()
    with get_duck_connection() as con:
        df = con.execute(
            f"SELECT DISTINCT firstName, lastName FROM {TRADE_TABLE} ORDER BY lastName, firstName"
        ).df()
    options = [{"label": f"{r['firstName']} {r['lastName']}", "value": f"{r['firstName']} {r['lastName']}"} for _,r in df.iterrows()]
    data = [{"member": o['label']} for o in options]
    return data, options

@app.callback(
    Output('trades-table', 'data'),
    Output('performance-chart', 'figure'),
    Input('member-dropdown', 'value')
)
def show_member_details(fullname):
    if not fullname:
        return [], {}
    fn, ln = fullname.split(' ', 1)
    # 1) Pull in buy_date & buy_price
    with get_duck_connection() as con:
        trades = con.execute(
            f"""
            SELECT
              t.transactionDate    AS buy_date,
              t.symbol,
              t.type,
              t.amount            AS amount,
              p.close             AS buy_price,
              t.assetDescription
            FROM {TRADE_TABLE} t
            LEFT JOIN {PRICE_TABLE} p
              ON p.symbol = t.symbol AND p.priceDate = t.transactionDate
            WHERE t.firstName = ? AND t.lastName = ?
            ORDER BY t.transactionDate
            """, (fn,ln)
        ).df()
    trades['buy_date'] = pd.to_datetime(trades['buy_date']).dt.date
    trades['amount']   = trades['amount'].apply(parse_amount)

    # 2) Compute holding-period returns
    as_of = date.today()
    returns = []
    def fetch_price(sym, tgt):
        with get_duck_connection() as c2:
            res = c2.execute(
                f"SELECT close FROM {PRICE_TABLE} WHERE symbol=? AND priceDate=?", (sym, tgt)
            ).fetchone()
        return res[0] if res else None

    # focus just on purchase lots
    buys = trades[trades['type'].str.lower().str.startswith('purchase')].copy()
    for _, r in buys.iterrows():
        delta_days = (as_of - r['buy_date']).days
        if delta_days < 365:
            # <1yr → return to date
            current = fetch_price(r['symbol'], as_of)
            if current is not None:
                pct = (current - r['buy_price']) / r['buy_price'] * 100
                returns.append({
                    'symbol': r['symbol'],
                    'holding_period': 'to date',
                    'return_pct': pct
                })
        else:
            # ≥1yr → returns at 1-5yrs
            for yrs in range(1,6):
                tgt = r['buy_date'] + relativedelta(years=yrs)
                if tgt > as_of:
                    break
                price_at = fetch_price(r['symbol'], tgt)
                if price_at is not None:
                    pct = (price_at - r['buy_price']) / r['buy_price'] * 100
                    returns.append({
                        'symbol': r['symbol'],
                        'holding_period': f'{yrs}yr',
                        'return_pct': pct
                    })

    df_ret = pd.DataFrame(returns)

    # 3) Chart via Plotly
    fig = {}
    if not df_ret.empty:
        fig = px.line(
            df_ret,
            x='holding_period', y='return_pct', color='symbol',
            markers=True,
            title=f"Holding-Period Returns for {fullname}",
            labels={'return_pct':'Return (%)','holding_period':'Holding Period'}
        )

    return trades.to_dict('records'), fig

# ─── Main CLI ───
if __name__=='__main__':
    if len(sys.argv)<2:
        logger.error('Usage: python house_trades.py <mode>')
        sys.exit(1)
    mode = sys.argv[1]
    initialize_tables()
    if mode == 'serve':
        app.run(debug=True, port=8067)
    elif mode == 'update-trades':
        load_new_trades()
    elif mode == 'update-members':
        update_all_member_details()
    elif mode == 'update-prices':
        update_all_price_history()
    else:
        logger.error(f'Unknown mode: {mode}')
        sys.exit(1)
