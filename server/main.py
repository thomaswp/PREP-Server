# Needed, since this is run in a subfolder
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import datetime, traceback, random, yaml
from flask import Flask, request, render_template_string, g
from flask_restful import Resource
from flask_cors import CORS
from model.store import ModelStore
from ps2lib.logger import SQLiteLogger
from ps2lib.progsnap import ProgSnap2Dataset, PS2, EventType
from ps2lib.providers import SQLiteDataProvider
from model.model import CorrectnessModelBuilder

app = Flask(__name__)
CORS(app)

def relative_path(path):
    basedir = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(basedir, path)

config_path = relative_path("config.yaml")
if not os.path.exists(config_path):
    config_path = relative_path("config.default.yaml")
    print("Warning: Loading default config file! Createa a server/config.yaml file.")

config = yaml.safe_load(open(config_path))

LOG_DATABASE = config["log_database"]

BUILD_MIN_CORRECT_COUNT_FOR_FEEDBACK = config["build"]["min_correct_count_for_feedback"]
BUILD_INCREMENT = config["build"]["increment"]
BUILD_LANG = config["build"]["language"]

CONDITIONS_ASSIGNMENT = config["conditions"]["assignment"]
CONDITIONS_INTERVENTION_PROBABILITY = config["conditions"]["intervention_probability"]
CONDITIONS_INVERSE_PROBLEMS = config["conditions"]["inverse_problems"]
CONDITIONS_MANUALLY_ASSIGNED_PROBLEMS = config["conditions"]["manually_assigned_problems"]

class ExampleIntervention(Resource):

    def __init__(self) -> None:
        super().__init__()

        logging_database_path = relative_path(f'data/{LOG_DATABASE}.db')
        self.logger = SQLiteLogger(logging_database_path)
        self.logger.create_tables()
        # The model store will also use the logging database, for consolidation and
        # since it needs to read the MainTable to determine when a model should be
        # rebuilt
        self.model_store = ModelStore(logging_database_path)
        self.model_store.create_models_table()

        with open(relative_path("templates/feedback.html"),"r") as file:
            self.feedback_tempalte = '\n'.join(file.readlines())


    def load_model_from_db(self, problem_id):
        models = self.model_store.get_model(problem_id)
        if models is None:
            print(f"Model not found for {problem_id} in {LOG_DATABASE}.db")
        return models

    def log_and_rebuild_model_if_needed(self, event_type, dict):
        logger = self.get_logger(LOG_DATABASE)
        dict["ServerTimestamp"] = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        try:
            client_timestamp = dict["ClientTimestamp"]
            dict["ClientTimestamp"] = datetime.datetime.strptime(client_timestamp, "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%Y-%m-%dT%H:%M:%S")
        except:
            pass
        logger.log_event(event_type, dict)
        if "ProblemID" in dict:
            self.rebuild_model_if_needed(dict["ProblemID"])

    def rebuild_model_if_needed(self, problem_id):
        problem_id = str(problem_id)
        logger = self.get_logger(LOG_DATABASE)
        if not logger.should_rebuild_model(problem_id, BUILD_MIN_CORRECT_COUNT_FOR_FEEDBACK, BUILD_INCREMENT):
            return
        try:
            provider = SQLiteDataProvider(logger.db_path)
            dataset = ProgSnap2Dataset(provider)
            builder = CorrectnessModelBuilder(problem_id)
            builder.lang = BUILD_LANG
            builder.build(dataset)
            model = builder.get_trained_model()
            correct_count = int(builder.X_train[builder.y_train].unique().size)
            self.model_store.set_model(problem_id, model, correct_count)
            print(f"Successfully rebuilt model for {problem_id} with {correct_count} unique correct submissions")
        except Exception:
            print(f"Failed model build for {problem_id}")
            traceback.print_exc()
            return

    def default_condition_is_intervention(self, id):
        state = str(LOG_DATABASE) + str(id)
        random.seed(state)
        is_intervention = random.random() < CONDITIONS_INTERVENTION_PROBABILITY
        # print(f"Random condition for {id}: {is_intervention}")
        return is_intervention


    def is_intervention_group(self, subject_id, problem_id):
        if problem_id in CONDITIONS_MANUALLY_ASSIGNED_PROBLEMS:
            is_intervention = CONDITIONS_MANUALLY_ASSIGNED_PROBLEMS[problem_id] == "intervention"
            # print (f"Manually assigned problem: {problem_id} is intervention: {is_intervention}")
            return is_intervention
        if CONDITIONS_ASSIGNMENT == "all_control":
            return False
        if CONDITIONS_ASSIGNMENT == "all_intervention":
            return True
        logger = self.get_logger(LOG_DATABASE)
        subject_condition = logger.get_or_set_subject_condition(
            subject_id, self.default_condition_is_intervention(subject_id))
        if problem_id in CONDITIONS_INVERSE_PROBLEMS:
            # print(f"Problem {problem_id} is inverse; switching {subject_condition} to {not subject_condition}")
            subject_condition = not subject_condition
        if CONDITIONS_ASSIGNMENT == "random_student":
            # print(f"Random student condition for {subject_id} on {problem_id}: {subject_condition}")
            return subject_condition
        else:
            print(f"Unknown condition assignment: {CONDITIONS_ASSIGNMENT}")
            return True

    def generate_feedback(self, problemID, code):
        model = self.load_model_from_db(problemID)
        if model is None:
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

feedback_generator = ExampleIntervention()

def generate_feedback_from_request():
    json = request.get_json()
    code = json["CodeState"]
    problem_id = json[PS2.ProblemID]
    if (PS2.SubjectID in json):
        subject_id = json[PS2.SubjectID]
        if (not feedback_generator.is_intervention_group(subject_id, problem_id)):
            return []
    else:
        print("Warning: No SubjectID provided")
    return feedback_generator.generate_feedback(problem_id, code)

@app.route('/', methods=['GET'])
def hello_world():
    return 'Hello, World!'

@app.route('/Submit/', methods=['POST'])
def submit():
    feedback_generator.log_and_rebuild_model_if_needed(EventType.Submit, request.get_json())
    return generate_feedback_from_request()

@app.route('/FileEdit/', methods=['POST'])
def file_edit():
    feedback_generator.log_and_rebuild_model_if_needed(EventType.FileEdit, request.get_json())
    return generate_feedback_from_request()

@app.route('/Run.Program/', methods=['POST'])
def run_program():
    feedback_generator.log_and_rebuild_model_if_needed(EventType.RunProgram, request.get_json())
    return []

# Enable to test efficiency
# @app.before_request
# def before_request():
#     g.start = time.time()

# @app.after_request
# def after_request(response):
#     diff = time.time() - g.start
#     print (diff)
#     return response

# api.add_resource(HelloWorld, '/')

if __name__ == '__main__':
    app.run(port=5500, debug=True)