import dash
from dash import dcc, html, Input, Output, State, dash_table

external_stylesheets = [
    'https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css'
]

def create_dash_app(server, url_base_pathname='/dash/pension-drawdown/'):
    app = dash.Dash(
        __name__, server=server,
        url_base_pathname=url_base_pathname,
        external_stylesheets=external_stylesheets
    )
    app.title = 'UK Pension Drawdown — BacktestBob'

    # Inline header/nav/footer with a direct static path for the logo
    app.index_string = '''
<!DOCTYPE html>
<html lang="en">
  <head>
    {%metas%}
    <title>{%title%}</title>
    {%favicon%}
    {%css%}

    <!-- Google Font & main stylesheet -->
    <link
      href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap"
      rel="stylesheet"
    />
    <link
      rel="stylesheet"
      href="/static/css/style.css"
    />
    <style>
      body { margin:0; font-family:Inter,sans-serif; background:#f9f9f9; }
      header {
        background:#fff; padding:1rem 2rem;
        display:flex; align-items:center; justify-content:space-between;
        border-bottom:1px solid #eee;
      }
      #logo { height:40px; }
      .navbar { display:flex; }
      .nav-item { position:relative; margin-left:1rem; }
      .nav-link { color:#111; text-decoration:none; font-weight:600; padding:.5rem; }
      .nav-item:hover .dropdown-content { display:block; }
      .dropdown-content {
        display:none; position:absolute; background:#fff;
        box-shadow:0 2px 8px rgba(0,0,0,0.1); border-radius:4px;
        top:100%; left:0; min-width:160px; z-index:100;
      }
      .dropdown-content a {
        display:block; padding:.75rem 1rem; color:#333; text-decoration:none;
      }
      .dropdown-content a:hover { background:#f0f0f0; }
      main.container { padding:2rem 1rem; }
      footer {
        background:#fff; padding:1rem 2rem; text-align:center;
        border-top:1px solid #eee; margin-top:2rem;
      }
    </style>
  </head>
  <body>
    <header>
      <a href="/"><img src="/static/backtestbob.png"
           alt="BacktestBob logo" id="logo" /></a>
      <nav class="navbar">
        <div class="nav-item">
          <a href="/" class="nav-link">Home</a>
        </div>
        <div class="nav-item">
          <span class="nav-link">Calculators ▾</span>
          <div class="dropdown-content">
            <a href="/dash/compound-interest/">Compound Interest</a>
            <a href="/dash/pension-drawdown/">Pension Drawdown</a>
          </div>
        </div>
        <div class="nav-item">
          <a href="/blog" class="nav-link">Blog</a>
        </div>
        <div class="nav-item">
          <a href="/admin/login" class="nav-link">Admin</a>
        </div>
      </nav>
    </header>

    <main class="container">
      {%app_entry%}
    </main>

    <footer>
      <p>© 2025 BacktestBob</p>
    </footer>

    {%config%}
    {%scripts%}
    {%renderer%}
  </body>
</html>
'''

    app.layout = html.Div(className='container', children=[
        html.H2("UK Pension Drawdown + State Pension",
                style={'marginBottom': '1.5rem'}),
        html.Div(className='row', children=[
            html.Div(className='col-md-6', children=[
                html.Label("Current Pension Pot (£)"),
                dcc.Input(id='pot', type='number', value=200000,
                          className='form-control'),
                html.Br(),

                html.Label("Annual Drawdown Desired (£/yr)"),
                dcc.Input(id='drawdown', type='number', value=15000,
                          className='form-control'),
                html.Br(),

                html.Label("Expected Annual Return (%)"),
                dcc.Input(id='return_rate', type='number', value=5,
                          className='form-control'),
                html.Br(),

                html.Label("Inflation Rate (%)"),
                dcc.Input(id='inflation', type='number', value=2,
                          className='form-control'),
                html.Br(),

                html.Label("Age at Start of Drawdown"),
                dcc.Input(id='start_age', type='number', value=60,
                          className='form-control'),
                html.Br(),

                html.Label("Age to Draw Until"),
                dcc.Input(id='end_age', type='number', value=95,
                          className='form-control'),
                html.Br(),

                html.Label("State Pension Age"),
                dcc.Input(id='state_age', type='number', value=67,
                          className='form-control'),
                html.Br(),

                html.Label("Current Annual State Pension (£/yr)"),
                dcc.Input(id='state_amount', type='number', value=10000,
                          className='form-control'),
                html.Br(),

                html.Button('Calculate', id='calc-btn', n_clicks=0,
                            className='btn btn-primary'),
            ]),
            html.Div(className='col-md-6', children=[
                html.H4(id='depletion-text',
                        style={'marginTop': '1rem'}),
                dcc.Graph(id='pot-chart'),
            ]),
        ]),
        html.Hr(),
        dash_table.DataTable(
            id='results-table',
            columns=[
                {'name': 'Age', 'id': 'age'},
                {'name': 'Start Pot (£)', 'id': 'start_pot'},
                {'name': 'State Pension Received (£)',
                 'id': 'state_pension'},
                {'name': 'Private Drawdown (£)',
                 'id': 'private_withdrawal'},
                {'name': 'End Pot (£)', 'id': 'end_pot'},
            ],
            style_table={'overflowX': 'auto', 'marginTop': '1rem'},
            style_cell={'textAlign': 'right', 'padding': '5px'},
            style_header={'fontWeight': 'bold'}
        )
    ])

    @app.callback(
        Output('results-table', 'data'),
        Output('pot-chart', 'figure'),
        Output('depletion-text', 'children'),
        Input('calc-btn', 'n_clicks'),
        State('pot', 'value'),
        State('drawdown', 'value'),
        State('return_rate', 'value'),
        State('inflation', 'value'),
        State('start_age', 'value'),
        State('end_age', 'value'),
        State('state_age', 'value'),
        State('state_amount', 'value'),
    )
    def update_drawdown(n, pot, drawdown, return_rate, inflation,
                        start_age, end_age, state_age, state_amount):
        # Convert inputs
        r = return_rate / 100
        i = inflation / 100

        years = list(range(start_age, end_age + 1))
        data = []
        current_pot = pot
        depleted_age = None

        for age in years:
            state_pension = 0
            if age >= state_age:
                state_pension = state_amount * ((1 + i) ** (age - state_age))

            private_withdrawal = max(drawdown - state_pension, 0)
            start_p = current_pot
            current_pot = start_p * (1 + r) - private_withdrawal
            end_pot = max(current_pot, 0)

            if depleted_age is None and current_pot <= 0:
                depleted_age = age

            data.append({
                'age': age,
                'start_pot': f"{start_p:,.0f}",
                'state_pension': f"{state_pension:,.0f}",
                'private_withdrawal': f"{private_withdrawal:,.0f}",
                'end_pot': f"{end_pot:,.0f}",
            })

        message = (
            f"⚠️ Your pot will run out at age {depleted_age}."
            if depleted_age else
            f"✅ Your pot lasts beyond age {end_age}."
        )

        fig = {
            'data': [{
                'x': years,
                'y': [float(r.replace(',', '')) for r in
                      [row['end_pot'] for row in data]],
                'mode': 'lines+markers',
                'name': 'End Pot (£)'
            }],
            'layout': {
                'title': 'Pension Pot Over Time',
                'xaxis': {'title': 'Age'},
                'yaxis': {'title': 'Pot Value (£)'},
                'margin': {'l': 50, 'r': 20, 't': 40, 'b': 50}
            }
        }

        return data, fig, message

    return app
