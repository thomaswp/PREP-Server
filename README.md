# SimpleAIF

**Description:** SimpleAIF is a basic server for generating feedback based on the input code's similarity to the different forms of the final solution.

This repository contains code for:

1. ``shared``: code for building SimpleAIF models from ProgSnap2 datasets (CSV or SQLite database) or via HTTP calls.
2. ``server``: a Python server for giving that feedback as a service.

## Setup

It is suggested to use VSCode to load this repository and a [virtual environment](https://code.visualstudio.com/docs/python/environments) to manage and install dependencies.

Take the following steps to install SimpleWebIDE.

1. Clone the repo.
```bash
git clone https://github.ncsu.edu/HINTSLab/SimpleAIF.git
```
2. Setup a python 3.9 environment. On Windows this is easiest using [VS Code](https://code.visualstudio.com/docs/python/environments) (you will need to [use CMD](https://code.visualstudio.com/docs/terminal/profiles) rather than Powershell for your termnial) or [Anaconda](https://conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html#activating-an-environment), and on Unix pyenv.
3. Install the dependencies using the included ``requirements.txt`` file.
   * **Note**: This only installs the server runtime dependencies: Running the Jupyter notebooks and doing EDA may require additional dependencies, which you can install manually.
```bash
pip install -r requirements.txt
```
4. Copy `server/config.example.yaml` to `server/config.yaml` and update it to your need based on the comments.


## Serving Feedback

You can run SimpleAIF using the code found in the server folder.
1. Update ``main.py`` to set the `SYSTEM_ID` variable to your system (e.g., `PCRS`, `iSnap`, `CWO`, `BlockPy`).
2. Run ``main.py``. It should start a server on port 5000.
3. If the server fails to start, make sure you're running it from the correct directory (the server directory).

Note that to work, you must build a model, either beforehand, or as the server runs. See instructions below on how to do so.


## Building a Model

### Building a Model Using an Existing ProgSnap2 Dataset

```python
from shared.progsnap import ProgSnap2Dataset
from shared.database import CSVDataProvider, SQLiteDataProvider
from shared.preprocess import SimpleAIFBuilder
from shared.data import SQLiteLogger

# Load a dataset from a folder with CSV files
dataset = ProgSnap2Dataset(CSVDataProvider(data_folder))

# Or load it from a SQLite database
dataset = ProgSnap2Dataset(SQLiteDataProvider(database_path))

# Create a builder with relevant parameters and build
builder = SimpleAIFBuilder(
    problem_id,
    code_column=code_column,
    problem_id_column=problem_id_column
)
builder.build(dataset)

# Train the progress model and classifier
progress_model = builder.get_trained_progress_model()
classifier = builder.get_trained_classifier()

# Optional: store that model in a database to be used by the server
logger = SQLiteLogger(database)
logger.create_tables()
correct_count = int(builder.X_train[builder.y_train].unique().size)
logger.set_models(problem_id, progress_model, classifier, correct_count)
```

### Building a Model On the Fly or Using a Custom Dataset via HTTP Post

If your dataset is not in ProgSnap2 format, or you do not have prior data, you can still use SimpleAIF. You can use the following steps to populate a new ProgSnap2 database and build the model, either as students submit their work, and/or with seed data you already have available.

1) Change the `SYSTEM_ID` constant in main.py to your system name.
2) Run `main.py` to start the server (see instructions above).
3) Add relevant data, with a call similar to the below:

```python
url = f"http://127.0.0.1:5000/{row[PS2.EventType]}/"
x = requests.post(url, json = row_dict)
```

Where the `row_dic` is an object with key-value pairs matching the fields described in the next section.

#### Student Attempts at a Problem

SimpleAIF is a data-driven model, and it requires some data from prior students to provide feedback. Ideally, this data is available for some or all problems beforehand (even if generated by an instructor), but if not it can be added at runtime.

Either way, send an HTTP-POST request to `http://127.0.0.1:5000/XXX/`, where XXX is one of the following ProgSnap2 EventTypes (they will have the same result):
* `Submit`
* `FileEdit`
* `Run.Program`

The request should at a minimum have the following JSON in the post body:
* `ProblemID`: The problem ID (e.g., `32` or `sum_of_three`).
* `SubjectID`: The user ID (e.g., `123` or `student_1`). **Note** that this ID will be stored in the local database, so if desired you can hash/encrypt it before sending it to the server. Ideally, SubjectIDs should remain consistent across problems, though this is not strictly necessary for SimpleAIF.
* `CodeState`: The student's current code at the time of the event (e.g., `def foo():\n\treturn 0`).
* `Score`: The score for the student's current code, ranging from 0-1, where 1 indicates fully correct code. This can be assessed automatically (e.g., by test cases) or manually if using previously collected data.
* `NoLogging` [Optional]: This can be set to `false` to tell SimpleAIF not to record the event.

The request can also include the following, though they are not currently used by SimpleAIF:
* `AssignmentID`: A unique ID for the assignment that this problem belongs to (e.g., `hw1` or `lab2`).
* `ClientTimestamp`: The time of the event according to the client in ISO format (e.g., `2021-11-08T15:00:00Z`).
* `ServerTimestamp`: The time of the event according to the server in ISO format (e.g., `2021-11-08T15:00:00Z`).

For example, the JSON request might look like:
```
{
    "ProblemID": "8",
    "SubjectID": "Student01",
    "CodeState": "def collect_underpreforme",
    "Score": 0
    "ShouldLog": true,
    "AssignmentID": "Assignment01",
    "ClientTimestamp": "2023-10-20T19:14:29.692Z",
}
```

Note that currently SimpleAIF will build a feedback model for a given problem when it has at least `MIN_CORRECT_COUNT_FOR_FEEDBACK` correct student responses for that problem. It will subsequently recompile the models if it receives an additional `COMPILE_INCREMENT` correct responses. These values are set in `main.py`.

For example, if `MIN_CORRECT_COUNT_FOR_FEEDBACK` is 10 and `COMPILE_INCREMENT` is 5, SimpleAIF will build a model after 10 correct responses, and then rebuild it after 15, 20, 25, etc. correct responses.

### Starter Code

If you have starter code for some problems (i.e., students are given a method definition, comments, variables, etc. to start with), you should add this to the database. This will allow the model to ignore any starter code when computing student progress.

If you have a ProgSnap2 dataset, you can put your starter code in the `StarterCode` column of the `Problem.csv` link table.

If building the dataset using HTTP, send an HTTP-POST request to `http://127.0.0.1:5000/X-SetStarterCode/` with the following JSON in the post body:
* `ProblemID`: The problem ID (e.g., `32` or `sum_of_three`).
* `StarterCode`: The starter code for the problem (e.g., `def foo():\n\treturn 0`).

For example
```
{
    "ProblemID": "32",
    "StarterCode": "def foo():\n\treturn 0"
}
```
