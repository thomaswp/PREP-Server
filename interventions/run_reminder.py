
from .intervention import Intervention
from ps2lib.progsnap import PS2, EventType
from .actions import show_message
from ps2lib.logger import MAIN_TABLE, SQLiteLogger
import time

custom_event_type = "X-Reminder"

class RunReminder(Intervention):

    def __init__(self, logger: SQLiteLogger):
        self.logger = logger
        self.reminder_time_s = 15
        
    def calculate_time_since_last_run(self, problem_id, subject_id):
        # We order by EventID since timestamp is stored as a string
        # for compatibility w/ the PS2 format
        query = f"""
        SELECT {PS2.ServerTimestamp}
        FROM {MAIN_TABLE}
        WHERE {PS2.ProblemID} = ? AND {PS2.SubjectID} = ? AND
        ({PS2.EventType} = "{EventType.RunProgram}" OR 
        {PS2.EventType} = "{EventType.Submit}" OR
        {PS2.EventType} = "{custom_event_type}")
        ORDER BY {PS2.EventID} DESC
        """
        params = (problem_id, subject_id)
        last_run = self.logger.execute_query(query, params)
        if last_run is None:
            return None
        # Get the first (and only) column of the first (and only) row
        parsed = time.strptime(last_run[0][0], "%Y-%m-%dT%H:%M:%S")
        # Get elapsed time since the parsed time
        elapsed = time.time() - time.mktime(parsed)
        return elapsed

    def on_event(self, event_type: str, data: dict[str, any], code: str) -> (dict | list[dict]):
        if event_type != EventType.FileEdit:
            return []
        elapsed = self.calculate_time_since_last_run(data[PS2.ProblemID], data[PS2.SubjectID])
        if elapsed is None or elapsed > self.reminder_time_s:
            self.logger.log_event(custom_event_type, data)
            return show_message("Don't forget to run your code!")
        return []