# Clean install from pyproject.toml
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install .[test,dev,telemetry]
