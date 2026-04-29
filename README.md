# IRAC Maker

AI-powered legal writing practice for American law school students. Runs entirely on your machine using a local LLM (no API keys, no data sent to the cloud).

## What it does

| Tab | Description |
|---|---|
| **Generate IRAC** | Paste a fact pattern — get a full IRREAC analysis with citations and element-by-element application |
| **Both Sides** | Generates plaintiff's and defendant's strongest arguments side by side |
| **Compare & Feedback** | Write your own IRAC, then get it graded section-by-section against the AI's model answer |
| **Socratic Mode** | A professor asks you one question at a time to help you spot the issues yourself |

The AI uses **IRREAC** — a two-Rule variant of IRAC (Issue, Rule Statement, Rule Exploration, Application, Conclusion) that adds a Rule Exploration step for richer analysis.

## Requirements

- [Ollama](https://ollama.com/download) installed and running
- Python 3.10+

## Setup

```bash
bash setup.sh
```

This will:
1. Pull the `qwen3.5:9b` base model via Ollama (~5.6 GB)
2. Build the custom `irac-maker` model from the included `Modelfile`
3. Create a Python virtual environment and install dependencies

## Run

```bash
source .venv/bin/activate
streamlit run app.py
```

Then open [http://localhost:8501](http://localhost:8501) in your browser.

## How it works

- The `irac-maker` Ollama model is a fine-tuned system prompt on top of `qwen3.5:9b` with two built-in few-shot examples (Contracts + Torts)
- Chain-of-thought is disabled (`think=False`) to avoid token waste
- The model is kept loaded in VRAM for 30 minutes between requests (`keep_alive=30m`)
- JSON output is streamed and parsed with a truncation-repair fallback

## Areas of Law supported

Contracts, Torts, Constitutional Law, Criminal Law, Criminal Procedure, Property, Civil Procedure, Evidence, Administrative Law, Business Associations, Family Law, Professional Responsibility

## Disclaimer

For educational purposes only. Not legal advice.
