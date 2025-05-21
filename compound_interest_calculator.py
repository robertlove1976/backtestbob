import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output, State
import plotly.graph_objs as go
from datetime import datetime


def create_dash_app(server=None, url_base_pathname='/dash/compound-interest/'):
    # Initialize Dash: standalone or embedded
    if server:
        app = dash.Dash(
            __name__,
            server=server,
            url_base_pathname=url_base_pathname,
            external_stylesheets=[],
        )
    else:
        app = dash.Dash(
            __name__,
            external_stylesheets=[],
        )
    app.title = 'Compound Interest Calculator — BacktestBob'

    # HTML template with header/footer
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
        <div class="nav-item"><a href="/admin/login" class="nav-link">Admin</a></div>
      </nav>
      <div class="hamburger">
        <div></div><div></div><div></div>
      </div>
      <nav class="mobile-menu">
        <a href="/">Home</a>
        <a href="/dash/compound-interest/">Compound Interest</a>
        <a href="/dash/pension-drawdown/">Pension Drawdown</a>
        <a href="/blog/">Blog</a>
        <a href="/admin/login">Admin</a>
      </nav>
    </header>
    <main>{{%app_entry%}}</main>
    <footer><p>© {datetime.utcnow().year} BacktestBob</p></footer>
    {{%config%}}{{%scripts%}}{{%renderer%}}
  </body>
</html>
'''

    # App layout
    app.layout = html.Div(style={'fontFamily':'Arial, sans-serif', 'maxWidth':'700px', 'margin':'auto'}, children=[
        html.H2('Compound Interest Calculator'),
        # Currency selector
        html.Div(style={'padding':'10px'}, children=[
            html.Label('Select Currency:'),
            dcc.Dropdown(
                id='currency',
                options=[{'label': c, 'value': c} for c in ['£', '$', '€', '¥']],
                value='£', clearable=False
            )
        ]),
        # Principal
        html.Div(style={'padding':'10px'}, children=[
            html.Label('Principal Amount:'),
            dcc.Input(id='principal', type='number', value=1000, min=0, step=0.01)
        ]),
        # Interest rate
        html.Div(style={'padding':'10px'}, children=[
            html.Label('Annual Interest Rate (%):'),
            dcc.Input(id='rate', type='number', value=5, min=0, step=0.1)
        ]),
        # Compounding frequency
        html.Div(style={'padding':'10px'}, children=[
            html.Label('Times Compounded Per Year:'),
            dcc.Input(id='n', type='number', value=12, min=1, step=1),
            html.P('Compounding frequency: 1=yearly, 12=monthly, 365=daily.', style={'fontStyle':'italic','marginTop':'5px'})
        ]),
        # Years
        html.Div(style={'padding':'10px'}, children=[
            html.Label('Number of Years:'),
            dcc.Input(id='years', type='number', value=10, min=1, step=1)
        ]),
        # Additional deposit
        html.Div(style={'padding':'10px'}, children=[
            html.Label('Additional Deposit Amount:'),
            dcc.Input(id='deposit_amt', type='number', value=0, min=0, step=0.01)
        ]),
        html.Div(style={'padding':'10px'}, children=[
            html.Label('Deposit Frequency:'),
            dcc.Dropdown(
                id='deposit_freq',
                options=[
                    {'label':'Weekly','value':'weekly'},
                    {'label':'Monthly','value':'monthly'},
                    {'label':'Annual','value':'annual'}
                ], value='monthly', clearable=False
            )
        ]),
        # Step-by-step controls
        html.Div(style={'padding':'10px'}, children=[
            dcc.Checklist(options=[{'label':' Enable step-by-step chart','value':'step'}], value=[], id='step_mode', inline=True)
        ]),
        html.Div(style={'padding':'10px'}, children=[
            html.Button('Step Year', id='step_btn', n_clicks=0),
            html.Button('Reset', id='reset_btn', n_clicks=0)
        ]),
        dcc.Store(id='current_year', data=0),
        html.Hr(),
        html.Div(id='summary_info', style={'fontSize':'18px','margin':'10px 0'}),
        html.Div(id='output_text', style={'fontSize':'20px','margin':'20px 0'}),
        dash_table.DataTable(
            id='summary_table',
            columns=[],
            data=[],
            style_table={'overflowX':'auto','marginBottom':'20px'},
            style_cell={'textAlign':'center','padding':'5px'},
            style_header={'fontWeight':'bold'}
        ),
        dcc.Graph(id='growth_graph')
    ])

    # Step callback
    @app.callback(
        Output('current_year','data'),
        [Input('step_btn','n_clicks'), Input('reset_btn','n_clicks'), Input('years','value')],
        [State('current_year','data'), State('step_mode','value')]
    )
    def update_current_year(step_clicks, reset_clicks, years_val, current, mode):
        if 'step' not in mode:
            return years_val
        ctx = dash.callback_context
        if not ctx.triggered:
            return current
        trigger = ctx.triggered[0]['prop_id'].split('.')[0]
        if trigger in ['years','reset_btn']:
            return 0
        if trigger=='step_btn':
            return min(current+1, years_val)
        return current

    # Main output callback
    @app.callback(
        [Output('summary_info','children'), Output('output_text','children'), Output('growth_graph','figure'),
         Output('summary_table','data'), Output('summary_table','columns')],
        [Input('principal','value'), Input('rate','value'), Input('n','value'), Input('years','value'),
         Input('current_year','data'), Input('step_mode','value'), Input('currency','value'),
         Input('deposit_amt','value'), Input('deposit_freq','value')]
    )
    def update_output(principal, rate, n, years_val, disp_year, mode, currency, deposit_amt, deposit_freq):
        try:
            P0 = float(principal or 0)
            r = float(rate or 0)/100.0
            n = int(n or 1)
            years_val = int(years_val or 0)
            symbol = currency or '£'
            dep_amt = float(deposit_amt or 0)
            freq_map = {'weekly':52,'monthly':12,'annual':1}
            dep_freq = freq_map.get(deposit_freq,0) if dep_amt>0 else 0

            records=[]
            balance=P0
            cum_int=0.0
            start_bal=P0
            for yr in range(1, years_val+1):
                events=[(i/n,'comp') for i in range(1,n+1)]
                if dep_freq:
                    events += [(j/dep_freq,'dep') for j in range(1,dep_freq+1)]
                events=sorted(events, key=lambda x:(x[0],0 if x[1]=='comp' else 1))
                year_int=0.0
                for _,etype in events:
                    if etype=='comp': intr=balance*(r/n); balance+=intr; year_int+=intr; cum_int+=intr
                    else: balance+=dep_amt
                records.append({'Year':yr,'Start':start_bal,'Interest':year_int,'CumInterest':cum_int,'End':balance})
                start_bal=balance

            # Format table
            rows=[{'Year':rec['Year'],'Start':f"{symbol}{rec['Start']:,.2f}",
                   'Interest':f"{symbol}{rec['Interest']:,.2f}",
                   'CumInterest':f"{symbol}{rec['CumInterest']:,.2f}",
                   'End':f"{symbol}{rec['End']:,.2f}"} for rec in records]
            cols=[{'name':'Year','id':'Year'},
                  {'name':f'Start ({symbol})','id':'Start'},
                  {'name':f'Interest ({symbol})','id':'Interest'},
                  {'name':f'Cumulative ({symbol})','id':'CumInterest'},
                  {'name':f'End ({symbol})','id':'End'}]

            # Graph
            xs=[r['Year'] for r in records]
            ys=[r['End'] for r in records]
            if 'step' in mode:
                idx=min(disp_year, years_val)
                xs, ys = (xs[:idx], ys[:idx]) if idx else ([], [])
            fig={'data':[] if not xs else [go.Scatter(x=xs,y=ys,mode='lines+markers')],
                 'layout':go.Layout(title='Investment Growth Over Time', xaxis={'title':'Years'},
                                     yaxis={'title':f'Balance ({symbol})'})}

            final=records[-1]['End'] if records else P0
            total_int=cum_int
            dbl_msg=("Doubling time N/A with deposits" if dep_amt>0 else
                     next((f"Doubles in ~{rec['Year']} yrs" for rec in records if rec['End']>=2*P0),
                          f"No double within {years_val} yrs"))
            summary=html.Ul([html.Li(f"Initial: {symbol}{P0:,.2f}"), html.Li(f"Final: {symbol}{final:,.2f}"),
                             html.Li(f"Total Interest: {symbol}{total_int:,.2f}"), html.Li(dbl_msg)])
            text=f"After {years_val} yrs: {symbol}{final:,.2f}."
            return summary, text, fig, rows, cols
        except Exception as e:
            return "", f"Error in input: {e}", {}, [], []

    return app

# Standalone debugging
if __name__ == '__main__':
    app = create_dash_app()
    app.run_server(debug=True, port=8058)
