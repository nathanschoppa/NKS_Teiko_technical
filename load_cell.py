import pandas as pd
from teiko_database import init_db, insert_csv_into_db
import logging

if __name__ == '__main__':
    logging.basicConfig(
    level=logging.DEBUG,           #minimum severity to capture
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    handlers=[
        logging.StreamHandler(),   #prints to terminal
        logging.FileHandler('teiko.log')  #also writes to a file
        ]
    )
    logger = logging.getLogger(__name__)
    
    db_path = r'C:\Users\admin\Documents\Teiko Assesment\teiko.db'
    init_db(db_path)
    cell_df = pd.read_csv('cell-count.csv')
    insert_csv_into_db(db_path,cell_df)