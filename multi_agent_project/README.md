# Multi-Agent Project

This is a simple Python multi-agent system.

## Files

- `main.py` runs one user task
- `agents.py` contains the agent classes
- `orchestrator.py` chooses the correct agent
- `orchestrator.py` returns a clear message when a task type is not supported
- `input_handler.py` gets task input from the user
- `result_handler.py` prints the result
- `config.py` stores supported task types and the unsupported-task message
- `tasks.py` stores example tasks
- `test_task.py` tests the supported task types
- `test_unknown_task.py` tests an unsupported task type
- `run_all.py` runs the main program and all tests
- `project_summary.txt` gives a short summary of the project
- `notes.txt` contains simple build notes
- `.gitignore` ignores Python cache folders and compiled Python files
- `__init__.py` marks the folder as a Python package
- `input_handler.py` normalizes task types to support any letter case
- `utils.py` formats task type input
- `test_utils.py` tests task type formatting
- `test_supported_types.py` tests the supported task type list
- `show_supported_types.py` prints the supported task types
- `test_math_error.py` tests invalid math input
- `test_task_data.py` tests running a task from a task-data dictionary
- `test_supported_types.py` also tests whether one task type is supported

## Supported task types

- `math`
- `text`
- `image`
- `greeting`
- `echo`