# Mercedes-Benz Smart Workshop Advisor

A small LangGraph state graph and Streamlit form for vehicle telemetry triage. Enter event details in the UI to calculate warranty eligibility, classify the alert, look up XENTRY repair guidance and parts, and generate a workshop advisory.

The repository intentionally excludes `.env`, virtual environments, raw telemetry/VIN samples, and ground-truth evaluation data. Alert input and user-entered vehicle details are processed locally by the app. The included XENTRY and parts JSON files are the local lookup data required to run the workflow.

## Run

Python 3.10 or newer is required. Install dependencies and start Streamlit:

```powershell
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

Enter a telemetry event in the form. Prefix the alert with `INFO ONLY:`, `SOFTWARE BUG:`, or `HARDWARE FAULT:` so the local classifier can route it correctly.

## Test

```powershell
python -m unittest -v
```
