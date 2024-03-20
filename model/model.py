import pandas as pd
from abc import ABC, abstractmethod
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.pipeline import Pipeline
from sklearn.dummy import DummyClassifier
from xgboost import XGBClassifier

from ps2lib.progsnap import ProgSnap2Dataset, PS2, EventType

class ModelBuilder(ABC):
    def __init__(self, problem_id, code_column=PS2.Code, problem_id_column=PS2.ProblemID):
        self.problem_id = problem_id
        self.code_column = code_column
        self.problem_id_column = problem_id_column
        self.submit_columns = [EventType.Submit, EventType.RunProgram]
        self.X_train = None
        self.y_train = None

    @staticmethod
    def get_submissions_table(data, submit_columns = [EventType.Submit, EventType.RunProgram, 'Project.Submit']):
        main_table = data.get_main_table()
        submissions = main_table[main_table[PS2.EventType].isin(submit_columns)]
        return submissions

    @staticmethod
    def get_code_table(data, submissions, problem_id_column, code_column):
        code_states = data.get_code_states_table()
        merged = pd.merge(
            submissions, code_states, on=PS2.CodeStateID
        )[[problem_id_column, PS2.Score, code_column]]
        # For both  models, we only want code with a specific score
        return merged[~merged[PS2.Score].isna()]

    def build(self, data: ProgSnap2Dataset):
        self.ps2_dataset = data
        submissions = ModelBuilder.get_submissions_table(data, self.submit_columns)
        self.mean_scores = submissions.groupby(self.problem_id_column).Score.mean()
        assignment_submissions = submissions[submissions[self.problem_id_column] == self.problem_id]
        assignment_code = ModelBuilder.get_code_table(data, assignment_submissions, self.problem_id_column, self.code_column)

        df = assignment_code.copy()
        # print(f"Found {len(df)} submissions for {self.problem_id}")
        df["Code"] = df[self.code_column]
        df["Correct"] = df["Score"] >= 1
        df = df[~df["Code"].isna()]

        self.X_train = df["Code"]
        self.y_train = df["Correct"]

    def get_correct_submissions(self):
        return self.X_train[self.y_train].reset_index(drop=True)

    def get_incorrect_submissions(self):
        return self.X_train[~self.y_train].reset_index(drop=True)

    @abstractmethod
    def get_trained_model(self):
        pass

class CorrectnessModelBuilder(ModelBuilder):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ngram_range = (1,3)
        self.classifier_factory = lambda: XGBClassifier()
        self.token_pattern = r"[\w]+|[^\s]|[ ]{4}"

    def create_vectorizer(self):
        return CountVectorizer(
            lowercase=False,
            token_pattern=self.token_pattern,
            ngram_range=self.ngram_range
        )

    def __create_classification_pipeline(self):
        if self.y_train.mean() == 1:
            return DummyClassifier(strategy="constant", constant=1)
        if self.y_train.mean() == 0:
            return DummyClassifier(strategy="constant", constant=0)

        stages = [
            ("vectorizer", self.create_vectorizer()),
            ("classifier", self.classifier_factory())
        ]

        return Pipeline(stages)

    def get_trained_model(self):
        progress_pipeline = self.__create_classification_pipeline()
        return progress_pipeline.fit(self.X_train, self.y_train)