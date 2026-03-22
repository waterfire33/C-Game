from utils import format_task_type


def get_task_input():
    task_type = input("Enter task type: ")
    task = input("Enter task: ")
    return format_task_type(task_type), task.strip()