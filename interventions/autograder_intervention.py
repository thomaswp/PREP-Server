
import os, traceback
from .intervention import Intervention
from model.store import ModelStore
from model.model import CorrectnessModelBuilder
from ps2lib.providers import SQLiteDataProvider
from ps2lib.progsnap import ProgSnap2Dataset
from flask import render_template_string

def relative_path(path):
    basedir = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(basedir, path)

class AutograderIntervention(Intervention):

    def __init__(self, model_store: ModelStore):
        self.model_store = model_store
        with open(relative_path("templates/feedback.html"),"r") as file:
            self.feedback_tempalte = '\n'.join(file.readlines())

    def on_event(self, event_type: str, data: dict[str, any], code: str) -> (dict | list[dict]):
        if "ProblemID" in data:
            self.rebuild_model_if_needed(data["ProblemID"])
        return self.generate_feedback(data["ProblemID"], code)

    def rebuild_model_if_needed(self, problem_id):
        problem_id = str(problem_id)
        if not self.model_store.should_rebuild_model(problem_id, 1, 1):
            return
        try:
            provider = SQLiteDataProvider(self.model_store.db_path)
            dataset = ProgSnap2Dataset(provider)
            builder = CorrectnessModelBuilder(problem_id)
            builder.load_data(dataset)
            model = builder.get_trained_model()
            correct_count = int(builder.X_train.unique().size)
            self.model_store.set_model(problem_id, model, correct_count)
            print(f"Successfully rebuilt model for {problem_id} with {correct_count} unique submissions")
        except Exception:
            print(f"Failed model build for {problem_id}")
            traceback.print_exc()
            return

    def generate_feedback(self, problem_id, code):
        model = self.model_store.get_model(problem_id)
        if model is None:
            print(f"Model not found for {problem_id}")
            return []

        score = model.predict_proba([code])[0,1]

        html = render_template_string(self.feedback_tempalte,
            score=score
        )
        return [
            {
                "action": "ShowDiv",
                "data": {
                    "html": html,
                    "x-score": float(score),
                }
            }
        ]