import dash
from dash import dcc, html, Input, Output, State, dash_table
from datetime import datetime

# Bootstrap just for the grid & form controls
external_stylesheets = [
    'https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css'
]

def create_dash_app(server, url_base_pathname='/dash/pension-drawdown/'):
    app = dash.Dash(
        __name__,
        server=server,
        url_base_pathname=url_base_pathname,
        external_stylesheets=external_stylesheets
    )
    app.title = 'UK Pension Drawdown — BacktestBob'

    # Use a normal Python string (NOT an f-string) for index_string
    app.index_string = """
<!DOCTYPE html>
<html lang="en">
  <head>
    {%metas%}
    <title>{%title%}</title>
    {%favicon%}
    {%css%}
    <!-- Main site stylesheet -->
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

    <main class="container my-4">
      {%app_entry%}
    </main>

    <footer>
      <p>© {year} BacktestBob</p>
    </footer>

    {%config%}
    {%scripts%}
    {%renderer%}

    <script>
      document.addEventListener('DOMContentLoaded', function() {
        const ham = document.querySelector('.hamburger'),
              menu = document.querySelector('.mobile-menu');
        ham.addEventListener('click', () => menu.classList.toggle('open'));
      });
    </script>
  </body>
</html>
""".replace("{year}", str(datetime.utcnow().year))

    # Now define the app.layout and callbacks
    app.layout = html.Div(className='container my-4', children=[
        html.H2("UK Pension Drawdown + State Pension", style={'marginBottom': '1.5rem'}),
        html.Div(className='row', children=[
            html.Div(className='col-md-6', children=[
                html.Label("Current Pension Pot (£)"),
                dcc.Input(id='pot', type='number', value=200000, className='form-control'),
                html.Br(),

                html.Label("Annual Drawdown Desired (£/yr)"),
                dcc.Input(id='drawdown', type='number', value=15000, className='form-control'),
                html.Br(),

                html.Label("Expected Annual Return (%)"),
                dcc.Input(id='return_rate', type='number', value=5, className='form-control'),
                html.Br(),

                html.Label("Inflation Rate (%)"),
                dcc.Input(id='inflation', type='number', value=2, className='form-control'),
                html.Br(),

                html.Label("Age at Start of Drawdown"),
                dcc.Input(id='start_age', type='number', value=60, className='form-control'),
                html.Br(),

                html.Label("Age to Draw Until"),
                dcc.Input(id='end_age', type='number', value=95, className='form-control'),
                html.Br(),

                html.Label("State Pension Age"),
                dcc.Input(id='state_age', type='number', value=67, className='form-control'),
                html.Br(),

                html.Label("Current Annual State Pension (£/yr)"),
                dcc.Input(id='state_amount', type='number', value=10000, className='form-control'),
                html.Br(),

                html.Button('Calculate', id='calc-btn', n_clicks=0, className='btn btn-primary'),
            ]),
            html.Div(className='col-md-6', children=[
                html.H4(id='depletion-text', style={'marginTop': '1rem'}),
                dcc.Graph(id='pot-chart'),
            ]),
        ]),
        html.Hr(),
        dash_table.DataTable(
            id='results-table',
            columns=[
                {'name': 'Age', 'id': 'age'},
                {'name': 'Start Pot (£)', 'id': 'start_pot'},
                {'name': 'State Pension Received (£)', 'id': 'state_pension'},
                {'name': 'Private Drawdown (£)', 'id': 'private_withdrawal'},
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
        r = return_rate / 100
        i = inflation / 100

        years = list(range(start_age, end_age + 1))
        data = []
        current = pot
        depleted = None

        for age in years:
            state_pension = 0
            if age >= state_age:
                state_pension = state_amount * ((1 + i) ** (age - state_age))

            private_withdrawal = max(drawdown - state_pension, 0)
            start_val = current
            current = start_val * (1 + r) - private_withdrawal
            end_val = max(current, 0)

            if depleted is None and current <= 0:
                depleted = age

            data.append({
                'age': age,
                'start_pot': f"{start_val:,.0f}",
                'state_pension': f"{state_pension:,.0f}",
                'private_withdrawal': f"{private_withdrawal:,.0f}",
                'end_pot': f"{end_val:,.0f}",
            })

        message = (
            f"⚠️ Your pot will run out at age {depleted}."
            if depleted else
            f"✅ Your pot lasts beyond age {end_age}."
        )

        fig = {
            'data': [{
                'x': years,
                'y': [float(row['end_pot'].replace(',', '')) for row in data],
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
