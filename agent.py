import json
import time
import os
from openai import OpenAI


class StemAgent:

    def __init__(self, domain, model="gpt-4o-mini"):
        self.domain = domain
        self.model = model
        self.client = OpenAI()

        self.system_prompt = "You are a helpful assistant."
        self.active_tools = []
        self.workflow = []
        self.focus_areas = []

        self.generation = 0
        self.history = []
        self.best_score = -1
        self.best_config = None

    def _chat(self, messages, temp=0.7):
        for attempt in range(2):
            try:
                r = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temp,
                )
                return r.choices[0].message.content
            except Exception as e:
                print(f"  api call failed (attempt {attempt+1}): {e}")
                if attempt == 0:
                    time.sleep(2)
        return None

    def _extract_json(self, text):
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            end = len(lines) - 1
            for j in range(len(lines) - 1, 0, -1):
                if lines[j].strip().startswith("```"):
                    end = j
                    break
            text = "\n".join(lines[1:end])
        return json.loads(text)

    def research(self):
        print(f"\n  [gen {self.generation}] researching '{self.domain}'...")

        msg = (
            f"I need to build an AI agent specialized in: {self.domain}\n\n"
            f"What are the main sub-tasks in {self.domain}? "
            f"What tools and techniques do people use? "
            f"What are common mistakes? "
            f"What does a good workflow look like?\n\n"
            f"Be specific. I'll use this to configure the agent."
        )

        notes = self._chat([
            {"role": "system", "content": "You are a domain expert. Be practical and specific."},
            {"role": "user", "content": msg},
        ])

        if notes:
            print(f"  got research notes ({len(notes)} chars)")
        return notes

    def design(self, research_notes, prev_eval=None):
        print(f"  [gen {self.generation}] designing agent config...")

        from tools import TOOL_REGISTRY, TOOL_DESCRIPTIONS

        tools_block = "\n".join(
            f"  {name}: {TOOL_DESCRIPTIONS.get(name, '?')}"
            for name in TOOL_REGISTRY
        )

        parts = [
            f"Domain: {self.domain}\n",
            f"Research:\n{research_notes}\n",
            f"Available tools:\n{tools_block}\n",
        ]

        if prev_eval:
            parts.append(f"Previous eval (use to improve):\n{prev_eval}\n")

        parts.append(
            "Design the agent config as JSON:\n"
            "{\n"
            '  "system_prompt": "detailed instructions for the agent",\n'
            '  "tools": ["tool names to enable"],\n'
            '  "workflow": ["step1", "step2", ...],\n'
            '  "focus_areas": ["what to focus on"]\n'
            "}\n\n"
            "The system_prompt is the most important part — be detailed.\n"
            "Only output JSON."
        )

        raw = self._chat([
            {"role": "system", "content": "You design AI agents. Output valid JSON only."},
            {"role": "user", "content": "\n".join(parts)},
        ], temp=0.4)

        if not raw:
            return None

        try:
            cfg = self._extract_json(raw)
            print(f"  config: {len(cfg.get('tools', []))} tools, "
                  f"{len(cfg.get('workflow', []))} steps")
            return cfg
        except (json.JSONDecodeError, ValueError) as e:
            print(f"  json parse failed: {e}")
            return None

    def apply_config(self, cfg):
        if not cfg:
            return False

        self.system_prompt = cfg.get("system_prompt", self.system_prompt)

        from tools import TOOL_REGISTRY
        wanted = cfg.get("tools", [])
        self.active_tools = [t for t in wanted if t in TOOL_REGISTRY]
        dropped = set(wanted) - set(self.active_tools)
        if dropped:
            print(f"  dropped unknown tools: {dropped}")

        self.workflow = cfg.get("workflow", [])
        self.focus_areas = cfg.get("focus_areas", [])
        return True

    def snapshot(self):
        return {
            "system_prompt": self.system_prompt,
            "active_tools": list(self.active_tools),
            "workflow": list(self.workflow),
            "focus_areas": list(self.focus_areas),
            "generation": self.generation,
        }

    def rollback(self, snap):
        self.system_prompt = snap["system_prompt"]
        self.active_tools = snap["active_tools"]
        self.workflow = snap["workflow"]
        self.focus_areas = snap["focus_areas"]
        print(f"  rolled back to gen {snap['generation']}")

    def _run_tools(self, code):
        from tools import TOOL_REGISTRY
        findings = []
        for name in self.active_tools:
            fn = TOOL_REGISTRY.get(name)
            if not fn:
                continue
            try:
                hits = fn(code)
                for h in hits:
                    h["source"] = name
                findings.extend(hits)
            except Exception as e:
                print(f"  tool '{name}' crashed: {e}")
        return findings

    def review(self, code, filename="unknown"):
        tool_findings = self._run_tools(code) if self.active_tools else []

        extra = ""
        if tool_findings:
            extra = "\n\nAutomated tool findings:\n"
            for f in tool_findings:
                extra += f"- Line {f.get('line', '?')}: {f['issue']} [{f.get('source', '')}]\n"

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": (
                f"Review this Python code ({filename}):\n\n"
                f"```python\n{code}\n```"
                f"{extra}\n\n"
                "List each issue: line number, what's wrong, why it matters. "
                "If the code is clean, say so."
            )},
        ]

        text = self._chat(messages, temp=0.3)
        return text, tool_findings

    def differentiate(self, test_cases, max_gens=5, target=0.85):
        print(f"\n{'='*50}")
        print(f"STEM AGENT — differentiating for: {self.domain}")
        print(f"max generations: {max_gens}, target score: {target}")
        print(f"{'='*50}")

        from eval import run_eval

        prev_eval_text = None

        for gen in range(max_gens):
            self.generation = gen
            snap = self.snapshot()

            notes = self.research()
            if not notes:
                continue

            cfg = self.design(notes, prev_eval_text)
            if not cfg:
                continue

            self.apply_config(cfg)

            print(f"\n  evaluating gen {gen}...")
            score, details = run_eval(self, test_cases)

            print(f"\n  gen {gen} score: {score:.3f} (best: {self.best_score:.3f})")

            self.history.append({
                "generation": gen,
                "score": score,
                "config": cfg,
                "details": details,
            })

            if score > self.best_score:
                self.best_score = score
                self.best_config = cfg
                print(f"  >>> new best!")
            else:
                self.rollback(snap)

            lines = []
            for d in details:
                s = f"- {d['name']}: {d['score']:.2f}"
                if d.get("missed"):
                    s += f" | missed: {d['missed']}"
                if d.get("false_positives"):
                    s += f" | false pos: {d['false_positives']}"
                lines.append(s)
            prev_eval_text = "\n".join(lines)

            if score >= target:
                print(f"\n  hit target score, done")
                break

            if len(self.history) >= 3:
                recent = [h["score"] for h in self.history[-3:]]
                if max(recent) - min(recent) < 0.03:
                    print(f"\n  plateau — scores not improving, stopping")
                    break

        if self.best_config:
            self.apply_config(self.best_config)

        print(f"\n{'='*50}")
        print(f"differentiation done. best score: {self.best_score:.3f}")
        print(f"{'='*50}\n")

        return self.history

    def save_config(self, path):
        cfg = {
            "system_prompt": self.system_prompt,
            "tools": self.active_tools,
            "workflow": self.workflow,
            "focus_areas": self.focus_areas,
            "domain": self.domain,
            "generation": self.generation,
            "best_score": self.best_score,
        }
        with open(path, "w") as f:
            json.dump(cfg, f, indent=2)
        print(f"config saved to {path}")

    def load_config(self, path):
        with open(path) as f:
            cfg = json.load(f)
        self.apply_config(cfg)
        self.best_score = cfg.get("best_score", -1)
        print(f"loaded config from {path} (score: {self.best_score:.3f})")
