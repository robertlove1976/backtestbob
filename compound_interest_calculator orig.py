import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output
import plotly.graph_objs as go

# External CSS for nicer styling
external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

# Initialize the Dash app and underlying server
app = dash.Dash(__name__, external_stylesheets=external_stylesheets)
server = app.server

# Set page title and custom HTML template
app.title = "Compound Interest Calculator"
app.index_string = '''<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
    </head>
    <body>
        <header style="text-align:center; padding:20px; background:#f8f9fa;">
            <h1>Compound Interest Calculator</h1>
        </header>
        <main style="max-width:800px; margin:40px auto; padding:0 20px;">
            {%app_entry%}
        </main>
        <footer style="text-align:center; padding:20px; background:#f8f9fa;">
            <p>Built with Dash & Plotly</p>
        </footer>
        {%config%}
        {%scripts%}
        {%renderer%}
    </body>
</html>'''

# Define the layout
app.layout = html.Div([
    html.Div([
        html.Label("Principal Amount (£):"),
        dcc.Input(id='principal', type='number', value=1000, min=0, step=100)
    ], style={'padding': '10px'}),

    html.Div([
        html.Label("Annual Interest Rate (%):"),
        dcc.Input(id='rate', type='number', value=5, min=0, step=0.1)
    ], style={'padding': '10px'}),

    html.Div([
        html.Label("Times Compounded Per Year:"),
        dcc.Input(id='n', type='number', value=12, min=1, step=1),
        html.P(
            "Compounding frequency refers to how many times interest is applied per year. "
            "For example, 1 = yearly, 12 = monthly, 365 = daily. Higher frequency yields slightly more interest.",
            style={'fontStyle': 'italic', 'marginTop': '5px'}
        )
    ], style={'padding': '10px'}),

    html.Div([
        html.Label("Number of Years:"),
        dcc.Input(id='years', type='number', value=10, min=0, step=1)
    ], style={'padding': '10px'}),

    html.Hr(),

    html.Div(id='output-text', style={'fontSize': '20px', 'margin': '20px 0'}),

    dash_table.DataTable(
        id='summary-table',
        columns=[{'name': 'Year', 'id': 'Year'}, {'name': 'Value (£)', 'id': 'Value'}],
        data=[],
        style_table={'overflowX': 'auto', 'marginBottom': '20px'},
        style_cell={'textAlign': 'center', 'padding': '5px'},
        style_header={'fontWeight': 'bold'}
    ),

    dcc.Graph(id='growth-graph')
], style={'fontFamily': 'Arial, sans-serif'})

# Callback to update outputs
@app.callback(
    [Output('output-text', 'children'), Output('growth-graph', 'figure'),
     Output('summary-table', 'data'), Output('summary-table', 'columns')],
    [Input('principal', 'value'), Input('rate', 'value'),
     Input('n', 'value'), Input('years', 'value')]
)
def update_output(principal, rate, n, years):
    try:
        P = float(principal)
        r = float(rate) / 100.0
        n = int(n)
        years = int(years)

        time_points = list(range(0, years + 1))
        values = [P * (1 + r / n) ** (n * t) for t in time_points]

        final_value = values[-1]
        text = f"After {years} years, the investment will be worth £{final_value:,.2f}."

        figure = {
            'data': [go.Scatter(x=time_points, y=values, mode='lines+markers')],
            'layout': go.Layout(title='Investment Growth Over Time',
                                xaxis={'title': 'Years'}, yaxis={'title': 'Amount (£)'},
                                hovermode='closest')
        }

        table_data = [{'Year': t, 'Value': f"£{val:,.2f}"} for t, val in zip(time_points, values)]
        table_columns = [{'name': 'Year', 'id': 'Year'}, {'name': 'Value (£)', 'id': 'Value'}]

        return text, figure, table_data, table_columns
    except Exception as e:
        return f"Error in input: {e}", {}, [], []

# Run the server
if __name__ == '__main__':
    app.run(debug=True)
