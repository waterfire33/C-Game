# Multi-Agent Project

This is a simple Python multi-agent system.

## Files

- `main.py` runs in a loop and supports `help` plus `exit` from either prompt
- `agents.py` contains the agent classes
- `orchestrator.py` chooses the correct agent
- `orchestrator.py` returns a clear message when a task type is not supported
- `input_handler.py` gets task input from the user
- `result_handler.py` prints the result
- `config.py` stores supported task types and the unsupported-task message
- `tasks.py` stores example tasks
- `test_task.py` tests the supported task types
- `test_unsupported_task.py` tests an unsupported task type message
- `run_all.py` runs the main program and all tests
- `project_summary.txt` gives a short summary of the project
- `notes.txt` contains simple build notes
- `.gitignore` ignores Python cache folders and compiled Python files
- `__init__.py` marks the folder as a Python package
- `input_handler.py` gets task type and task text input
- `utils.py` formats task type input
- `test_utils.py` tests task type formatting
- `test_supported_types.py` tests the supported task type list
- `test_supported_types.py` also tests whether one task type is supported
- `test_supported_types.py` also tests whether one task type is not supported
- `test_supported_types.py` also tests the number of supported task types
- `show_supported_types.py` prints the supported task types
- `test_math_error.py` tests invalid math input
- `test_task_data.py` tests running supported and unsupported tasks from task-data dictionaries
- `main.py` also shows the total number of supported task types
- `test_route.py` tests routing for supported and unsupported task types
- `test_task.py` also tests the words-based math task

## Supported task types

- `math`
- `text`
- `image`
- `greeting`
- `echo`