import argparse
import json
import os
from dotenv import load_dotenv

load_dotenv()

from agent import StemAgent
from eval import TEST_CASES, run_eval


def print_comparison(baseline_details, final_details, test_cases):
    print(f"\n  {'case':<25} {'before':>8} {'after':>8} {'delta':>8}")
    print(f"  {'-'*49}")
    for i, tc in enumerate(test_cases):
        b = baseline_details[i]["score"] if i < len(baseline_details) else 0
        a = final_details[i]["score"] if i < len(final_details) else 0
        d = a - b
        sign = "+" if d > 0 else ""
        print(f"  {tc['name']:<25} {b:>8.2f} {a:>8.2f} {sign}{d:>7.2f}")


def main():
    p = argparse.ArgumentParser(description="stem agent")
    p.add_argument("--domain", default="python code review",
                   help="task domain to specialize for")
    p.add_argument("--model", default="gpt-4o-mini")
    p.add_argument("--gens", type=int, default=4, help="max generations")
    p.add_argument("--target", type=float, default=0.85, help="stop when score reaches this")
    p.add_argument("--load", help="load a saved config json instead of differentiating")
    p.add_argument("--review", help="review a single .py file (use with --load)")
    p.add_argument("--eval-only", action="store_true", help="just run eval, no differentiation")
    args = p.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        print("error: set OPENAI_API_KEY in .env or environment")
        return

    agent = StemAgent(args.domain, model=args.model)

    if args.load:
        agent.load_config(args.load)

    if args.review:
        if not args.load:
            print("(warning: no config loaded, using generic agent)")
        with open(args.review) as f:
            code = f.read()
        text, tools = agent.review(code, filename=args.review)
        print("\n--- review output ---\n")
        print(text)
        return

    print(f"domain: {args.domain}")
    print(f"model:  {args.model}")
    print(f"tests:  {len(TEST_CASES)} cases\n")

    print("=" * 50)
    print("BASELINE (generic agent, no specialization)")
    print("=" * 50)
    baseline_score, baseline_details = run_eval(agent, TEST_CASES)
    print(f"\nbaseline avg score: {baseline_score:.3f}")

    if args.eval_only:
        return

    history = agent.differentiate(TEST_CASES, max_gens=args.gens, target=args.target)

    print("=" * 50)
    print("FINAL (specialized agent)")
    print("=" * 50)
    final_score, final_details = run_eval(agent, TEST_CASES)
    print(f"\nfinal avg score: {final_score:.3f}")

    # --- comparison ---
    print("\n" + "=" * 50)
    print("BEFORE vs AFTER")
    print("=" * 50)
    print(f"  baseline:    {baseline_score:.3f}")
    print(f"  specialized: {final_score:.3f}")
    delta = final_score - baseline_score
    print(f"  improvement: {'+' if delta >= 0 else ''}{delta:.3f}")

    print_comparison(baseline_details, final_details, TEST_CASES)

    os.makedirs("results", exist_ok=True)

    agent.save_config("results/best_config.json")

    results = {
        "domain": args.domain,
        "model": args.model,
        "baseline_score": baseline_score,
        "final_score": final_score,
        "delta": delta,
        "generations": len(history),
        "history": [
            {"gen": h["generation"], "score": h["score"]}
            for h in history
        ],
        "baseline_details": baseline_details,
        "final_details": final_details,
    }
    with open("results/run_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\nresults saved to results/")


if __name__ == "__main__":
    main()
