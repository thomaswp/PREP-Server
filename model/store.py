# Needed, since this is in a subfolder
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import pickle
import sqlite3
from ps2lib.logger import SQLiteLogger, MAIN_TABLE
from ps2lib.progsnap import PS2

MODELS_TABLE = 'Models'

MODELS_TABLE_COLUMNS = {
    'ModelID': 'INTEGER PRIMARY KEY AUTOINCREMENT',
    'ProblemID': 'TEXT UNIQUE',
    'Model': 'BLOB',
    'TrainingCount': 'INTEGER',
}

class ModelStore(SQLiteLogger):

    def create_models_table(self):
        self._create_table(MODELS_TABLE, MODELS_TABLE_COLUMNS)

    def should_rebuild_model(self, problem_id, min_count, increment):
        with self._connect() as conn:
            c = conn.cursor()
            c.execute(f"SELECT COUNT(DISTINCT({PS2.CodeStateID})) FROM {MAIN_TABLE} WHERE ProblemID = ?", (problem_id,))
            result = c.fetchone()
            if result is None or result[0] < min_count:
                return False
            current_correct_count = result[0]

            c.execute(f"SELECT TrainingCount FROM {MODELS_TABLE} WHERE ProblemID = ?", (problem_id,))
            result = c.fetchone()
            if result is None:
                return True
            return current_correct_count >= result[0] + increment

    def __blobify(self, obj):
        pdata = pickle.dumps(obj)
        return sqlite3.Binary(pdata)

    def __deblobify(self, blob):
        return pickle.loads(blob)

    def set_model(self, problem_id, model, training_correct_count):
         with self._connect() as conn:
            c = conn.cursor()
            query = f"INSERT OR IGNORE INTO {MODELS_TABLE} (ProblemID, Model) VALUES (?,NULL);"
            c.execute(query, (problem_id,))
            query = f"UPDATE {MODELS_TABLE} SET Model = ?, TrainingCount = ? WHERE ProblemID = ?;"
            c.execute(query, (self.__blobify(model), training_correct_count, problem_id))
            conn.commit()

    def get_model(self, problem_id):
        with self._connect() as conn:
            c = conn.cursor()
            c.execute(f"SELECT Model FROM {MODELS_TABLE} WHERE ProblemID = ?", (problem_id,))
            result = c.fetchone()
            if result is None:
                return None
            return self.__deblobify(result[0])