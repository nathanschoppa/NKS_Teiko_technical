'''
AUTHOR: Nathaniel Schoppa
DATE: JULY 02 2026
 
Generates static output files for the Teiko pipeline.
Called by `make pipeline` after load_data.py.
 
Outputs:
    outputs/sample_data.csv             — Part 1: raw cell data
    outputs/proportions_boxplot.png     — Part 2: cell type proportions by response
    outputs/pairwise_results.csv        — Part 2: pairwise t-test results
    outputs/cell_analytics_summary.csv  — Part 3: pivot table summary
'''
from pathlib import Path
import pandas as pd
import plotly.express as px
from scipy.stats import ttest_ind
from statsmodels.stats import multitest
from itertools import combinations
from teiko_database import _db_connection
import logging
 
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)
 
# ── Config ─────────────────────────────────────────────────────────────────────
DB_PATH    = Path('teiko.db')
OUTPUT_DIR = Path('outputs')
OUTPUT_DIR.mkdir(exist_ok=True)
 
# ── Default filter settings (matching dashboard defaults) ──────────────────────
PART2_FACTOR  = 'response'
PART2_FILTERS = {
    'treatment':  ['miraclib'],
    'sample_type': ['PBMC'],
    'condition':  ['melanoma'],
}
 
PART3_COLUMNS = ['project', 'subject', 'condition', 'age', 'sex',
                 'treatment', 'response', 'sample_type',
                 'time_from_treatment_start']
PART3_FILTERS = {
    'treatment':                 ['miraclib'],
    'sample_type':               ['PBMC'],
    'condition':                 ['melanoma'],
    'time_from_treatment_start': [0],
}
 
# ── Load data from database ────────────────────────────────────────────────────
def load_analysis_data(db_path: Path) -> pd.DataFrame:
    '''Pull joined analysis data from the database.'''
    with _db_connection(db_path) as conn:
        df = pd.read_sql('''SELECT sub.project as project,
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
        df['response'] = df['response'].fillna('NA')
        df = pd.merge(df,load_cell_data(DB_PATH),on='sample')
    return df
 
 
def load_cell_data(db_path: Path) -> pd.DataFrame:
    '''Pull raw cell count data for Part 1 output.'''
    with _db_connection(db_path) as conn:
        df = pd.read_sql('''SELECT sample as sample,
                                cell_type as population, 
                                cell_count as count 
                            FROM CELL_COUNT 
                            ORDER BY sample''',conn)
        df['total_count'] = df.groupby('sample')['count'].transform('sum')
        df['proportion'] = (df['count'] / df['total_count']).round(4)
        df = df[['sample','population','total_count','count','proportion']]
    return df
 
 
# ── Helper ─────────────────────────────────────────────────────────────────────
def _apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    '''Apply a dict of {column: [values]} filters to a DataFrame.'''
    filtered = df.copy()
    for col, vals in filters.items():
        filtered = filtered[filtered[col].isin(vals)]
    return filtered
 
 
# ── Part 1: raw sample data ────────────────────────────────────────────────────
def save_sample_data(db_path: Path):
    logger.info('Part 1 — saving sample data...')
    df = load_cell_data(db_path)
    out = OUTPUT_DIR / 'sample_data.csv'
    df.to_csv(out, index=False)
    logger.info(f'Saved {len(df)} rows to {out}')
 
 
# ── Part 2: boxplot + pairwise test ───────────────────────────────────────────
def generate_response_barchart(filtered: pd.DataFrame,
                                factor: str | None):
    return px.box(
        filtered,
        x='population',
        y='proportion',
        color=factor,
        points='outliers',
        title=f'Cell Type Proportions by {factor.title() if factor else ""}',
    )
 
 
def pairwise_test(filtered: pd.DataFrame, factor: str) -> pd.DataFrame:
    if not factor:
        return pd.DataFrame()
 
    levels = filtered[factor].dropna().unique()
    cell_types = filtered['population'].dropna().unique()
 
    if len(levels) < 2:
        return pd.DataFrame()
 
    rows = []
    for _type in cell_types:
        for pair in combinations(levels, 2):
            _x1 = filtered['proportion'][
                (filtered['population'] == _type) & (filtered[factor] == pair[0])
            ]
            _x2 = filtered['proportion'][
                (filtered['population'] == _type) & (filtered[factor] == pair[1])
            ]
            if len(_x1) == 0 or len(_x2) == 0:
                continue
            rows.append({
                'cell_type':  _type,
                'comparison': f'{pair[0]} - {pair[1]}',
                'p-value':    ttest_ind(_x1, _x2).pvalue,
            })
 
    if not rows:
        return pd.DataFrame()
 
    _df = pd.DataFrame(rows)
    _, _df['p-adj'],  _, _ = multitest.multipletests(_df['p-value'], method='holm')
    _, _df['FDR BH'], _, _ = multitest.multipletests(_df['p-value'], method='fdr_bh')
    _df['p-value'] = _df['p-value'].map(lambda x: float(f'{x:.3g}'))
    _df['p-adj']   = _df['p-adj'].map(lambda x: float(f'{x:.3g}'))
    _df['FDR BH']  = _df['FDR BH'].map(lambda x: float(f'{x:.3g}'))
    return _df
 
 
def save_part2(analysis_data: pd.DataFrame):
    logger.info('Part 2 — generating boxplot and pairwise results...')
 
    # Apply filters
    filtered = analysis_data.copy()
    filtered = filtered[~filtered['response'].isna()]
    filtered = _apply_filters(filtered, PART2_FILTERS)
 
    # Boxplot
    fig = generate_response_barchart(filtered, PART2_FACTOR)
    plot_out = OUTPUT_DIR / 'proportions_boxplot.png'
    fig.write_image(plot_out)
    logger.info(f'Saved plot to {plot_out}')
 
    # Pairwise test
    _df = pairwise_test(filtered, PART2_FACTOR)
    if not _df.empty:
        csv_out = OUTPUT_DIR / 'pairwise_results.csv'
        _df.to_csv(csv_out, index=False)
        logger.info(f'Saved {len(_df)} rows to {csv_out}')
    else:
        logger.warning('Part 2 — pairwise test returned no results')
 
 
# ── Part 3: cell analytics pivot table ────────────────────────────────────────
def save_part3(analysis_data: pd.DataFrame):
    logger.info('Part 3 — generating cell analytics summary...')
 
    # Apply filters
    filtered = _apply_filters(analysis_data, PART3_FILTERS)
 
    if filtered.empty:
        logger.warning('Part 3 — no data after filtering, skipping')
        return
 
    _cell_types = filtered['population'].dropna().unique().tolist()
    _col_list   = [c for c in PART3_COLUMNS if c in filtered.columns]
 
    # Pivot table — matching filter_cell_table logic exactly
    pivot = pd.pivot_table(
        filtered,
        index=_col_list,
        columns='population',
        values='count',
        aggfunc='mean',
        margins=True,
    ).reset_index()
 
    pivot.columns.name = None
 
    # Move margin row to top
    pivot = pd.concat(
        [pivot.iloc[[-1]], pivot.iloc[:-1]]
    ).reset_index(drop=True)
 
    # Convert All column to total_count
    pivot['All'] = pivot['All'] * int(len(_cell_types))
    pivot = pivot.rename(columns={'All': 'total_count'})
 
    # Round
    _cell_types_full = _cell_types + ['total_count']
    pivot[_cell_types_full] = pivot[_cell_types_full].round(3)
 
    out = OUTPUT_DIR / 'cell_analytics_summary.csv'
    pivot.to_csv(out, index=False)
    logger.info(f'Saved {len(pivot)} rows to {out}')
 
 
# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    logger.info('Loading analysis data from database...')
    analysis_data = load_analysis_data(DB_PATH)
    logger.info(f'Loaded {len(analysis_data)} rows')
 
    save_sample_data(DB_PATH)
    save_part2(analysis_data)
    save_part3(analysis_data)
 
    logger.info(f'All outputs saved to {OUTPUT_DIR}/')