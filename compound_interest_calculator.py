import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output, State
import plotly.graph_objs as go
from datetime import datetime

def create_dash_app(server, url_base_pathname='/dash/compound-interest/'):
    # Initialize Dash without any extra CSS (we'll load style.css ourselves)
    app = dash.Dash(
        __name__,
        server=server,
        url_base_pathname=url_base_pathname,
        external_stylesheets=[],
    )
    app.title = 'Compound Interest Calculator — BacktestBob'

    # Embed your header/footer and link to your style.css
    app.index_string = f'''
<!DOCTYPE html>
<html lang="en">
  <head>
    {{%metas%}}
    <title>{{%title%}}</title>
    {{%favicon%}}
    {{%css%}}
    <link rel="stylesheet" href="/static/css/style.css" />
  </head>
  <body>
    <header>
      <a href="/"><img src="/static/backtestbob.png" id="logo" alt="BacktestBob logo" /></a>
      <nav class="navbar desktop-nav">
        <div class="nav-item"><a href="/" class="nav-link">Home</a></div>
        <div class="nav-item">
          <span class="nav-link">Calculators ▾</span>
          <div class="dropdown-content">
            <a href="/dash/compound-interest/">Compound Interest</a>
            <a href="/dash/pension-drawdown/">Pension Drawdown</a>
          </div>
        </div>
        <div class="nav-item"><a href="/blog/" class="nav-link">Blog</a></div>
        <div class="nav-item"><a href="/admin/login/" class="nav-link">Admin</a></div>
      </nav>
      <div class="hamburger">
        <div></div><div></div><div></div>
      </div>
      <nav class="mobile-menu">
        <a href="/">Home</a>
        <a href="/dash/compound-interest/">Compound Interest</a>
        <a href="/dash/pension-drawdown/">Pension Drawdown</a>
        <a href="/blog/">Blog</a>
        <a href="/admin/login/">Admin</a>
      </nav>
    </header>

    <main>
      {{%app_entry%}}
    </main>

    <footer>
      <p>© {datetime.utcnow().year} BacktestBob</p>
    </footer>

    {{%config%}}
    {{%scripts%}}
    {{%renderer%}}

    <script>
      // Toggle mobile menu
      document.addEventListener('DOMContentLoaded', function() {{
        const ham = document.querySelector('.hamburger'),
              menu = document.querySelector('.mobile-menu');
        ham.addEventListener('click', () => menu.classList.toggle('open'));
      }});
    </script>
  </body>
</html>
'''

    # Now define the actual Dash app layout & callbacks exactly as before
    app.layout = html.Div(style={'fontFamily': 'Arial, sans-serif'}, children=[
        html.Div(style={'padding':'10px'}, children=[
            html.Label("Principal Amount (£):"),
            dcc.Input(id='principal', type='number', value=1000, min=0, step=100)
        ]),
        html.Div(style={'padding':'10px'}, children=[
            html.Label("Annual Interest Rate (%):"),
            dcc.Input(id='rate', type='number', value=5, min=0, step=0.1)
        ]),
        html.Div(style={'padding':'10px'}, children=[
            html.Label("Times Compounded Per Year:"),
            dcc.Input(id='n', type='number', value=12, min=1, step=1),
            html.P(
                "Compounding frequency refers to how many times interest is applied per year. "
                "1 = yearly, 12 = monthly, 365 = daily.",
                style={'fontStyle':'italic','marginTop':'5px'}
            )
        ]),
        html.Div(style={'padding':'10px'}, children=[
            html.Label("Number of Years:"),
            dcc.Input(id='years', type='number', value=10, min=1, step=1)
        ]),

        # step-by-step toggle + controls
        html.Div(style={'padding':'10px'}, children=[
            dcc.Checklist(
                options=[{'label':' Enable step-by-step chart','value':'step'}],
                value=[], id='step-mode', inline=True
            )
        ]),
        html.Div(style={'padding':'10px'}, children=[
            html.Button('Step Year', id='step-btn', n_clicks=0),
            html.Button('Reset', id='reset-btn', n_clicks=0)
        ]),
        dcc.Store(id='current-year', data=0),

        html.Hr(),
        html.Div(id='summary-info', style={'fontSize':'18px','margin':'10px 0'}),
        html.Div(id='output-text', style={'fontSize':'20px','margin':'20px 0'}),

        dash_table.DataTable(
            id='summary-table',
            columns=[
                {'name':'Year','id':'Year'},
                {'name':'Start Balance (£)','id':'Start'},
                {'name':'Interest Earned (£)','id':'Interest'},
                {'name':'Cumulative Interest (£)','id':'CumInterest'},
                {'name':'End Balance (£)','id':'End'}
            ],
            data=[],
            style_table={'overflowX':'auto','marginBottom':'20px'},
            style_cell={'textAlign':'center','padding':'5px'},
            style_header={'fontWeight':'bold'}
        ),
        dcc.Graph(id='growth-graph')
    ])

    @app.callback(
        Output('current-year','data'),
        [Input('step-btn','n_clicks'),
         Input('reset-btn','n_clicks'),
         Input('years','value')],
        [State('current-year','data'),
         State('step-mode','value')]
    )
    def update_current_year(step_clicks, reset_clicks, years_val, current, mode):
        if 'step' not in mode:
            return years_val
        ctx = dash.callback_context
        if not ctx.triggered:
            return current
        trigger = ctx.triggered[0]['prop_id'].split('.')[0]
        if trigger in ['years','reset-btn']:
            return 0
        if trigger=='step-btn':
            return min(current+1, years_val)
        return current

    @app.callback(
        [Output('summary-info','children'),
         Output('output-text','children'),
         Output('growth-graph','figure'),
         Output('summary-table','data'),
         Output('summary-table','columns')],
        [Input('principal','value'),
         Input('rate','value'),
         Input('n','value'),
         Input('years','value'),
         Input('current-year','data'),
         Input('step-mode','value')]
    )
    def update_output(principal, rate, n, years_val, disp_year, mode):
        try:
            P0 = float(principal)
            r = float(rate)/100.0
            n = int(n)
            years_val = int(years_val)

            tps = list(range(years_val+1))
            bals = [P0*(1+r/n)**(n*t) for t in tps]
            maxb = max(bals)

            rows = []
            for i, t in enumerate(tps):
                st = bals[i-1] if i else P0
                en = bals[i]
                interest = en - st
                cum = en - P0
                rows.append({
                    'Year': t,
                    'Start': f"£{st:,.2f}",
                    'Interest': f"£{interest:,.2f}",
                    'CumInterest': f"£{cum:,.2f}",
                    'End': f"£{en:,.2f}"
                })

            if 'step' in mode:
                idx = min(disp_year, years_val)
                xs = tps[:idx+1] if idx else []
                ys = bals[:idx+1] if idx else []
            else:
                xs, ys = tps, bals

            fig = {
                'data': [] if not xs else [go.Scatter(x=xs, y=ys, mode='lines+markers')],
                'layout': go.Layout(
                    title='Investment Growth Over Time',
                    xaxis={'title':'Years','range':[0, years_val+1]},
                    yaxis={'title':'Balance (£)','range':[0, maxb*1.05]},
                    hovermode='closest'
                )
            }

            final = bals[-1]
            total_int = final - P0
            dbl = next((t for t,b in zip(tps,bals) if b >= 2*P0), None)
            dbl_msg = (
                f"Investment doubles in ~{dbl} years" if dbl is not None
                else f"Does not double within {years_val} years"
            )

            summary = html.Ul([
                html.Li(f"Initial Principal: £{P0:,.2f}"),
                html.Li(f"Final Balance: £{final:,.2f}"),
                html.Li(f"Total Interest Earned: £{total_int:,.2f}"),
                html.Li(dbl_msg)
            ])

            text = f"After {years_val} years, the investment will be worth £{final:,.2f}."
            columns = [
                {'name':'Year','id':'Year'},
                {'name':'Start Balance (£)','id':'Start'},
                {'name':'Interest Earned (£)','id':'Interest'},
                {'name':'Cumulative Interest (£)','id':'CumInterest'},
                {'name':'End Balance (£)','id':'End'}
            ]

            return summary, text, fig, rows, columns

        except Exception as e:
            return "", f"Error in input: {e}", {}, [], []

    return app

# Standalone debugging
if __name__ == '__main__':
    test_app = create_dash_app(server=None)
    test_app.run_server(debug=True, port=8058)
