import json
import time


TEST_CASES = [
    {
        "name": "mutable_default",
        "code": (
            "def add_tag(tag, tags=[]):\n"
            "    tags.append(tag)\n"
            "    return tags\n"
        ),
        "expected_issues": ["mutable default argument"],
    },
    {
        "name": "bare_except",
        "code": (
            "import json\n"
            "\n"
            "def load_config(path):\n"
            "    try:\n"
            "        with open(path) as f:\n"
            "            return json.load(f)\n"
            "    except:\n"
            "        return {'debug': False, 'log_level': 'info'}\n"
        ),
        "expected_issues": ["bare except clause — should catch specific exceptions"],
    },
    {
        "name": "none_compare",
        "code": (
            "def process(data):\n"
            "    result = transform(data)\n"
            "    if result == None:\n"
            "        return default_value()\n"
            "    return result\n"
            "\n"
            "def transform(data):\n"
            "    if len(data) == 0:\n"
            "        return None\n"
            "    return data.upper()\n"
        ),
        "expected_issues": ["== None comparison (should use 'is None')"],
    },
    {
        "name": "sql_injection",
        "code": (
            "import sqlite3\n"
            "\n"
            "def find_user(db_path, username):\n"
            "    conn = sqlite3.connect(db_path)\n"
            "    query = f\"SELECT * FROM users WHERE username = '{username}'\"\n"
            "    result = conn.execute(query).fetchone()\n"
            "    conn.close()\n"
            "    return result\n"
        ),
        "expected_issues": ["SQL injection via string formatting"],
    },
    {
        "name": "eval_danger",
        "code": (
            "def calculator(expression):\n"
            "    allowed = set('0123456789+-*/(). ')\n"
            "    if all(c in allowed for c in expression):\n"
            "        return eval(expression)\n"
            "    raise ValueError('invalid expression')\n"
        ),
        "expected_issues": ["use of eval() — dangerous even with input filtering"],
    },
    {
        "name": "resource_leak",
        "code": (
            "def read_csv_data(filepath):\n"
            "    f = open(filepath, 'r')\n"
            "    header = f.readline().strip().split(',')\n"
            "    rows = []\n"
            "    for line in f:\n"
            "        values = line.strip().split(',')\n"
            "        rows.append(dict(zip(header, values)))\n"
            "    return rows\n"
        ),
        "expected_issues": ["file not closed / no context manager"],
    },
    {
        "name": "silent_fail",
        "code": (
            "import logging\n"
            "\n"
            "def send_notification(user_id, message):\n"
            "    try:\n"
            "        client = NotificationAPI()\n"
            "        client.send(user_id, message)\n"
            "    except Exception:\n"
            "        pass\n"
        ),
        "expected_issues": ["exception silently swallowed — at minimum should log it"],
    },
    {
        "name": "off_by_one",
        "code": (
            "def find_pairs(nums, target):\n"
            "    pairs = []\n"
            "    for i in range(len(nums)):\n"
            "        for j in range(i, len(nums)):\n"
            "            if nums[i] + nums[j] == target:\n"
            "                pairs.append((nums[i], nums[j]))\n"
            "    return pairs\n"
        ),
        "expected_issues": [
            "inner loop starts at i instead of i+1 — element pairs with itself"
        ],
    },
    {
        "name": "global_mutation",
        "code": (
            "_cache = {}\n"
            "\n"
            "def get_user_data(user_id, use_cache=True):\n"
            "    if use_cache and user_id in _cache:\n"
            "        data = _cache[user_id]\n"
            "        data['access_count'] = data.get('access_count', 0) + 1\n"
            "        return data\n"
            "\n"
            "    data = fetch_from_db(user_id)\n"
            "    _cache[user_id] = data\n"
            "    return data\n"
        ),
        "expected_issues": [
            "mutating cached dict — changes are visible to all callers (shared mutable state)"
        ],
    },
    {
        "name": "clean_code",
        "code": (
            "from pathlib import Path\n"
            "from typing import Optional\n"
            "\n"
            "def read_file_safe(path: str, encoding: str = 'utf-8') -> Optional[str]:\n"
            "    fp = Path(path)\n"
            "    if not fp.exists():\n"
            "        return None\n"
            "    with open(fp, encoding=encoding) as f:\n"
            "        return f.read()\n"
        ),
        "expected_issues": [],
    },
    {
        "name": "hardcoded_secret",
        "code": (
            "import requests\n"
            "\n"
            "API_KEY = 'sk-proj-8kXnM4a7b2cD9eF1gH3jK5lM7nP9qR'\n"
            "\n"
            "def get_weather(city):\n"
            "    url = f'https://api.weather.com/v1/current?city={city}'\n"
            "    headers = {'Authorization': f'Bearer {API_KEY}'}\n"
            "    resp = requests.get(url, headers=headers)\n"
            "    return resp.json()\n"
        ),
        "expected_issues": ["hardcoded API key in source code"],
    },
    {
        "name": "type_confusion",
        "code": (
            "def get_discount(user):\n"
            "    discount = calculate_loyalty_discount(user)\n"
            "    if discount:\n"
            "        return apply_discount(user.cart, discount)\n"
            "    return user.cart.total\n"
            "\n"
            "def calculate_loyalty_discount(user):\n"
            "    years = user.membership_years\n"
            "    if years > 5:\n"
            "        return 0.15\n"
            "    if years > 2:\n"
            "        return 0.10\n"
            "    return 0\n"
        ),
        "expected_issues": [
            "falsy value bug — discount=0 is valid but 'if discount' treats it as False"
        ],
    },
]


def judge_review(client, model, code, review_text, expected_issues):
    if not expected_issues:
        prompt = (
            f"This Python code has NO real issues:\n\n```python\n{code}\n```\n\n"
            f"A reviewer said:\n{review_text}\n\n"
            "Did the reviewer correctly say the code is fine, or did they report "
            "false issues?\n\n"
            "Return JSON:\n"
            '{"found": [], "missed": [], '
            '"false_positives": ["list any non-issues reported"], '
            '"score": 1.0 if no false positives else lower}\n'
            "Only output JSON."
        )
    else:
        issues_str = "\n".join(f"- {x}" for x in expected_issues)
        prompt = (
            f"Code:\n```python\n{code}\n```\n\n"
            f"Known issues:\n{issues_str}\n\n"
            f"Review:\n{review_text}\n\n"
            "Which known issues did the review catch? Which did it miss? "
            "Any false positives?\n\n"
            "Return JSON:\n"
            '{"found": ["caught issues"], "missed": ["missed issues"], '
            '"false_positives": ["non-issues reported"], '
            '"score": <0.0 to 1.0 based on recall, minus a bit for false positives>}\n'
            "Only output JSON, no markdown."
        )

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You evaluate code reviews. Only output valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )
        raw = resp.choices[0].message.content.strip()

        if raw.startswith("```"):
            lines = raw.split("\n")
            end = len(lines) - 1
            for k in range(len(lines) - 1, 0, -1):
                if lines[k].strip().startswith("```"):
                    end = k
                    break
            raw = "\n".join(lines[1:end])

        result = json.loads(raw)
        result["score"] = max(0.0, min(1.0, float(result.get("score", 0))))
        return result

    except json.JSONDecodeError:
        print("judge json parse failed")
        return {"found": [], "missed": list(expected_issues), "false_positives": [], "score": 0.0}
    except Exception as e:
        print(f"judge error: {e}")
        return {"found": [], "missed": list(expected_issues), "false_positives": [], "score": 0.0}


def run_eval(agent, test_cases, judge_model=None):
    jmodel = judge_model or agent.model
    client = agent.client

    details = []
    total = 0.0

    for idx, tc in enumerate(test_cases):
        name = tc["name"]
        print(f"  [{idx+1}/{len(test_cases)}] {name}...", end=" ", flush=True)

        review_text, tool_hits = agent.review(tc["code"], filename=f"{name}.py")

        if review_text is None:
            print("FAIL")
            details.append({"name": name, "score": 0, "error": "no llm response"})
            continue

        judgment = judge_review(client, jmodel, tc["code"], review_text, tc["expected_issues"])
        sc = judgment["score"]
        total += sc

        details.append({
            "name": name,
            "score": sc,
            "found": judgment.get("found", []),
            "missed": judgment.get("missed", []),
            "false_positives": judgment.get("false_positives", []),
            "tool_hits": len(tool_hits),
        })

        tag = "OK" if sc >= 0.7 else ("PARTIAL" if sc >= 0.3 else "MISS")
        print(f"{tag} ({sc:.2f})")

        time.sleep(0.3)

    avg = total / len(test_cases) if test_cases else 0
    return avg, details
