
from abc import ABC, abstractmethod

class Intervention(ABC):

    @abstractmethod
    def on_event(self, event_type: str, data: dict[str, any], code: str) -> (dict | list[dict]):
        pass
