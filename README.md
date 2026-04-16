# Stem Agent

An AI agent that specializes itself for a given task domain through iterative self-modification.

## How it works

1. **Research** — learns what good practice looks like in the domain
2. **Design** — writes its own config: system prompt, tool selection, workflow  
3. **Evaluate** — runs on test cases, scored by an LLM judge
4. **Keep or rollback** — improves? keep. regress? revert. repeat.

Stops when target score is hit or improvement plateaus.

## Setup

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
echo "OPENAI_API_KEY=your-key" > .env
```

## Run

```bash
python main.py
python main.py --model gpt-4o --gens 6 --target 0.9
python main.py --load results/best_config.json --review mycode.py
```
