from agents import MathAgent, TextAgent, ImageAgent, GreetingAgent, EchoAgent
from config import SUPPORTED_TASK_TYPES, UNSUPPORTED_TASK_MESSAGE


class Orchestrator:
    def __init__(self):
        self.agents = {
            "math": MathAgent(),
            "text": TextAgent(),
            "image": ImageAgent(),
            "greeting": GreetingAgent(),
            "echo": EchoAgent(),
        }

    def route(self, task_type):
        if task_type not in SUPPORTED_TASK_TYPES:
            return None

        return self.agents.get(task_type)

    def run_task(self, task_type, task):
        agent = self.route(task_type)

        if agent is not None:
            return agent.run(task)
        else:
            return f"{UNSUPPORTED_TASK_MESSAGE} {task_type}"

    def run_task_data(self, item):
        return self.run_task(item["type"], item["task"])

    def get_supported_task_types(self):
        return list(self.agents.keys())
    
    def is_supported_task_type(self, task_type):
        return task_type in self.agents