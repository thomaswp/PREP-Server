from .intervention import Intervention
from .actions import show_message, show_div
from ps2lib.progsnap import PS2, EventType

class HelloIntervention(Intervention):
    
    def on_event(self, event_type: str, data: dict[str, any], code: str) -> (dict | list[dict]):
        # When Submit is received, show a message
        if event_type == EventType.Submit:
            return show_message("Great submission!")
        # When the code is edited, show some feedback
        if event_type == EventType.FileEdit:
            subject_id = data[PS2.SubjectID] if PS2.SubjectID in data else "Student"
            problem_id = data[PS2.ProblemID] if PS2.ProblemID in data else "this problem"
            written = len(code)
            return show_div(f"Great work, <b>{subject_id}</b>! You've written <b>{written}</b> characters on {problem_id}.")
        # Otherwise do nothing
        return []