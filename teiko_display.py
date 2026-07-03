import dash
from dash import dcc, html, dash_table, Input, Output,State, callback
from teiko_database import _db_connection
import plotly.express as px
import pandas as pd
from scipy.stats import ttest_ind
import statsmodels.stats.multitest as multitest
from itertools import combinations
 
# ── Palette ────────────────────────────────────────────────────────────────────
GREY_BG      = "#F2F2F2"   # outer page background
WHITE        = "#FFFFFF"   # card / section bodies
ACCENT       = "#E8491E"   # red-orange highlight
ACCENT_LIGHT = "#FAD9D1"   # soft tint for hover / selected rows
BORDER       = "#DEDEDE"   # subtle dividers
TEXT_PRIMARY = "#1A1A1A"
TEXT_MUTED   = "#6B6B6B"
FONT         = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
 
# ── Load data, process ──────────────────────────────────────────────────────────
db_path = r'C:\Users\admin\Documents\Teiko Assesment\teiko.db'

#access data
with _db_connection(db_path) as conn:
    #cell count information from CELL_COUNT
    cell_data = pd.read_sql('''SELECT sample as sample,
                                cell_type as population, 
                                cell_count as count 
                            FROM CELL_COUNT 
                            ORDER BY sample''',conn)
    #non-identifying subject and sample information
    sample_data = pd.read_sql('''SELECT sub.project as project,
                                    sub.subject as subject,
                                    sam.sample as sample,
                                    sub.condition as condition,
                                    sub.treatment as treatment,
                                    sub.response as response,
                                    sub.sex as sex,
                                    sam.sample_type as sample_type,
                                    sam.time_from_treatment_start as time_from_treatment_start
                                FROM subject sub
                                JOIN sample sam 
                                ON sub.subject = sam.subject
                              ''',conn)

###Data used for long cell counts data overview, Section 1
#transform cell_data to include a total count and proportion column
cell_data['total_count'] = cell_data.groupby("sample")["count"].transform("sum")
cell_data["proportion"] = (cell_data["count"] / cell_data["total_count"]).round(4)
cell_data = cell_data[['sample','population','total_count','count','proportion']]

#filled NaN value with 'Na'. Note: isna still catches these, but is a valid input
sample_data['response'] = sample_data['response'].fillna('NA')

###Data used for statistical analysis, Section 2
analysis_data = pd.merge(sample_data,cell_data,on='sample')

###Section 3: columns used for analysis
col_list = sample_data.columns
 
# ── Reusable style helpers ──────────────────────────────────────────────────────
def section_card(children, **kwargs):
    base = {
        "backgroundColor": WHITE,
        "borderRadius":    "10px",
        "padding":         "24px 28px",
        "marginBottom":    "24px",
        "boxShadow":       "0 1px 4px rgba(0,0,0,0.07)",
        "border":          f"1px solid {BORDER}",
        "fontFamily":   FONT,
    }
    if kwargs:
        base.update(kwargs)
    return html.Div(children, style=base)
 
 
def section_label(text):
    return html.P(text, style={
        "fontSize":      "14px",
        "fontWeight":    "600",
        "letterSpacing": "0.08em",
        "textTransform": "uppercase",
        "color":         ACCENT,
        "marginBottom":  "4px",
        "marginTop":     "0",
        "fontFamily":   FONT,
    })
 
def section_title(text):
    return html.H2(text, style={
        "fontSize":     "32px",
        "fontWeight":   "600",
        "color":        TEXT_PRIMARY,
        "margin":       "0 0 16px 0",
        "fontFamily":   FONT,
    })

def subsection_title(text, id=None):
    props = {"style": 
            {"fontSize": "24px",
            "fontWeight": "600",
            "color": TEXT_PRIMARY,
            "margin": "0 0 16px 0",
            "fontFamily":   FONT}}
    if id is not None:
        props["id"] = id
    return html.H3(text, **props)

def section_text(text):
    return html.P(text, style={
        "fontSize":     "14px",
        "fontWeight":   "400",
        "color":        TEXT_PRIMARY,
        "margin":       "0 0 16px 0",
        "fontFamily":   FONT,
    })

def subsection_text(text):
    return html.Span(text, style={
        "fontSize":     "14px",
        "fontWeight":   "600",
        "color":        TEXT_PRIMARY,
        "fontFamily":   FONT,
    })
 
def styled_dropdown(dropdown_id, options, placeholder, value=None,multi=True):
    return dcc.Dropdown(
        id=dropdown_id,
        options=options,
        value=value,
        multi=multi,
        placeholder=placeholder,
        clearable=True,
        style={
            "fontFamily":    FONT,
            "fontSize":      "13px",
            "borderRadius":  "6px",
            "border":        f"1px solid {BORDER}",
            "marginBottom":  "16px",
            "width":         "280px",
        },
        
    )
 
 
def styled_table(table_id:str, dataframe:pd.DataFrame = None,**kwargs):
    '''
    Wrapper for stylized table
    dataframe = [] will create an empty table. Provide a columns kwarg
    to define the table
    '''
    isdf = isinstance(dataframe,pd.DataFrame)
    defaults = dict(
        id=table_id,
        columns=[{"name": c, "id": c} for c in dataframe.columns] if isdf else [],
        data=dataframe.to_dict("records") if isdf else [],
        page_size=10,
        style_table={
            "overflowX": "auto",
            "borderRadius": "6px",
            "border": f"1px solid {BORDER}",
        },
        style_header={
            "backgroundColor": GREY_BG,
            "fontWeight":      "600",
            "fontSize":        "12px",
            "color":           TEXT_PRIMARY,
            "borderBottom":    f"2px solid {ACCENT}",
            "padding":         "10px 14px",
            "fontFamily":      FONT,
        },
        style_cell={
            "fontFamily":  FONT,
            "fontSize":    "13px",
            "color":       TEXT_PRIMARY,
            "padding":     "9px 14px",
            "border":      f"1px solid {BORDER}",
            "whiteSpace":  "normal",
            "height":      "auto",
        },
        style_data_conditional=[
            {
                "if": {"row_index": "odd"},
                "backgroundColor": "#FAFAFA",
            },
            {
                "if": {"state": "selected"},
                "backgroundColor": ACCENT_LIGHT,
                "border":          f"1px solid {ACCENT}",
            },
        ],
    )
    defaults.update(kwargs)
    extra_conditions = kwargs.pop("style_data_conditional", [])
    defaults["style_data_conditional"] += extra_conditions
    return dash_table.DataTable(**defaults)
 
def styled_button( buttonid,text=None,n_clicks=None):
    return html.Button(
        text,
        id = buttonid,
        n_clicks=n_clicks,
        style={
        "backgroundColor": ACCENT,
        "color":           WHITE,
        "border":          "none",
        "borderRadius":    "6px",
        "padding":         "0px 10x",   # ← zero vertical padding, let height do the work
        "height":          "36px",        # ← match dropdown height exactly
        "alignSelf":       "flex-start",      
        "fontSize":        "13px",
        "boxSizing":       "border-box",
        "fontWeight":      "600",
        "cursor":          "pointer",
        "fontFamily":      FONT,
        "lineHeight":      "36px",        # ← matches height to center text vertically
        
    }
    )

def styled_filter_summary(filters: list[str] | None) -> html.Div:
    """
    Displays active filters as a series of label: value rows.
    Number of rows depends on how many unique columns are in filters.
    """
    if not filters:
        return html.P("No filters applied", style={"color": TEXT_MUTED, "fontSize": "13px"})

    # Group values by column
    grouped = {}
    for selection in filters:
        col, val = selection.split(":", 1)
        grouped.setdefault(col, []).append(val)

    # Generate one row per column
    rows = []
    for col, values in grouped.items():
        rows.append(
            html.Div(style={
                "display":     "flex",
                "gap":         "8px",
                "alignItems":  "center",
                "padding":     "6px 0",
                "borderBottom": f"1px solid {BORDER}",
            }, children=[
                html.Span(f"{col}:", style={
                    "fontWeight":  "600",
                    "fontSize":    "12px",
                    "color":       ACCENT,
                    "minWidth":    "160px",
                    "fontFamily":  FONT,
                }),
                html.Span(", ".join(values), style={
                    "fontSize":  "13px",
                    "color":     TEXT_PRIMARY,
                    "fontFamily": FONT,
                }),
            ])
        )

    return html.Div(rows)

def styled_value_counts(df: pd.DataFrame, columns: list[str]) -> html.Div:
    """
    Auto-generates value count summaries for each column.
    """
    #remove summary row 
    if not df.empty:
        if df['project'].iloc[0]:
            df = df.iloc[1:]
    blocks = []
    for col in columns:
        #subject/sample (1:1) have too many values, so instead just
        #return the total count
        if col in ['subject','sample']:
            counts = len(df[col])
            blocks.append(html.Div(style={
                    "marginBottom": "20px",
                }, children=[
                    html.Span(col, style={
                        "fontSize":      "11px",
                        "fontWeight":    "600",
                        "letterSpacing": "0.08em",
                        "textTransform": "uppercase",
                        "color":         ACCENT,
                        "margin":        "0 0 8px 0",
                    }),
                    html.Span(f"    {counts}", style={
                            "fontSize":   "12px",
                            "color":      TEXT_MUTED,
                            "fontFamily": FONT,
                            "minWidth":   "80px",
                            "textAlign":  "right",
                        }),
                ]))
        else:
            counts = df[col].value_counts(dropna=False).reset_index()
            counts.columns = ["value", "count"]
            counts["pct"] = (counts["count"] / counts["count"].sum() * 100).round(1)

            # One row per unique value
            value_rows = []
            for _, row in counts.iterrows():
                value_rows.append(
                    html.Div(style={
                        "display":        "flex",
                        "justifyContent": "space-between",
                        "alignItems":     "center",
                        "padding":        "4px 0",
                        "gap":            "12px",
                    }, children=[
                        html.Span(str(row["value"]), style={
                            "fontSize":  "13px",
                            "color":     TEXT_PRIMARY,
                            "fontFamily": FONT,
                            "minWidth":  "100px",
                        }),
                        # Bar
                        html.Div(style={
                            "flexGrow":        "1",
                            "height":          "6px",
                            "borderRadius":    "3px",
                            "backgroundColor": BORDER,
                            "position":        "relative",
                        }, children=[
                            html.Div(style={
                                "width":           f"{row['pct']}%",
                                "height":          "100%",
                                "borderRadius":    "3px",
                                "backgroundColor": ACCENT,
                            })
                        ]),
                        html.Span(f"{row['count']} ({row['pct']}%)", style={
                            "fontSize":   "12px",
                            "color":      TEXT_MUTED,
                            "fontFamily": FONT,
                            "minWidth":   "80px",
                            "textAlign":  "right",
                        }),
                    ])
                )

            blocks.append(html.Div(style={
                "marginBottom": "20px",
            }, children=[
                html.P(col, style={
                    "fontSize":      "11px",
                    "fontWeight":    "600",
                    "letterSpacing": "0.08em",
                    "textTransform": "uppercase",
                    "color":         ACCENT,
                    "margin":        "0 0 8px 0",
                }),
                html.Div(value_rows)
            ]))
    return html.Div(blocks)

# ── App layout ─────────────────────────────────────────────────────────────────
app = dash.Dash(__name__, title="Teiko — Immune Profile Explorer")
 
app.layout = html.Div(style={
    "backgroundColor": GREY_BG,
    "minHeight":       "100vh",
    "fontFamily":      FONT,
    "padding":         "0",
    "margin":          "0",
}, children=[
 
    # ── Header bar ────────────────────────────────────────────────────────────
    html.Div(style={
        "backgroundColor": WHITE,
        "borderBottom":    f"3px solid {ACCENT}",
        "padding":         "18px 48px",
        "display":         "flex",
        "alignItems":      "center",
        "justifyContent":  "space-between",
        "marginBottom":    "32px",
        "boxShadow":       "0 1px 4px rgba(0,0,0,0.06)",
    }, children=[
        html.Div([
            html.Span("teiko", style={
                "fontSize":   "22px",
                "fontWeight": "700",
                "color":      ACCENT,
                "letterSpacing": "-0.02em",
            }),
            html.Span(" · melanoma cell count explorer", style={
                "fontSize": "14px",
                "color":    TEXT_MUTED,
                "marginLeft": "8px",
            }),
            html.Span(" ·  UNOFFICIAL - Nathan SCHOPPA TECHNICAL TEST", 
                style={
                    "fontSize": "14px",
                    "color":    TEXT_MUTED,
                    "marginLeft": "8px",
                }),
        ]),
        html.P("Clinical Trial Dashboard", style={
            "fontSize":  "12px",
            "color":     TEXT_MUTED,
            "margin":    "0",
            "fontWeight": "500",
        }),
    ]),
 
    # ── Main content ──────────────────────────────────────────────────────────
    html.Div(style={"padding": "0 48px 48px 48px", "maxWidth": "1400px", "margin": "0 auto"}, children=[
 
        # ── Section 1: Data overview table with filter ────────────────────────
        section_card([
            section_label("Section 1"),
            section_title("Data Overview: Cell Counts"),
            section_text('''
                This section contains a live-access record of cell count information, drawn from
                the database. To use, select any column from 'Sort by Column' to sort the dataset.
                Select any samples or cell types from 'Filter by Sample' and 'Filter by Cell Type'
                to filter the dataset. At any time, press the orange 'Download' button to download
                the current selection as a csv file. Use the arrows at the bottom of the table to
                look through the full dataset.
            '''),
            html.Div(style={"display": "flex", "justifyContent": "space-between",
                             "alignItems": "flex-start"}, children=[
                html.Div(style={"display": "flex", "gap": "16px"}, children=[
                    styled_dropdown(
                        "sample-column-sorter",
                        options=[{"label": col, "value": col} for col in cell_data.columns],
                        multi = False,
                        placeholder="Sort by Column…",
                    ),
                    styled_dropdown(
                        "sample-id-filter",
                        options=[{"label": p, "value": p} for p in sorted(cell_data["sample"].unique())],
                        placeholder="Filter by Sample…",
                    ),
                    styled_dropdown(
                        "sample-cell-type-filter",
                        options=[{"label": c, "value": c} for c in sorted(cell_data["population"].unique())],
                        placeholder="Filter by Cell Type…",
                    ),
                ]),
                html.Div(style={"display": "flex", "gap": "16px"}, children=[
                    styled_button(
                        'sample-download-button',
                        text='Download'
                        # style = {}
                    ),
                    dcc.Download(id='download-sampled-dataframe'),
                ]),
            ]),
            html.Div(style={'marginTop':'12px'},children = [
                styled_table("subsample-table", cell_data),
            ]),
        ]),
 
        # ── Section 2: Graph placeholder ──────────────────────────────────────
        section_card([
            section_label("Section 2"),
            section_title("Visualizations"),
            section_text('''
                This section contains boxplots comparing cell type proportions. Use the 'Choose Factor-By
                Column' dropdown (left) to choose a factor to compare over. Use the 'Narrow Down Conditions'
                dropdown (right) to select filters for the data. Note that some combinations of filters will
                result in only one level or no data selected; simply clear filters to resume. *If* chosen factors
                and filters have more than one level, a multiple t-test is performed per cell type (table 
                below). The table reports p-values, Holms adjusted p-values, and Benjamini-Hochberg False
                Discover Rate. Rows with Holms adjusted p-values < 0.05 are highlighted in red. Note that 
                the table will be empty if there are not enough levels to compare over.
            '''),
            subsection_title('Filters Applied'),
            html.Div(id="boxplot-filter-summary"),
            html.Div(style={"height": "16px"}),
            html.Div(style={"display": "flex", "alignItems": "center", "gap": "16px"}, children=[
                styled_dropdown(
                        "boxplot-factor-choice",
                        options=[{"label": col, "value": col} for col in ['condition',
                                                                          'treatment',
                                                                          'response',
                                                                          'sample_type',
                                                                          'time_from_treatment_start']],
                        multi = False,
                        placeholder="Choose Factor-By Column...",
                        value = 'response'
                    ),
                styled_dropdown(
                        "boxplot-focusing-choice",
                        options=[{"label": f'{col} : {val}', "value": f'{col}:{val}'} for col in 
                        ['condition','treatment','response','sample_type','time_from_treatment_start']
                                 for val in analysis_data[col].dropna().unique()],
                        multi = True,
                        placeholder="Narrow Down Conditions...",
                        value = ['treatment:miraclib','sample_type:PBMC','condition:melanoma']
                    ),
            ]),
            html.Div(style={'marginTop':'12px'},children = [
                dcc.Graph(id='boxplot-cell-type_proportions'),
            ]),
            subsection_title('',id='proportions-table-title'),
            html.Div(style={'marginTop':'12px'},children = [
                styled_table(
                    table_id='proportions-table',
                    columns=[
                        {"name": "Cell Type",   "id": "cell_type"},
                        {"name": "Comparison",  "id": "comparison"},
                        {"name": "p-value",     "id": "p-value"},
                        {"name": "Holms p-adj",       "id": "p-adj"},
                        {"name": "FDR BH",      "id": "FDR BH"},
                    ],
                    page_size=20,
                    style_data_conditional=[
                        # Highlight significant results
                        {
                            "if":                {"filter_query": "{p-adj} < 0.05"},
                            "backgroundColor":   ACCENT_LIGHT,
                            "fontWeight":        "600",
                        },
                    ],
                ),
            ]),
        ]),
 
        # ── Section 3: Cell count table with multi-select filter ───────────────
        section_card([
            section_label("Section 3"),
            section_title("Cell Count Data"),
            section_text('''
                This section contains further information about samples, including sample
                metadata and wide format cell counts or proportions. By default, the table
                displays sample-level counts and metadata. Use the 'Select Factors…' 
                dropdown (right) to select factors to pivot over. Us the 'Narrow Down
                Conditions' dropdown to filter the dataset. Note that some combinations
                will result in an empty dataset. Press the 'Toggle Proportions' button to
                switch the dataset between cell counts (or averaged cell counts) and
                cell proportions (or averaged cell proportions). At any time, press the orange 
                'Download' button to download the current selection as a csv file. Use the 
                arrows at the bottom of the table to look through the full dataset. \n
                         
                Below the table, there are 'Set Filter' buttons. Press to set a preset of
                factors and filters. The first filter corresponds to your inital questions
                (and is the app default). The second can be used to find the average number
                of B cells for Melanoma male responders at time=0. \n
                         
                Finally, at the bottom, the is a breakdown of unique factor values in the
                current selection. Note that it will not display unique subject nor sample
                ids.
                '''),
            subsection_title('Filters Applied'),
            html.Div(id="cell-analytics-filter-summary"),
            html.Div(style={"height": "16px"}),
            html.Div(style={"display": "flex", "justifyContent": "space-between",
                             "alignItems": "flex-start"}, children=[
                html.Div(style={"display": "flex", "gap": "16px"}, children=[
                    styled_dropdown(
                        dropdown_id="cell-analytics-column_selection",
                        options=[{"label": col, "value": col} for col in col_list],
                        placeholder="Select Factors…",
                        multi=True,   # multi-select for this section
                        value=col_list
                    ),
                    styled_dropdown(
                        dropdown_id="cell-analytics-focusing-choice",
                        options=[{"label": f'{col} : {val}', "value": f'{col}:{val}'} for col in 
                                    #selects all major categorical combos, except for 
                                    [_col for _col in col_list if _col not in ['subject','sample']]
                                    for val in analysis_data[col].dropna().unique()],
                        multi = True,
                        placeholder="Narrow Down Conditions...",
                        value = ['treatment:miraclib','sample_type:PBMC',
                                'condition:melanoma','time_from_treatment_start:0']
                    ),
                    styled_button(
                        buttonid='cell-analytics-toggle-proportion',
                        text='Toggle Proportions',
                        n_clicks=1
                    )
                ]),
                html.Div(style={"display": "flex", "gap": "16px"}, children=[
                    styled_button(
                        'cell-analytics-download-button',
                        text='Download'
                        # style = {}
                    ),
                    dcc.Download(id='download-cell-analytics-dataframe'),
                ]),
            ]),
            styled_table(
                table_id = "cell-analytics-table"
            ),
            subsection_title('Filter Presets'),
            html.Div(style={"display": "flex", "alignItems": "center", 
                            "gap":"16px","height":"36px"}, children=[
                styled_button(
                    'cell-analytics-filter-1',
                    text='Set Filters'
                ),
                subsection_text('1: Condition: Melanoma, Treatment: miraclib, Sample_type: PBMC, ' \
                'Time from treatment start:    0')
            ]),
            html.Div(style={"height": "16px"}),
            html.Div(style={"display": "flex", "alignItems": "center", 
                            "gap":"16px","height":"36px"}, children=[
                styled_button(
                    'cell-analytics-filter-2',
                    text='Set Filters'
                ),
                subsection_text('2: Condition: Melanoma,  Response: Yes, ' \
                    'Sex: Male, Time from treatment start:    0')
            ]),
            html.Div(style={"height": "16px"}),
            subsection_title('Sample Counts For Selected Factors'),
            html.Div(id="cell-analytics-value-counts"),
        ]),
 
    ]),
])
 
 
# ── Callbacks ──────────────────────────────────────────────────────────────────
 
@callback(
    Output("subsample-table", "data"),
    Input("sample-column-sorter", "value"),
    Input("sample-id-filter", "value"),
    Input("sample-cell-type-filter", "value"),
)
def filter_subject_table(column:str, sample: str, population: str) -> list[dict]:
    """Filter subject table by project and/or condition."""
    filtered = cell_data.copy()
    if sample:
        filtered = cell_data[cell_data["sample"].isin(sample)]
    if population:
        filtered = cell_data[cell_data["population"].isin(population)]
    if column:
        if column == 'proportion':
            filtered = cell_data.sort_values(by=column,ascending=False)
        else:   
            filtered = cell_data.sort_values(by=column)
    return filtered.to_dict("records")

@callback(
    Output("download-sampled-dataframe", "data"),
    Input("sample-download-button", "n_clicks"),
    State("subsample-table", "data"),
    prevent_initial_call=True,
)
def download_sample_data(n_clicks:int,data:list[dict]):
    return dcc.send_data_frame(pd.DataFrame(data).to_csv, "sample_data.csv") 


def _unzip_filters(_filters:list[str]):
    uz_filters = dict()
    for selection in _filters:
        _col, _val = selection.split(":", 1)   # ← the 1 prevents splitting on colons in the value
        if _col == 'time_from_treatment_start':
            _val = int(_val)
        uz_filters.setdefault(_col,[]).append(_val)
    return uz_filters

@app.callback(
    Output("boxplot-cell-type_proportions", "figure"),
    Output("proportions-table", "data"),
    Input("boxplot-focusing-choice", "value"),
    Input("boxplot-factor-choice", "value")
    )
def update_proportion_comparison(filters:list[str]|None, factor:str|None):
    filtered = analysis_data.copy()
    
    if factor == 'response':
        filtered = filtered[~filtered['response'].isna()]    
    if filters:
        uz_filters = _unzip_filters(filters)
        for col in uz_filters.keys():
            filtered = filtered[filtered[col].isin(uz_filters[col])]
    fig = generate_response_barchart(filtered,factor)
    if factor:
        _df = pairwise_test(filtered,factor)
        table_data = _df.to_dict("records") if not _df.empty else []
    else:
        table_data = []
    return fig, table_data

def generate_response_barchart(filtered, factor:str|None):
    fig = px.box(filtered, x='population', y='proportion', color = factor,points="outliers")
    return fig

@callback(
    Output("boxplot-filter-summary", "children"),
    Input("boxplot-focusing-choice", "value"),
)
def update_boxplot_filter_summary(filters):
    return styled_filter_summary(filters)

def pairwise_test(filtered:pd.DataFrame, factor:str):
    if not factor:
        return pd.DataFrame()
    rows = []
    levels = filtered[factor].dropna().unique()
    if len(levels) < 2:
        return pd.DataFrame()

    cell_types = filtered['population'].dropna().unique()
    
    for _type in cell_types:
        for pair in list(combinations(levels,2)):
            _x1 = filtered['proportion'][(filtered['population'] == _type)&(filtered[factor] == pair[0])]
            _x2 = filtered['proportion'][(filtered['population'] == _type)&(filtered[factor] == pair[1])]
            
            if len(_x1) == 0 or len(_x2) == 0:
                continue
            
            rows.append({
                'cell_type':_type,
                'comparison': f'{pair[0]} - {pair[1]}',
                'p-value':ttest_ind(_x1,_x2).pvalue
            })

    # if not rows:
    #     return pd.DataFrame()

    _df = pd.DataFrame(data=rows)
    _, _df['p-adj'], _, _ = multitest.multipletests(_df['p-value'],method='holm')
    _, _df['FDR BH'], _, _ = multitest.multipletests(_df['p-value'],method='fdr_bh')
    _df['p-value'] = _df['p-value'].map(lambda x: float(f"{x:.3g}"))
    _df['p-adj']   = _df['p-adj'].map(lambda x: float(f"{x:.3g}"))
    _df['FDR BH']  = _df['FDR BH'].map(lambda x: float(f"{x:.3g}"))
    return _df

@callback(
    Output('proportions-table-title','children'),
    Input("boxplot-factor-choice", "value")
)
def pairwise_title_update(response:str):
    return f'Multiple t-test Accross {response}'

@callback(
    Output("cell-analytics-table", "data"),
    Output("cell-analytics-table", "columns"),
    Output("cell-analytics-value-counts", "children"),
    Input("cell-analytics-column_selection", "value"),
    Input("cell-analytics-focusing-choice", "value"),
    Input('cell-analytics-toggle-proportion','n_clicks')
)
def filter_cell_table(response: list[str],filters:list[str],nclicks) -> list[dict]:
    """Filter cell count table by one or more cell types."""
    _col_list = [_col for _col in col_list if _col in response]
    if len(_col_list) < 1:
        _col_list.append('project')

    filtered = analysis_data.copy()
    if filters:
        uz_filters = _unzip_filters(filters)
        for col in uz_filters.keys():
            filtered = filtered[filtered[col].isin(uz_filters[col])]

    _cell_types = filtered['population'].dropna().unique().tolist()

    if filtered.empty:
        empty_msg = html.P(
            "No data matches the current filters.",
            style={"color": TEXT_MUTED, "fontSize": "13px"}
        )
        return [],[],empty_msg

    filtered = pd.pivot_table(filtered,
                    index=_col_list,
                    columns='population',
                    values='count',
                    aggfunc='mean',
                    margins=True)
    #reverts to a normal table
    filtered = filtered.reset_index()
    
    #filter options can result in an empty table, so do math only if not empty
    # Move last row to first
    filtered = pd.concat([filtered.iloc[[-1]], filtered.iloc[:-1]]).reset_index(drop=True)
    #column-level average comparison is unhelpful, but
    #we can easily derive the total #cells
    filtered['All'] = filtered['All']*int(len(_cell_types))
    filtered = filtered.rename(columns={'All':'total_count'})

    _cell_types_full = _cell_types + ['total_count']

    if nclicks%2 == 0:
        filtered[_cell_types_full] = filtered[_cell_types_full].div(filtered['total_count'],axis=0)

    filtered[_cell_types_full] = filtered[_cell_types_full].round(3)

    value_counts = styled_value_counts(filtered,_col_list)
    table_data = filtered.to_dict("records")
    colunms = [{'name': _col, 'id': str(_col)} for _col in filtered.columns]
    return table_data, colunms, value_counts

@callback(
    Output("download-cell-analytics-dataframe", "data"),
    Input("cell-analytics-download-button", "n_clicks"),
    State("cell-analytics-table", "data"),
    prevent_initial_call=True,
)
def download_cell_analytics_data(n_clicks:int,data:list[dict]):
    return dcc.send_data_frame(pd.DataFrame(data).to_csv, "cell_count_data.csv") 

@callback(
    Output("cell-analytics-filter-summary", "children"),
    Input("cell-analytics-focusing-choice", "value"),
)
def update_class_filter_summary(filters):
    return styled_filter_summary(filters)

@callback(
    Output("cell-analytics-column_selection", "value"),
    Output("cell-analytics-focusing-choice", "value"),
    Input('cell-analytics-filter-1','n_clicks'),
    Input('cell-analytics-filter-2','n_clicks'),
)
def update_cell_count_filters(filter1,filter2):
    ctx = dash.callback_context
    
    ##this function suppresses the initial call to 'update_class_filter_summary'
    #if we do this, it will trigger it anyways
    if not ctx.triggered or ctx.triggered[0]['value'] is None:
        column_selection = col_list
        filter_selection = ['treatment:miraclib','sample_type:PBMC',
                                'condition:melanoma','time_from_treatment_start:0']
        return column_selection, filter_selection
    
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]

    if triggered_id == 'cell-analytics-filter-1':
        column_selection = col_list
        filter_selection = ['treatment:miraclib','sample_type:PBMC',
                                'condition:melanoma','time_from_treatment_start:0']
        return column_selection, filter_selection
    if triggered_id == 'cell-analytics-filter-2':
        #everything but subject and sample
        column_selection = col_list
        filter_selection = ['condition:melanoma','response:yes',
                            'time_from_treatment_start:0','sex:M']
        return column_selection, filter_selection
    else:
        return dash.no_update, dash.no_update

# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=True)