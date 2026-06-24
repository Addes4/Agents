# Private Credit Committee Demo

A local Streamlit prototype for a synthetic private credit investment committee.

The app lets you create or load a demo deal, run an advisory-only multi-agent credit committee, and generate an IC pack with risk views, diligence questions, approval conditions, and a human decision note.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

By default the app runs in deterministic mock mode. To use OpenAI-backed agent responses, set:

```bash
export OPENAI_API_KEY=...
export OPENAI_MODEL=gpt-4.1-mini
streamlit run app.py
```

## Safety Note

This is a synthetic/demo workflow. Do not upload or enter confidential borrower, sponsor, fund, or portfolio data into the prototype unless your environment and model provider configuration have been reviewed and approved.

## Tests

```bash
pytest
```
