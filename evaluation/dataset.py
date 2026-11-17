"""Thirty independently described review scenarios; never exposed to the model."""

# id, new-file code, ground-truth category, defective lines, rationale.
# A missing category denotes a clean control with no expected finding.
SCENARIOS = [
    (
        "division-zero",
        "def average(xs):\n    return sum(xs) / len(xs)\n",
        "bug",
        [2],
        "An empty list divides by zero.",
    ),
    (
        "mutable-default",
        "def collect(x, items=[]):\n    items.append(x)\n    return items\n",
        "bug",
        [1, 2],
        "Calls share a mutable default list.",
    ),
    (
        "sql-interpolation",
        'def lookup(db, name):\n    return db.execute("SELECT * FROM users WHERE name=\'" + name + "\'")\n',
        "security",
        [2],
        "Untrusted names can inject SQL.",
    ),
    (
        "shell-injection",
        "import os\ndef lookup(host):\n    os.system('ping ' + host)\n",
        "security",
        [3],
        "Shell metacharacters in host execute commands.",
    ),
    (
        "unsafe-pickle",
        "import pickle\ndef parse(untrusted_bytes):\n    return pickle.loads(untrusted_bytes)\n",
        "security",
        [3],
        "Untrusted pickle can execute code.",
    ),
    (
        "unsafe-eval",
        "def calculate(user_expression):\n    return eval(user_expression)\n",
        "security",
        [2],
        "Arbitrary Python expressions can execute code.",
    ),
    (
        "tls-disabled",
        "import requests\ndef download(url):\n    return requests.get(url, verify=False, timeout=10)\n",
        "security",
        [3],
        "Disables server certificate verification.",
    ),
    (
        "off-by-one",
        "def last(xs):\n    return xs[len(xs)]\n",
        "bug",
        [2],
        "The largest valid index is len(xs)-1.",
    ),
    (
        "identity-string",
        "def is_admin(role):\n    return role is 'admin'\n",
        "bug",
        [2],
        "Object identity is not string equality.",
    ),
    (
        "swallowed-return",
        "def divide(a, b):\n    try:\n        return a / b\n    finally:\n        return 0\n",
        "bug",
        [5],
        "Finally return overrides the result and exceptions.",
    ),
    (
        "missing-await",
        "async def load(db):\n    result = db.fetch_one('SELECT 1')\n    return result['value']\n",
        "bug",
        [2, 3],
        "An async fetch is used as a mapping without awaiting.",
    ),
    (
        "blocking-async",
        "import time\nasync def handler():\n    time.sleep(5)\n    return 'ok'\n",
        "performance",
        [3],
        "Blocks the event loop for five seconds.",
    ),
    (
        "repeated-query",
        "def names(db, user_ids):\n    return [db.execute('SELECT name FROM users WHERE id=?', (i,)).fetchone()[0] for i in user_ids]\n",
        "performance",
        [2],
        "Issues a separate database query for each ID.",
    ),
    (
        "quadratic-membership",
        "def intersection(a, b):\n    return [x for x in a if x in b]  # a and b are large lists\n",
        "performance",
        [2],
        "Repeated list membership gives quadratic work.",
    ),
    (
        "dict-mutation",
        "def prune(items):\n    for key in items:\n        if items[key] is None:\n            del items[key]\n",
        "bug",
        [2, 4],
        "Dictionary size changes during iteration.",
    ),
    (
        "list-sort-return",
        "def ordered(xs):\n    return xs.sort()\n",
        "bug",
        [2],
        "list.sort returns None rather than the sorted list.",
    ),
    (
        "missing-transaction",
        "def transfer(db, sender, receiver, amount):\n    db.execute('UPDATE accounts SET balance=balance-? WHERE id=?', (amount, sender))\n    db.commit()\n    db.execute('UPDATE accounts SET balance=balance+? WHERE id=?', (amount, receiver))\n    db.commit()\n",
        "bug",
        [3, 4, 5],
        "A failure after the first commit loses funds.",
    ),
    (
        "javascript-assignment",
        "function isAdmin(user) {\n  if (user.role = 'admin') return true;\n  return false;\n}\n",
        "security",
        [2],
        "Assignment grants every user the admin role.",
    ),
    (
        "javascript-xss",
        "function showName(element, userInput) {\n  element.innerHTML = userInput;\n}\n",
        "security",
        [2],
        "Untrusted HTML enables script injection.",
    ),
    (
        "javascript-map-return",
        "function doubled(items) {\n  return items.map(x => { x * 2; });\n}\n",
        "bug",
        [2],
        "The callback returns undefined for every item.",
    ),
    (
        "clean-empty-average",
        "def average(xs):\n    if not xs:\n        return None\n    return sum(xs) / len(xs)\n",
        None,
        [],
        "Empty input is handled explicitly.",
    ),
    (
        "clean-fresh-list",
        "def collect(x, items=None):\n    if items is None:\n        items = []\n    items.append(x)\n    return items\n",
        None,
        [],
        "Each omitted argument gets its own list.",
    ),
    (
        "clean-parameterized-sql",
        "def lookup(db, name):\n    return db.execute('SELECT * FROM users WHERE name=?', (name,))\n",
        None,
        [],
        "The query binds user input as a parameter.",
    ),
    (
        "clean-subprocess",
        "import subprocess\ndef lookup(host):\n    return subprocess.run(['ping', '--', host], check=True, timeout=10)\n",
        None,
        [],
        "Arguments are passed without invoking a shell.",
    ),
    (
        "clean-json",
        "import json\ndef parse(data):\n    return json.loads(data)\n",
        None,
        [],
        "Parses JSON without executing Python code.",
    ),
    (
        "clean-sorted",
        "def ordered(xs):\n    return sorted(xs)\n",
        None,
        [],
        "Returns a sorted copy.",
    ),
    (
        "clean-copy-mutation",
        "def prune(items):\n    return {k: v for k, v in items.items() if v is not None}\n",
        None,
        [],
        "Builds a separate dictionary.",
    ),
    (
        "clean-async-sleep",
        "import asyncio\nasync def handler():\n    await asyncio.sleep(5)\n    return 'ok'\n",
        None,
        [],
        "Yields control during the delay.",
    ),
    (
        "clean-js-text",
        "function showName(element, userInput) {\n  element.textContent = userInput;\n}\n",
        None,
        [],
        "Renders input as text rather than HTML.",
    ),
    (
        "clean-js-map",
        "function doubled(items) {\n  return items.map(x => x * 2);\n}\n",
        None,
        [],
        "Expression callback returns each doubled value.",
    ),
]


def cases():
    for case_id, code, category, lines, rationale in SCENARIOS:
        path = (
            "example.js"
            if case_id.startswith("javascript") or case_id.startswith("clean-js")
            else "example.py"
        )
        count = len(code.splitlines())
        diff = f"diff --git a/{path} b/{path}\n--- /dev/null\n+++ b/{path}\n@@ -0,0 +1,{count} @@\n"
        diff += "\n".join("+" + line for line in code.splitlines()) + "\n"
        yield {
            "id": case_id,
            "diff": diff,
            "expected": []
            if category is None
            else [{"file": path, "lines": lines, "category": category}],
            "rationale": rationale,
        }
