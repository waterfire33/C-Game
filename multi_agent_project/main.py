from orchestrator import Orchestrator
from result_handler import show_result
from input_handler import get_task_input
from show_supported_types import show_supported_types


def run_once():
    orchestrator = Orchestrator()

    print("Supported task types:")
    show_supported_types()

    task_type, task = get_task_input()
    task_data = {"type": task_type, "task": task}
    result = orchestrator.run_task_data(task_data)
    show_result(result)


if __name__ == "__main__":
    run_once()