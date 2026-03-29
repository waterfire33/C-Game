from orchestrator import Orchestrator
from result_handler import show_result
from show_supported_types import show_supported_types
from input_handler import get_task_type_input, get_task_input


def run_loop():
    orchestrator = Orchestrator()

    print("Supported task types:")
    print(f"Total supported task types: {orchestrator.count_supported_task_types()}")
    show_supported_types()
    print("Type 'help' to see supported task types again.")
    print("Type 'exit' to stop.")

    while True:
        task_type = get_task_type_input()

        if task_type == "exit":
            print("Program stopped.")
            break

        if task_type == "help":
            print("Supported task types:")
            print(f"Total supported task types: {orchestrator.count_supported_task_types()}")
            show_supported_types()
            continue

        task = get_task_input()

        if task.lower() == "exit":
            print("Program stopped.")
            break

        task_data = {"type": task_type, "task": task}
        result = orchestrator.run_task_data(task_data)
        show_result(result)


if __name__ == "__main__":
    run_loop()