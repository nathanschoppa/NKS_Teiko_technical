'''
AUTHOR: Nathaniel Schoppa
DATE: JULY 02 2026

Integration and unit tests for teiko_database.py
Run with: pytest tests/
'''
import pytest
import sqlite3
import pandas as pd
import os
from pathlib import Path
from teiko_database import (
    _db_connection,
    _init_db_tables,
    _write_insert,
    _insert_value_into_table,
    init_db,
    insert_csv_into_db,
)

# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    '''Provides a fresh temporary database path for each test.'''
    return tmp_path / 'test_teiko.db'


@pytest.fixture
def initialized_db(db_path: Path) -> Path:
    '''Provides a path to a fully initialized (tables created) database.'''
    init_db(db_path)
    return db_path


@pytest.fixture
def conn(initialized_db: Path):
    '''Provides a live connection to an initialized database.'''
    connection = sqlite3.connect(initialized_db)
    connection.execute('PRAGMA foreign_keys = ON')
    yield connection
    connection.close()


@pytest.fixture
def minimal_df() -> pd.DataFrame:
    '''
    Minimal valid DataFrame matching the expected cell-count.csv format.
    Two subjects, two samples, two cell types each.
    '''
    return pd.DataFrame({
        'project':                    ['prj1', 'prj1', 'prj1', 'prj1'],
        'subject':                    ['sbj001', 'sbj001', 'sbj002', 'sbj002'],
        'age':                        [34, 34, 45, 45],
        'sex':                        ['M', 'M', 'F', 'F'],
        'condition':                  ['melanoma', 'melanoma', 'healthy', 'healthy'],
        'treatment':                  ['miraclib', 'miraclib', 'none', 'none'],
        'response':                   ['yes', 'yes', None, None],
        'sample':                     ['sample001', 'sample001', 'sample002', 'sample002'],
        'sample_type':                ['PBMC', 'PBMC', 'PBMC', 'PBMC'],
        'time_from_treatment_start':  [0, 0, 7, 7],
        'b_cell':                     [1200, 1200, 980, 980],
        'cd8_t_cell':                 [3100, 3100, 2400, 2400],
        'cd4_t_cell':                 [4500, 4500, 3100, 3100],
        'nk_cell':                    [1300, 1300, 900, 900],
        'monocyte':                   [800, 800, 600, 600],
    })


# ── _db_connection tests ───────────────────────────────────────────────────────

class TestDbConnection:

    def test_creates_database_file(self, db_path: Path):
        '''Connection should create the database file if it does not exist.'''
        assert not db_path.exists()
        with _db_connection(db_path) as conn:
            pass
        assert db_path.exists()

    def test_yields_connection(self, db_path: Path):
        '''Context manager should yield a valid sqlite3 Connection.'''
        with _db_connection(db_path) as conn:
            assert isinstance(conn, sqlite3.Connection)

    def test_foreign_keys_enabled(self, db_path: Path):
        '''PRAGMA foreign_keys should be ON inside the context.'''
        with _db_connection(db_path) as conn:
            result = conn.execute('PRAGMA foreign_keys').fetchone()
            assert result[0] == 1

    def test_connection_closed_after_context(self, db_path: Path):
        '''Connection should be closed after the with block exits.'''
        with _db_connection(db_path) as conn:
            captured = conn
        with pytest.raises(Exception):
            captured.execute('SELECT 1')

    def test_rollback_on_error(self, db_path: Path):
        '''An exception inside the context should trigger a rollback.'''
        with _db_connection(db_path) as conn:
            conn.execute('CREATE TABLE test_rollback (id INTEGER PRIMARY KEY)')
        
        with pytest.raises(sqlite3.Error):
            with _db_connection(db_path) as conn:
                conn.execute('INSERT INTO test_rollback VALUES (1)')
                raise sqlite3.Error('Simulated error')

        # Row should not have been committed
        with _db_connection(db_path) as conn:
            result = conn.execute('SELECT COUNT(*) FROM test_rollback').fetchone()
            assert result[0] == 0


# ── _init_db_tables tests ──────────────────────────────────────────────────────

class TestInitDbTables:

    EXPECTED_TABLES = {
        'PROJECT', 'SEX', 'CONDITION', 'TREATMENT', 'RESPONSE',
        'SUBJECT', 'SAMPLE_TYPE', 'SAMPLE', 'CELL_TYPE', 'CELL_COUNT'
    }

    def test_all_tables_created(self, conn: sqlite3.Connection):
        '''All expected tables should exist after initialization.'''
        result = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        tables = {row[0].upper() for row in result}
        assert self.EXPECTED_TABLES.issubset(tables)

    def test_idempotent(self, initialized_db: Path):
        '''Calling _init_db_tables twice should not raise an error.'''
        with _db_connection(initialized_db) as conn:
            _init_db_tables(conn)   # second call — should be safe

    def test_subject_check_constraint(self, conn: sqlite3.Connection):
        '''SUBJECT should reject a response without a treatment.'''
        conn.execute("INSERT INTO PROJECT VALUES ('prj1')")
        conn.execute("INSERT INTO SEX VALUES ('M')")
        conn.execute("INSERT INTO RESPONSE VALUES ('yes')")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("""
                INSERT INTO SUBJECT (subject, Project, age, Sex, Treatment, Response)
                VALUES ('sbj001', 'prj1', 34, 'M', NULL, 'yes')
            """)

    def test_subject_fk_project(self, conn: sqlite3.Connection):
        '''SUBJECT should reject a reference to a non-existent project.'''
        conn.execute("INSERT INTO SEX VALUES ('M')")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("""
                INSERT INTO SUBJECT (subject, Project, age, Sex)
                VALUES ('sbj001', 'nonexistent_project', 34, 'M')
            """)

    def test_cell_count_composite_pk(self, conn: sqlite3.Connection):
        '''CELL_COUNT should reject duplicate (sample, cell_type) pairs.'''
        conn.execute("INSERT INTO PROJECT VALUES ('prj1')")
        conn.execute("INSERT INTO SEX VALUES ('M')")
        conn.execute("INSERT INTO SUBJECT (subject, Project, Sex) VALUES ('sbj001', 'prj1', 'M')")
        conn.execute("INSERT INTO SAMPLE_TYPE VALUES ('PBMC')")
        conn.execute("INSERT INTO SAMPLE VALUES ('s001', 'sbj001', 'PBMC', 0)")
        conn.execute("INSERT INTO CELL_TYPE VALUES ('b_cell')")
        conn.execute("INSERT INTO CELL_COUNT VALUES ('s001', 'b_cell', 1000)")
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO CELL_COUNT VALUES ('s001', 'b_cell', 2000)")


# ── _write_insert tests ────────────────────────────────────────────────────────

class TestWriteInsert:

    def test_single_column(self):
        sql = _write_insert('PROJECT', 1, ['project'])
        assert sql == 'INSERT INTO PROJECT (project) VALUES (?)'

    def test_multiple_columns(self):
        sql = _write_insert('SUBJECT', 1, ['subject', 'project', 'age'])
        assert sql == 'INSERT INTO SUBJECT (subject, project, age) VALUES (?,?,?)'

    def test_raises_over_999(self):
        with pytest.raises(ValueError, match='999'):
            _write_insert('PROJECT', 1000, ['project'])

    def test_placeholder_count_matches_columns(self):
        columns = ['a', 'b', 'c', 'd', 'e']
        sql = _write_insert('TEST', 1, columns)
        placeholder_count = sql.count('?')
        assert placeholder_count == len(columns)


# ── _insert_value_into_table tests ────────────────────────────────────────────

class TestInsertValueIntoTable:

    def test_insert_list_of_strings(self, conn: sqlite3.Connection):
        '''Should correctly insert a flat list of strings.'''
        _insert_value_into_table(conn, 'PROJECT', ['prj1', 'prj2'], ['project'])
        result = conn.execute('SELECT project FROM PROJECT').fetchall()
        projects = [row[0] for row in result]
        assert 'prj1' in projects
        assert 'prj2' in projects

    def test_insert_series(self, conn: sqlite3.Connection):
        '''Should correctly insert a pandas Series.'''
        s = pd.Series(['melanoma', 'healthy'])
        _insert_value_into_table(conn, 'CONDITION', s, ['condition'])
        result = conn.execute('SELECT condition FROM CONDITION').fetchall()
        conditions = [row[0] for row in result]
        assert 'melanoma' in conditions
        assert 'healthy' in conditions

    def test_insert_dataframe(self, conn: sqlite3.Connection):
        '''Should correctly insert a DataFrame with multiple columns.'''
        conn.execute("INSERT INTO PROJECT VALUES ('prj1')")
        conn.commit()
        df = pd.DataFrame({'project': ['prj1', 'prj1'], 'subject': ['sbj001', 'sbj002'],
                           'age': [34, 45], 'sex': ['M', 'F'],
                           'condition': [None, None], 'treatment': [None, None],
                           'response': [None, None]})
        conn.execute("INSERT INTO SEX VALUES ('M')")
        conn.execute("INSERT INTO SEX VALUES ('F')")
        conn.commit()
        _insert_value_into_table(conn, 'SUBJECT', df,
                                  ['project', 'subject', 'age', 'sex',
                                   'condition', 'treatment', 'response'])
        result = conn.execute('SELECT COUNT(*) FROM SUBJECT').fetchone()
        assert result[0] == 2

    def test_raises_on_empty_columns(self, conn: sqlite3.Connection):
        with pytest.raises(ValueError, match='columns list cannot be empty'):
            _insert_value_into_table(conn, 'PROJECT', ['prj1'], [])

    def test_raises_on_empty_table(self, conn: sqlite3.Connection):
        with pytest.raises(ValueError, match='table name cannot be empty'):
            _insert_value_into_table(conn, '', ['prj1'], ['project'])

    def test_raises_on_batch_less_than_1(self, conn: sqlite3.Connection):
        with pytest.raises(ValueError, match='batch must be at least 1'):
            _insert_value_into_table(conn, 'PROJECT', ['prj1'], ['project'], batch=0)

    def test_raises_on_batch_exceeds_max(self, conn: sqlite3.Connection):
        with pytest.raises(ValueError, match='999'):
            _insert_value_into_table(conn, 'PROJECT', ['prj1'], ['project'], batch=1000)

    def test_raises_on_unsupported_type(self, conn: sqlite3.Connection):
        with pytest.raises(TypeError, match='Unsupported values type'):
            _insert_value_into_table(conn, 'PROJECT', {'key': 'val'}, ['project'])

    def test_batching_inserts_all_rows(self, conn: sqlite3.Connection):
        '''All rows should be inserted even when batching splits them.'''
        values = [f'prj{i}' for i in range(10)]
        _insert_value_into_table(conn, 'PROJECT', values, ['project'], batch=3)
        result = conn.execute('SELECT COUNT(*) FROM PROJECT').fetchone()
        assert result[0] == 10


# ── insert_csv_into_db integration tests ──────────────────────────────────────

class TestInsertCsvIntoDb:

    def test_projects_inserted(self, initialized_db: Path, minimal_df: pd.DataFrame):
        insert_csv_into_db(initialized_db, minimal_df)
        with _db_connection(initialized_db) as conn:
            result = conn.execute('SELECT project FROM PROJECT').fetchall()
            projects = [row[0] for row in result]
        assert 'prj1' in projects

    def test_subjects_inserted(self, initialized_db: Path, minimal_df: pd.DataFrame):
        insert_csv_into_db(initialized_db, minimal_df)
        with _db_connection(initialized_db) as conn:
            result = conn.execute('SELECT COUNT(*) FROM SUBJECT').fetchone()
        assert result[0] == 2   # two unique subjects

    def test_samples_inserted(self, initialized_db: Path, minimal_df: pd.DataFrame):
        insert_csv_into_db(initialized_db, minimal_df)
        with _db_connection(initialized_db) as conn:
            result = conn.execute('SELECT COUNT(*) FROM SAMPLE').fetchone()
        assert result[0] == 2   # two unique samples

    def test_cell_counts_inserted(self, initialized_db: Path, minimal_df: pd.DataFrame):
        insert_csv_into_db(initialized_db, minimal_df)
        with _db_connection(initialized_db) as conn:
            result = conn.execute('SELECT COUNT(*) FROM CELL_COUNT').fetchone()
        # 2 samples × 5 cell types = 10 rows
        assert result[0] == 10

    def test_cell_types_inserted(self, initialized_db: Path, minimal_df: pd.DataFrame):
        insert_csv_into_db(initialized_db, minimal_df)
        with _db_connection(initialized_db) as conn:
            result = conn.execute('SELECT cell_type FROM CELL_TYPE').fetchall()
            cell_types = [row[0] for row in result]
        for ct in ['b_cell', 'cd8_t_cell', 'cd4_t_cell', 'nk_cell', 'monocyte']:
            assert ct in cell_types

    def test_idempotent_insert(self, initialized_db: Path, minimal_df: pd.DataFrame):
        '''Inserting the same CSV twice should not create duplicate rows.'''
        insert_csv_into_db(initialized_db, minimal_df)
        insert_csv_into_db(initialized_db, minimal_df)
        with _db_connection(initialized_db) as conn:
            result = conn.execute('SELECT COUNT(*) FROM SUBJECT').fetchone()
        assert result[0] == 2   # still 2, not 4

    def test_cell_count_values_correct(self, initialized_db: Path, minimal_df: pd.DataFrame):
        '''Cell count values should match the input DataFrame.'''
        insert_csv_into_db(initialized_db, minimal_df)
        with _db_connection(initialized_db) as conn:
            result = conn.execute('''
                SELECT cell_count FROM CELL_COUNT
                WHERE Sample = 'sample001' AND Cell_type = 'b_cell'
            ''').fetchone()
        assert result[0] == 1200

    def test_null_response_allowed(self, initialized_db: Path, minimal_df: pd.DataFrame):
        '''Subjects with no response (None) should be inserted without error.'''
        insert_csv_into_db(initialized_db, minimal_df)
        with _db_connection(initialized_db) as conn:
            result = conn.execute('''
                SELECT Response FROM SUBJECT WHERE subject = 'sbj002'
            ''').fetchone()
        assert result[0] is None

    def test_reference_tables_populated(self, initialized_db: Path, minimal_df: pd.DataFrame):
        '''All reference tables should be populated from CSV values.'''
        insert_csv_into_db(initialized_db, minimal_df)
        with _db_connection(initialized_db) as conn:
            assert conn.execute('SELECT COUNT(*) FROM CONDITION').fetchone()[0] > 0
            assert conn.execute('SELECT COUNT(*) FROM TREATMENT').fetchone()[0] > 0
            assert conn.execute('SELECT COUNT(*) FROM SAMPLE_TYPE').fetchone()[0] > 0
            assert conn.execute('SELECT COUNT(*) FROM SEX').fetchone()[0] > 0


# ── init_db tests ──────────────────────────────────────────────────────────────

class TestInitDb:

    def test_creates_db_file(self, db_path: Path):
        init_db(db_path)
        assert db_path.exists()

    def test_tables_exist_after_init(self, db_path: Path):
        init_db(db_path)
        with _db_connection(db_path) as conn:
            result = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        assert len(result) > 0

    def test_idempotent(self, db_path: Path):
        '''Calling init_db twice should not raise an error.'''
        init_db(db_path)
        init_db(db_path)   # second call — safe
