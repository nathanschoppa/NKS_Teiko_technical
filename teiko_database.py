'''
AUTHOR: Nathaniel Schoppa
DATE: JULY 02 2026

Scripts for creating teiko database, uploading data,
and pulling data
'''
from contextlib import contextmanager
import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path 
import logging

logger = logging.getLogger(__name__)

@contextmanager
def _db_connection(db_path:str|Path):
    '''
    Context manager managing database connection

    Pass path to database.

    Us as:
    with _db_connection(db_path) as conn:
        <code>
    '''
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        conn.execute('PRAGMA foreign_keys = ON')
        logger.info(f'Connected to database: {db_path}')
        yield conn
        conn.commit()
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        print(f'Database error: {e}')
        raise
    finally:
        if conn:
            conn.close()
            logger.info(f'Connection closed to database: {db_path}')

def _init_db_tables(_conn:sqlite3.Connection):
    '''
    Function creates default tables for the supplied database 
    according the design scheme. See README.md for ERD

    Called either for initial database creation or database repair

    Returns: nothing
    '''
    cursor = _conn.cursor()
    
    #create major entity PROJECT
    cursor.execute('''
            CREATE TABLE IF NOT EXISTS PROJECT (
                project TEXT NOT NULL,
                PRIMARY KEY (project)
            )
        ''')
    
    ###create reference entities for SUBJECT
    #subject sex
    cursor.execute('''
            CREATE TABLE IF NOT EXISTS SEX (
                sex INT NOT NULL,
                PRIMARY KEY (sex)
            )
        ''')
    #subject condition (e.g. healthy, has melanoma)
    cursor.execute('''
            CREATE TABLE IF NOT EXISTS CONDITION (
                condition TEXT NOT NULL,
                PRIMARY KEY (condition)
            )
        ''')
    #subject treatment (none, some drug)
    cursor.execute('''
            CREATE TABLE IF NOT EXISTS TREATMENT (
                treatment TEXT NOT NULL,
                PRIMARY KEY (treatment)
            )
        ''')
    #response to treatment
    cursor.execute('''
            CREATE TABLE IF NOT EXISTS RESPONSE (
                response TEXT NOT NULL,
                PRIMARY KEY (response)
            )
        ''')
    
    ###create the subject entity
    #check ensure that any subject must have a treatment 
    #to have a response
    cursor.execute('''
            CREATE TABLE IF NOT EXISTS SUBJECT (
                subject TEXT NOT NULL,
                Project TEXT NOT NULL,
                age INTEGER,
                Sex TEXT NOT NULL,
                Condition TEXT NULL,
                Treatment TEXT NULL,
                Response TEXT NULL,
                PRIMARY KEY (subject),
        
                FOREIGN KEY (Project) REFERENCES PROJECT(project),
                FOREIGN KEY (Sex) REFERENCES SEX(sex),
                FOREIGN KEY (Condition) REFERENCES CONDITION(condition),
                FOREIGN KEY (Treatment) REFERENCES TREATMENT(treatment),
                FOREIGN KEY (Response) REFERENCES RESPONSE(response),
                
                CHECK (treatment IS NOT NULL OR response IS NULL)
            )
        ''')
    
    #Sample reference entity
    #sample sample type
    cursor.execute('''
            CREATE TABLE IF NOT EXISTS SAMPLE_TYPE (
                sample_type TEXT NOT NULL,
                PRIMARY KEY (sample_type)
            )
        ''')
    
    #Sample entity
    cursor.execute('''
            CREATE TABLE IF NOT EXISTS SAMPLE (
                sample TEXT NOT NULL,
                Subject TEXT NOT NULL,
                Sample_type TEXT NOT NULL,
                time_from_treatment_start INTEGER,
                PRIMARY KEY (sample),
                   
                Foreign Key (Subject) REFERENCES SUBJECT(subject)
                Foreign Key (Sample_type) REFERENCES SAMPLE_TYPE(Sample_type)
            )
        ''')
    
    #Cell count reference entity
    cursor.execute('''
            CREATE TABLE IF NOT EXISTS CELL_TYPE (
                cell_type TEXT NOT NULL,
                PRIMARY KEY (cell_type)
            )
        ''')
    
    cursor.execute('''
            CREATE TABLE IF NOT EXISTS CELL_COUNT (
                Sample TEXT NOT NULL,
                Cell_type TEXT NOT NULL,
                cell_count INTEGER NOT NULL,
                PRIMARY KEY (Sample,Cell_type),
                   
                Foreign Key (Sample) REFERENCES SAMPLE(sample),
                Foreign Key (Cell_type) REFERENCES CELL_TYPE(cell_type)
            )
        ''')
    #redundant but important
    _conn.commit()
    cursor.close()

def _write_insert(table:str,
                val_num:int,
                columns:list[str]):
    '''
    Internal function is a quick wrapper that generates a SQL insert
    command with wildcards for values
    '''
    if val_num > 999:
        raise ValueError(f'Cannot insert more than 999 rows!')
    
    column_clause = ', '.join(columns)
    placeholders  = ','.join('?' * len(columns))
    single_row    = f'({placeholders})'
    return f'INSERT INTO {table} ({column_clause}) VALUES {single_row}'


def _insert_value_into_table(_conn:sqlite3.Connection,
                      table:str,
                      values:list[str]|list[list[str]]|pd.Series|pd.DataFrame,
                      columns:list[str],
                      batch = 25):
    '''
    Internal function takes either a list of values and inserts them into
    columns in the table. Batches in 25
    '''
    ###catch invalid entries
    if batch < 1:
        raise ValueError(f'batch must be at least 1, got {batch}')
    
    if not columns:
        raise ValueError('columns list cannot be empty') 
    max_batch = 999 // len(columns)
    if batch > max_batch:
        raise ValueError(f'batch must be at less than 999/'
                         f'(number of columns), got {batch} > {max_batch}')
    if not table:
        raise ValueError('table name cannot be empty')
    
    #if passed a single string, wrap to make processible
    if isinstance(columns,str):
        columns = [columns]

    #Normalize to list of tuples upfront -> list[str]|list[list[str]]
    if isinstance(values, pd.DataFrame):
    #Each row becomes a flat tuple of scalar values
        values = [tuple(row) for row in values[columns].itertuples(index=False)]
    elif isinstance(values, pd.Series):
        values = [(v,) for v in values.tolist()]
    elif isinstance(values, list):
        if values and not isinstance(values[0], (list, tuple)):
            values = [(v,) for v in values]
        else:
            values = [tuple(v) for v in values]
    else:
        raise TypeError(f'Unsupported values type: {type(values)}')

    #split indexes into *batch*-sized fragments and add last index
    if batch > 1:
        inx_split = [i for i in range(0,len(values),batch)] + [len(values)]
    else:
        inx_split = [i for i in range(len(values))]
    
    #iterate through index pairs to splice value list
    for i in range(len(inx_split)-1):
        split_dif = inx_split[i+1]-inx_split[i]
        #NOTE: sql_command is an INSERT... not INSERT OR IGNORE
        #the goal is to catch any failed uploads
        sql_cmd = _write_insert(table,split_dif,columns)
    
        batch_values = values[inx_split[i]:inx_split[i+1]]
        insert_val = tuple(_val for _val in batch_values)
        try:
            _conn.executemany(sql_cmd,insert_val)
            #commiting code will happen after all insertions!
            #this prevents a partial upload if there's a critical issue
            logger.info(f'Inserted {len(insert_val)} records into {table}')
        
        #violated constraint, such as UNIQUE if already in the table
        except sqlite3.IntegrityError as e:
            logger.warning(f'Skipped {len(insert_val)} records into {table} '
                           f'— constraint violation (likely duplicates): {e}')
            #NOT raise
            #currently want it to skip any values for which there's a duplicate upload
        
        #duplication or other insert failure
        except sqlite3.OperationalError as e:
            logger.error(f'Operational error inserting into {table}: {e}')
            logger.info(f'Failed to inserted {len(insert_val)} records into {table}')
            raise  

def insert_csv_into_db(db_path:str|Path,df:pd.DataFrame):
    '''
    Function takes a csv in the format 'cell_count.csv' (see files).
    This is currently a hardcoded operation
    This format has the following columns:
    ['project', 'subject', 'condition', 'age', 'sex', 'treatment',
       'response', 'sample', 'sample_type', 'time_from_treatment_start',
       'b_cell', 'cd8_t_cell', 'cd4_t_cell', 'nk_cell', 'monocyte']

    To avoid errors, data will be inserted in the following order
       
    ---Reference entities
    sex             -->SEX
    condition       -->CONDITION
    treatment       -->TREATMENT
    response        -->RESPONSE
    sample_type     -->SAMPLE_TYPE
    b_cell, cd8_t_cell, cd4_t_cell, nk_cell, monocyte-->CELL_TYPE
    ---Main entities in descending heiarchy
    project         -->PROJECT
    subject, age, sex, condition, treatment, response, project-->Subject
    sample, subject, sample_type,time_from_treatment_start--> Sample
    sample, cell_type, cell_count-->CELL_COUNT
    '''
    with _db_connection(db_path) as _conn:
        ###Master list of cell types. Used for CELL_TYPE and CELL_COUNT
        #this can be expanded in the future
        cell_types = ['b_cell', 'cd8_t_cell', 'cd4_t_cell', 'nk_cell', 'monocyte']
        
        ###handle reference columns AND projects
        #ASSUMING .csv has correct values, insert any new reference values found in .csv
        ref_cols = ['sex','condition', 'treatment','response','sample_type','cell_type','project']
        for col in ref_cols:
            #always true now, but future-proofing
            if col in df.columns or col =='cell_type':
                if col == 'cell_type':
                    values = cell_types.copy()
                else:   
                    values:pd.Series = df[col].unique()
                
                #takes advantage that table key value has same name as table
                #to retrieve all values already in the dataset
                #then unpack (otherwise in form [('VAL1',),...])
                db_values = _conn.execute(f'SELECT DISTINCT {col} from {col}').fetchall()
                db_values = [row[0] for row in db_values]
                
                unique_val = []
                #O(n^2), but potentially only bad for PROJECT
                for val in values:
                    if val not in db_values:
                        unique_val.append(val)
                print(f'Info: type {type(unique_val)}: {unique_val}')
                _insert_value_into_table(_conn,table=col,values=unique_val,columns=[col])

        ###insert into subject
        subject_cols = ['project', 'subject', 'age', 'sex','condition', 'treatment','response']
        subject_values:pd.DataFrame = df[subject_cols]
        #there SHOULDN'T be any, but nice to check
        subject_values = subject_values.drop_duplicates()
        _insert_value_into_table(_conn,table='SUBJECT',values=subject_values,columns=subject_cols)

        ###insert into sample
        sample_cols = ['sample', 'subject', 'sample_type', 'time_from_treatment_start']
        sample_values:pd.DataFrame = df[sample_cols]
        #there SHOULDN'T be any, but nice to check
        sample_values = sample_values.drop_duplicates()
        _insert_value_into_table(_conn,table='SAMPLE',values=sample_values,columns=sample_cols)
        
        ###inserting into cell_counts
        #transforming from wide to long data
        for cell_type in cell_types:
            if cell_type in df.columns:
                df_cell_count = df[['sample',cell_type]]
                #fill a column with cell_type identifier
                df_cell_count['cell_type'] = cell_type
                df_cell_count = df_cell_count.rename(columns={cell_type:'cell_count'})
                _insert_value_into_table(_conn,table='CELL_COUNT',values=df_cell_count,columns=['sample','cell_type','cell_count'])


def init_db(db_path:str|Path='data/teiko.db'):
    '''
    Function initializes database at db_path according to
    the design scheme. See README.md for ERD
    --calls table creation
    '''
    with _db_connection(db_path) as conn:
        _init_db_tables(conn)

if __name__ == '__main__':
    db_path = r'teiko.db'
    init_db(db_path)


