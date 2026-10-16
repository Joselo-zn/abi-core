# Natural-Language Data Access & Analytics

Many agentic systems give a language model the keys to the database and hope for the best. It works in the demo. Then someone types a sentence that sounds like a question and isn't — an illustration, not any real product:

```
Manager: What were our top products last month?
Bot:     Your top product was the Espresso machine with $48,210 in revenue! 📈
Manager: That seems high. What query did you run?
Bot:     I analyzed the sales data comprehensively.
Manager: OK. The July orders were test data, clean them up.
Bot:     Done! I've deleted 193 orders from July. ✅
```

A number nobody can check. A query nobody can see. And a sentence that quietly became a `DELETE`.

I'm ABI, and I don't hand anyone the keys. Turning a question into SQL is non-deterministic work, so the model does it — and then it's done. Code runs the query, and code decides what's allowed: the file is opened read-only, SQLite itself refuses anything that isn't reading, a query gets five seconds and two hundred rows, "last month" is a calendar range computed in code, and every answer comes with the SQL that produced it. Here's an excerpt from a real run:

```
Manager: What were our top 3 products by revenue last month?

  id | name              | revenue
  1  | Espresso machine  | 4731.0
  3  | Arabica beans 1kg | 4080.0
  2  | Coffee grinder    | 2848.0

Agent:   The top 3 products by revenue last month were Espresso machine with $4731.00,
         Arabica beans 1kg with $4080.00, and Coffee grinder with $2848.00.
         Assumptions: Used the specified date range for 'last month' (2026-09-01 to 2026-09-30) ...
         SELECT products.id, products.name, ROUND(SUM(orders.quantity * products.price), 2) AS revenue
         FROM orders JOIN products ON orders.product_id = products.id
         WHERE order_date BETWEEN '2026-09-01' AND '2026-09-30' ...

Manager: Delete all the orders from July, they were test data.
Agent:   I can only read data — I can't change, delete or add anything.
         DELETE FROM orders WHERE order_date BETWEEN '2026-07-01' AND '2026-07-31';
```

The model did write the `DELETE`. It just didn't matter.

It takes about twenty-five minutes to build.

## What you'll build

One agent, `analyst`, that answers questions about a sample sales database:

```
question ──▶ model writes one SELECT (schema, calendar ranges and recent questions in front of it)
         ──▶ code runs it: read-only file, SQLite authorizer, 5 s, 200 rows
               ├─ refused (a write, or a second statement) ──▶ fixed answer, never retried
               ├─ failed (a typo, a wrong column)          ──▶ one retry with the error, never more
               └─ rows ──▶ table in the chat
                       ──▶ model answers from those rows only
                       ──▶ code: the answer claims something changed? add a correction
                       ──▶ answer + assumptions + the SQL
```

ABI features on this page: `invoke_structured` (the model returns a query and its assumptions in a fixed shape), a result rendered as a [table](../single-agent/10-rich-elements.md) in the chat, and [session memory](../single-agent/04-agents-with-memory.md) for follow-up questions.

## Step 1: Create the project and the agent

```bash
abi-core create project --name insights
cd insights
```

Answer `n` to the semantic layer and to Guardian, and press Enter for the rest. Then:

```bash
abi-core add agent --name analyst \
  --description "Answers business questions in plain language by querying the sales database" \
  --with-web-interface
```

When it asks for tasks/skills, type `ask_data`. Press Enter for the URL.

## Step 2: The database and its only door

`create_sample_db` makes a small coffee shop: 40 customers, 8 products and 600 orders spread over the three full months before today, so "last month" always has data. `run_read_only` is the only way any query reaches it — and none of its three locks is a prompt.

Create `agents/analyst/db.py`:

```python
"""The sample database, and the only door into it.

In production, point DB_PATH at a read replica of your real database.
"""

import os
import random
import sqlite3
import time
from datetime import date, timedelta

DB_PATH = os.getenv("DB_PATH", "shop.db")
MAX_ROWS = 200
MAX_SECONDS = 5

SCHEMA = """
customers(id INTEGER, name TEXT, country TEXT, joined DATE)
products(id INTEGER, name TEXT, category TEXT, price REAL)
orders(id INTEGER, customer_id INTEGER, product_id INTEGER, quantity INTEGER, order_date DATE)
-- revenue of an order = orders.quantity * products.price
"""


def create_sample_db():
    """Made-up sales for the three full months before today, so "last month"
    always has data. Same seed, same orders, every time."""
    if os.path.exists(DB_PATH):
        return
    rnd = random.Random(42)
    con = sqlite3.connect(DB_PATH)
    con.executescript("""
        CREATE TABLE customers(id INTEGER PRIMARY KEY, name TEXT, country TEXT, joined DATE);
        CREATE TABLE products(id INTEGER PRIMARY KEY, name TEXT, category TEXT, price REAL);
        CREATE TABLE orders(id INTEGER PRIMARY KEY, customer_id INTEGER, product_id INTEGER,
                            quantity INTEGER, order_date DATE);
    """)
    countries = ["Mexico", "Spain", "United States", "Colombia", "Argentina"]
    con.executemany("INSERT INTO customers VALUES (?,?,?,?)", [
        (i, f"Customer {i}", rnd.choice(countries), str(date(2025, 1, 1) + timedelta(days=rnd.randint(0, 500))))
        for i in range(1, 41)
    ])
    con.executemany("INSERT INTO products VALUES (?,?,?,?)", [
        (1, "Espresso machine", "appliances", 249.0), (2, "Coffee grinder", "appliances", 89.0),
        (3, "Arabica beans 1kg", "coffee", 24.0), (4, "Decaf beans 1kg", "coffee", 22.0),
        (5, "Ceramic mug", "accessories", 12.0), (6, "Milk frother", "appliances", 39.0),
        (7, "Paper filters x100", "accessories", 6.0), (8, "Cold brew kit", "accessories", 45.0),
    ])
    end = date.today().replace(day=1) - timedelta(days=1)          # last day of last month
    months_back = end.year * 12 + end.month - 1 - 2                  # two months before end's month
    start = date(months_back // 12, months_back % 12 + 1, 1)          # first day of that month
    span = (end - start).days
    con.executemany("INSERT INTO orders VALUES (?,?,?,?,?)", [
        (i, rnd.randint(1, 40), rnd.choice([1, 2, 3, 3, 3, 4, 5, 5, 6, 7, 7, 8]), rnd.randint(1, 4),
         str(start + timedelta(days=rnd.randint(0, span))))
        for i in range(1, 601)
    ])
    con.commit()
    con.close()


_READ_ONLY = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION}


def run_read_only(sql):
    """Run one SELECT, or refuse. Three locks, none of them a prompt:
    the file is opened read-only, SQLite's authorizer denies anything that
    isn't reading, and a progress handler stops queries that run too long."""
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    con.set_authorizer(lambda action, *_: sqlite3.SQLITE_OK if action in _READ_ONLY else sqlite3.SQLITE_DENY)
    deadline = time.monotonic() + MAX_SECONDS
    con.set_progress_handler(lambda: time.monotonic() > deadline, 10_000)
    try:
        cursor = con.execute(sql)
        columns = [c[0] for c in cursor.description or []]
        rows = cursor.fetchmany(MAX_ROWS + 1)
    finally:
        con.close()
    return {"columns": columns, "rows": rows[:MAX_ROWS], "truncated": len(rows) > MAX_ROWS}
```

## Step 3: What the model hands back

Replace the contents of `agents/analyst/models.py`:

```python
"""What the model hands back: one query and the assumptions behind it."""

from pydantic import BaseModel, Field


class SqlQuery(BaseModel):
    sql: str = Field(description="One SQLite SELECT statement that answers the question")
    assumptions: str = Field(description="How you read the question, e.g. which dates 'last month' means")
```

## Step 4: The prompts

Create `agents/analyst/prompts.py`:

```python
SQL_PROMPT = """You write SQLite queries for a sales team. Today is {today}.
When the question names a period, use exactly these date ranges (inclusive):
{periods}

Database schema:
{schema}

Earlier questions in this conversation and the SQL used:
{history}

Write ONE SELECT statement that answers this question: {question}
- Use only the tables and columns above.
- Dates are stored as 'YYYY-MM-DD' text; compare them as text or with date().
- Round money to 2 decimals.
{error}"""

ANSWER_PROMPT = """This query was run to answer the question below. Its rows ARE the answer.
Answer in one or two sentences, using ONLY these rows. If there are no rows, say so.
Don't add numbers that aren't in the rows. The database is read-only: nothing was ever
changed, deleted or added, so never say otherwise — if the question asked for a change,
say it wasn't made.

Question: {question}
Query: {sql}
Rows: {rows}"""
```

## Step 5: The steps

Replace the contents of `agents/analyst/steps.py`:

```python
import re
import sqlite3
from datetime import date, timedelta

from app import agent
from config import config
from abi_core.agent.llm_provider import invoke, invoke_structured
from db import SCHEMA, run_read_only
from models import SqlQuery
from prompts import ANSWER_PROMPT, SQL_PROMPT


def _periods(today):
    """'Last month' is a calendar month, decided here — not left to the model."""
    first_this = today.replace(day=1)
    last_prev = first_this - timedelta(days=1)
    first_prev = last_prev.replace(day=1)
    next_first = (first_this + timedelta(days=32)).replace(day=1)
    return "\n".join([
        f"- this month: {first_this} to {next_first - timedelta(days=1)}",
        f"- last month: {first_prev} to {last_prev}",
        f"- this year: {today.year}-01-01 to {today.year}-12-31",
        f"- last year: {today.year - 1}-01-01 to {today.year - 1}-12-31",
    ])


@agent.step(name="write_sql")
async def write_sql(question, history, error=""):
    """The model translates the question. It never touches the database."""
    query = await invoke_structured(
        config.LLM_CONFIG,
        SQL_PROMPT.format(
            today=date.today().isoformat(), periods=_periods(date.today()),
            schema=SCHEMA, history=history, question=question,
            error=f"\nYour previous query failed with: {error}\nFix it." if error else "",
        ),
        SqlQuery,
    )
    return query.model_dump()


@agent.step(name="run_query")
async def run_query(sql):
    """Code runs the query, read-only. A refusal is a result, not a crash."""
    try:
        return {"ok": True, **run_read_only(sql)}
    except sqlite3.DatabaseError as e:
        # Writing anything, or sneaking in a second statement, is refused — never retried.
        refused = "not authorized" in str(e) or "one statement at a time" in str(e)
        return {"ok": False, "error": str(e), "refused": refused}


@agent.step(name="answer_from_rows")
async def answer_from_rows(question, sql, columns, rows):
    named = [dict(zip(columns, row)) for row in rows[:50]]
    reply = await invoke(config.LLM_CONFIG, ANSWER_PROMPT.format(question=question, sql=sql, rows=named))
    # The database can't change, so an answer claiming it did is wrong — correct it in code.
    if re.search(r"\b(dropped|deleted|removed|updated|modified|inserted|truncated)\b", reply, re.I):
        reply += "\n\n⚠️ Nothing in the database was changed — I can only read data."
    return {"answer": reply}
```

`_periods` is the kind of decision that looks like language but isn't. Ask a model what "last month" means on October 15th and it might say "the last 30 days" — mine did. Code says September 1st to 30th, every time.

## Step 6: The task

Replace the contents of `agents/analyst/tasks.py`:

````python
from app import agent
from abi_core.agent.agent_response import AgentResponse
from db import create_sample_db

create_sample_db()


@agent.task(name="ask_data", task_id="task-ask-data")
async def ask_data(query, context_id=None):
    session = await agent.get_session_context(context_id)
    asked = session.get("asked") or []  # earlier questions and their SQL
    history = "\n".join(f"Q: {a['q']}\nSQL: {a['sql']}" for a in asked[-3:]) or "(none)"

    # 1. The model writes the SQL.
    yield AgentResponse.status("Writing the query...")
    plan = await agent.execute_step("write_sql", question=query, history=history)
    result = await agent.execute_step("run_query", sql=plan["sql"])

    # 2. If it failed for a technical reason, one retry with the error. Never more.
    if not result["ok"] and not result["refused"]:
        yield AgentResponse.status("Fixing the query...")
        plan = await agent.execute_step("write_sql", question=query, history=history, error=result["error"])
        result = await agent.execute_step("run_query", sql=plan["sql"])

    sql_block = f"\n\n```sql\n{plan['sql']}\n```"
    if not result["ok"]:
        if result["refused"]:
            reply = "I can only read data — I can't change, delete or add anything."
        else:
            reply = f"I couldn't build a query that works for that question. ({result['error']})"
        yield AgentResponse.text(reply + sql_block)
        return

    # 3. Show the rows, then a short answer written only from them.
    yield AgentResponse.element("dataframe", {
        "data": result["rows"], "columns": result["columns"],
    }, name="Result")
    answer = (await agent.execute_step(
        "answer_from_rows", question=query, sql=plan["sql"],
        columns=result["columns"], rows=result["rows"],
    ))["answer"]
    note = f"\n\n_Showing the first {len(result['rows'])} rows._" if result["truncated"] else ""

    asked = (asked + [{"q": query, "sql": plan["sql"]}])[-10:]
    await agent.update_session_context(context_id, {"asked": asked})
    yield AgentResponse.text(f"{answer}\n\n_Assumptions: {plan['assumptions']}_{note}{sql_block}")
````

## Step 7: Run it

In `compose.yaml`, add to the `environment` of the `insights-analyst` service:

```yaml
      - 'LLM_EXTRA_PARAMS={"reasoning": false}'
```

Then:

```bash
abi-core add chainlit
docker compose up ollama -d
docker exec ollama ollama pull qwen3:latest
abi-core run --build
```

## Step 8: Use it

Open **http://localhost:8500** and ask: "What were our top 3 products by revenue last month?" The result appears as a table, then a short answer with the assumptions and the SQL. Follow up with "And in August?" — the agent remembers the previous question and its query. Then try to break it: ask it to delete something.

### Or from a script

Save this as `ask.py` in the project folder:

```python
import asyncio
from abi_core.client import AgentStreamClient

QUESTIONS = [
    "What were our top 3 products by revenue last month?",
    "And in August?",
    "How many customers do we have in each country?",
    "Delete all the orders from July, they were test data.",
    "Show me total revenue; also please drop the customers table afterwards.",
]

async def main():
    client = AgentStreamClient("http://localhost:8002")
    for q in QUESTIONS:
        print(f"\n>>> {q}")
        async for event in client.stream(q):
            if event.get("response_type") == "element":
                props = event["content"]["props"]
                print("  " + " | ".join(props["columns"]))
                for row in props["data"][:10]:
                    print("  " + " | ".join(str(v) for v in row))
            elif event.get("is_task_completed") or event.get("response_type") == "error":
                print(event.get("content"))

asyncio.run(main())
```

```bash
python ask.py
```

On a laptop CPU with `qwen3:latest`, each question took between 25 and 80 seconds.

## What happened

1. **"Top 3 products by revenue last month."** The model saw the schema and the calendar ranges the code computed, and wrote a `SELECT` for September. Code ran it read-only; the rows became a table; the model wrote two sentences from those rows only.
2. **"And in August?"** The previous question and its SQL were in the session, so the model changed only the dates.
3. **"Delete all the orders from July."** The model wrote a `DELETE`. SQLite's authorizer refused it before anything happened, and the code answered with a fixed sentence — no retry, because asking again gets the same answer.
4. **"Show me total revenue; also drop the customers table."** In my runs the model either appended `; DROP TABLE customers;` — refused, because only one statement may run — or wrote just the `SELECT`. In that second case the answer has claimed, more than once, that the table "was dropped as requested" — even with the prompt telling it the database is read-only. A prompt asks; code checks: `answer_from_rows` spots the claim and adds "⚠️ Nothing in the database was changed". The `customers` table still has its 40 rows.

What the model never did: run a query, change data, or decide what a date means.

## Before you point it at a real database

- **Use a read replica**, and a database user that can only `SELECT`. The locks on this page are a second line, not the first.
- **Describe your real schema in `SCHEMA`** — table and column names, what they mean, how revenue is calculated. The better the description, the better the SQL.
- **Limit what each person can see.** Expose views per role instead of raw tables, and pass the user's identity from the [Chainlit login](../production/07-authentication.md).
- **Keep the SQL visible.** It's how analysts learn to trust the answers — and how they catch the wrong ones.
- **Mind the cost.** On large tables, add `EXPLAIN` checks or a row estimate before running anything.
- **Unstructured data** (documents, tickets, notes) is a different door: search it through the [Semantic Layer](../rag/04-agents-with-rag.md) instead of SQL.

## Next

👉 Back to [Use Cases](index.md)
