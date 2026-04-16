# Stem Agent: Self-Specializing AI Through Iterative Self-Modification

## The Idea

I didn't want to build an agent that pretends to evolve. The task description talks about stem cells reading signals from their environment and actually changing, and I wanted that, not a simulation of it. So the "genome" here is literal: system prompt, tool selection, workflow. They change based on measured performance. If a generation scores worse, it gets rolled back. If it scores better, it stays.

The setup is two LLMs talking to each other, kind of. One at the meta level, deciding what kind of agent to be. One at the object level, doing the actual task. Same model, different prompts, different jobs.

## Why Code Review

I needed a domain where you can actually tell if something improved. Code review worked because the ground truth is easy to define: did the agent find the bug or not? You can also give it real tools to pick from, not just prompt variations. AST parsing, regex checkers, security scanners. That felt closer to what "discovering capabilities" should mean.

I wrote 12 Python snippets with different problem types. Mutable defaults, SQL injection, eval() misuse, silenced exceptions, off-by-one errors, a falsy-value trap where discount=0 gets treated as False. One clean snippet to see if the agent hallucinates issues. The bugs go from obvious to genuinely subtle on purpose.

## How It Works

Each generation does five things. Research (what does good code review look like?), design (write a JSON config based on that research plus last eval's results), apply (load the new config, validate the tools exist), evaluate (run 12 cases, score with an LLM judge), then keep or roll back depending on whether the score went up.

The agent starts with zero tools enabled and no real system prompt. During design, it sees descriptions of five Python analysis tools (AST checker, regex searcher, security scanner, complexity checker, style checker) and picks which ones to activate. The idea is that it shouldn't get a pre-built toolkit, it should choose one.

## Results

Real run over three generations:

| Phase | Score |
|-------|-------|
| Baseline (generic agent) | 0.804 |
| Gen 0 | 0.817 (kept, new best) |
| Gen 1 | 0.804 (rolled back) |
| Gen 2 | 0.815 (rolled back, plateau) |
| Final (best config, re-evaluated) | 0.850 |

Net improvement: +0.046. Not huge, but real. The run stopped at generation 2 because scores plateaued (last three generations within 0.03).

The per-case breakdown is where it gets interesting:

Big wins:
- `none_compare`: 0.14 → 1.00. The generic agent kept ignoring `== None` as an issue. The specialized prompt with pattern_search catches it every time.
- `silent_fail`: 0.50 → 0.90
- `off_by_one`: 0.75 → 1.00
- `resource_leak`: 0.75 → 1.00
- `global_mutation`: 0.80 → 1.00

Regressions (I did not expect these):
- `sql_injection`: 1.00 → 0.50
- `hardcoded_secret`: 1.00 → 0.50
- `type_confusion`: 0.90 → 0.50

The regressions are the most interesting part of the whole run. The generic agent was already catching these fine. After specialization, the agent shifts its attention and starts missing things it used to find. Specialization isn't strictly additive. You trade attention across cases, and the evolutionary loop can't see that because it only looks at the average.

## What Surprised Me

The regressions, mainly. I assumed specialization would only add capability, not move it around. But the prompt changes, the focus changes, and cases that were solved start breaking. A +0.86 gain on `none_compare` masks a −0.50 loss on `sql_injection` when you only look at the average. That's a real cost of self-modification I didn't think about in advance.

In generation 2 the agent requested 17 tools, including `pytest`, `mypy`, `bandit`, `black`, `flake8`, `pylint`, and others that don't exist in my registry. It just invented them. My validation stripped the fake ones out, but the interesting part is that the agent confidently designed a whole workflow around tools it wished it had. The LLM is happy to hallucinate capabilities if you give it the chance.

The rollback mechanism actually did its job. Gen 1 tied baseline at 0.804, gen 2 hit 0.815 but didn't beat gen 0's 0.817. Both got rolled back. Without that, the agent would have drifted into worse configurations chasing improvements that weren't there.

## What Failed

Evaluation variance is a real problem. Gen 0 scored 0.817 during differentiation, but the same config re-evaluated at the end of the run scored 0.850. Same prompt, same tools, same test cases, different score. The LLM judge isn't deterministic, and 12 cases is a small set, so a couple of borderline judgments move the average. That makes it hard to separate real improvement from noise.

The research phase is mostly wasted effort. Every generation asks the same question and gets about the same answer. The real signal comes from eval feedback in the design phase, not from research. I should have run research once and cached the result.

The judge and the agent are the same model. If GPT-4o-mini has a blind spot, both share it. The `sql_injection` regression might partly be this. The specialized agent probably described the issue in different words than the baseline, and the judge didn't count that as a catch. I can't fully tell without a stronger judge or human labels.

## What I'd Do With More Time

Research should actually hit the web. Right now the agent only knows what GPT already knows. Linter docs, Stack Overflow threads, recent papers, that's where the real signal lives.

Instead of rewriting the whole prompt each generation, I'd touch only the parts the eval flags as failing. Keep what's working. This is basically what DSPy does, and it would probably converge in fewer generations and avoid the regressions.

The gap I keep thinking about is tool discovery. Right now the agent picks from a fixed list I wrote. When it asked for `pytest` and `mypy` in gen 2, that was the agent telling me what it wanted. A real stem agent would generate those tools at runtime, write a new checker function, test it on the eval set, keep the ones that help. Harder to build, but it's what the biology metaphor actually points at. The cell doesn't pick from a menu, it grows new structures.
