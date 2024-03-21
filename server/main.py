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
from interventions.hello_intervention import HelloIntervention
from interventions.autograder import AutograderIntervention
from interventions.run_reminder import RunReminder

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

CONDITIONS_ASSIGNMENT = config["conditions"]["assignment"]
CONDITIONS_INTERVENTION_PROBABILITY = config["conditions"]["intervention_probability"]
CONDITIONS_INVERSE_PROBLEMS = config["conditions"]["inverse_problems"]
CONDITIONS_MANUALLY_ASSIGNED_PROBLEMS = config["conditions"]["manually_assigned_problems"]

class EventManager(Resource):

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

        # self.intervention = HelloIntervention()
        self.intervention = RunReminder(self.logger)
        # self.intervention = AutograderIntervention(self.model_store)

    def log_and_get_actions_for_event(self, event_type, data):
        self.log_event(event_type, data)

        # At a minimum we expect a ProblemID and CodeState
        if PS2.ProblemID not in data:
            print("Warning: No ProblemID provided - skipping intervention.")
            return []
        if "CodeState" not in data:
            print("Warning: No CodeState provided - skipping intervention.")
            return []
        problem_id = data[PS2.ProblemID]

        # Determine whether this is an intervention condition
        if (PS2.SubjectID in data):
            subject_id = data[PS2.SubjectID]
            if (not event_manager.is_intervention_group(subject_id, problem_id)):
                return []
        else:
            print("Warning: No SubjectID provided - defaulting to intervention group.")

        code = data["CodeState"]
        return self.get_actions_for_event(event_type, data, code)

    def log_event(self, event_type, data):
        logger = self.logger
        data["ServerTimestamp"] = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        try:
            client_timestamp = data["ClientTimestamp"]
            data["ClientTimestamp"] = datetime.datetime.strptime(client_timestamp, "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%Y-%m-%dT%H:%M:%S")
        except:
            pass
        logger.log_event(event_type, data)


    def get_actions_for_event(self, event_type, data, code):
        action_or_actions = self.intervention.on_event(event_type, data, code)
        if not isinstance(action_or_actions, list):
            return [action_or_actions]
        return action_or_actions

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
        logger = self.logger
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

event_manager = EventManager()

def handle_request(event_type: str):
    json = request.get_json()
    actions = event_manager.log_and_get_actions_for_event(event_type, json)
    print(actions)
    return actions


@app.route('/', methods=['GET'])
def hello_world():
    return 'Hello, World!'

@app.route('/Submit/', methods=['POST'])
def submit():
    return handle_request(EventType.Submit)

@app.route('/FileEdit/', methods=['POST'])
def file_edit():
    return handle_request(EventType.FileEdit)

@app.route('/Run.Program/', methods=['POST'])
def run_program():
    return handle_request(EventType.RunProgram)

# Enable to test efficiency
# @app.before_request
# def before_request():
#     g.start = time.time()

# @app.after_request
# def after_request(response):
#     diff = time.time() - g.start
#     print (diff)
#     return response

if __name__ == '__main__':
    app.run(port=5500, debug=True)