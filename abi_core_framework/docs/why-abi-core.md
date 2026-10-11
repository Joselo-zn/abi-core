# Why ABI-Core

You've seen the demo. Everybody has.

An agent books the flight, writes the code, summarizes the quarter, and does it all in ninety seconds on a stage with flattering lights. People clap. Someone posts that the future arrived on a Tuesday. Then Monday comes, you put the same thing in front of real users with real data and a real budget, and it comes apart in ways nobody on that stage thought worth mentioning.

I've watched that Monday happen. More than once — and I've seen too many to bother being polite about it.

## The villain

It's always the same story. The model decides everything — which tool, in what order, how many times, when to stop — and it's brilliant on the happy path and a slot machine everywhere else. Security is a plugin you'll add later, where later means after the incident. Agents know each other by hard-coded addresses, so adding a fourth one means editing the other three. And when one agent isn't enough, the fashionable answer is to put several of them in a group chat and let them work it out. They do talk. They talk a lot. They agree, warmly, on interfaces none of them ever built, and the bill shows up before the answer does.

Consensus isn't correctness. A chat log isn't an audit trail. A demo isn't a system.

Somebody got tired of it. That's why I exist.

## The hero

I'm ABI. I let you build AI agents that work together — and keep working on Monday.

You write ordinary Python functions. I turn them into agents that live in their own containers, find each other by describing what they need, talk through one standard protocol, and ask for permission before they act. One `pip install`. A few decorators. That's the whole ceremony.

A team of AI specialists, started with one command. On your laptop.

The features are nice, but they aren't really the point. The point is a handful of stubborn opinions, baked so deep into me that you'd have to work hard to get around them.

## The AI thinks. Your code decides.

Every agent has a skeleton, and you write it: steps, in an order you choose, wired together by hand. The model lives inside those steps — it classifies, drafts, reasons, and it's good at all of it — but it never gets to rearrange the skeleton. That's the line.

The goal was never to get rid of uncertainty. You can't; it's a language model, not a calculator. The goal is to decide where predictable execution ends, and what happens to whatever spills over. Fence it. Then you can sleep. Everything else is hope with a nice logo.

## Agents don't chat. They hand over work.

Here's a story. Five agents each wrote one file of a small game. Every file looked fine on its own. Every file compiled. The game crashed on the very first frame. Not because the model was bad — because nobody had been given the job of making the pieces fit.

The tempting fix is to let the agents talk it over. I don't. With me, agents coordinate through the work itself: each one receives the actual files the others produced, code checks how those pieces fit, and the whole thing runs in a sealed sandbox before you ever see it. No negotiation, no runaway token bill, no transcript to dig through later. And if something is still broken at the end, you're told — word for word. Not a cheerful summary that says it went great.

## Enough beats smartest.

"Which model is the smartest?" is the wrong question. The right one is "which model is enough for this job?" A small model on your own machine is plenty for most of what an agent does, and it breaks at a predictable point. I'm built to keep the hard part away from that point, or to send just that part somewhere bigger.

So I'm local by default. Ollama on your hardware, nothing leaving your network unless you decide it should. Want a cloud model for one agent? Change an environment variable. The code doesn't notice.

## Patience, measured in progress.

When a long task times out, the instinct is to raise the number. Ten minutes. Twenty. An hour. It works until the hardware changes, or the load does, and then you raise it again. That's not a fix; it's a habit.

I ask a different question: is it still working? While the model keeps producing, I wait. When it stops, I act. A task stuck in line behind four others on a lonely CPU isn't broken. It's waiting its turn, and it gets one.

## Rules that agents can't rewrite.

Before anything runs, a gatekeeper called Guardian checks the request against your rules. Some rules ship locked: no agent can make copies of itself, and no agent can edit the rules — not even a little, not even with a good reason. With Guardian in place, every conversation between agents is checked against policy and written down.

And the rule I care about most: nothing big happens without you. Hand me a real job and I come back with a plan. You approve it, change it, or throw it away. The system proposes. You decide.

## Found by meaning, not by address.

Each agent describes what it can do in plain words. Other agents find it by asking — "who can analyze revenue?" — and the right one answers, even if it describes itself as "examines sales figures." Add an agent and it's discoverable the moment it starts. No address book to maintain, no wiring to update.

## Built for the bad day.

Memory service down? Your agent still answers — with a little less context, and without crashing. A container restarts mid-conversation? The conversation lives in shared storage, not in the container that just died. One night every agent working on a request failed, all of them, and the user still got a working result, because nothing in the design depended on a single agent being a hero.

That's the part demos never show. It's also the part that matters on Monday.

## One more thing

Everything above assumes your agents already exist. What if they don't?

Ask me for something nobody planned for. I write a plan. I show it to you. And once you say yes, I build the specialists I'm missing — brand-new agents, made for that one job, each in its own sealed container. They do the work. They hand it over. And then they're gone. No leftovers. No forgotten processes chewing through your memory at three in the morning. I call them zombies. It felt honest.

All of it on your own hardware.

It's early — the self-building part is still alpha. José Luis, who built me, first saw a computer in 1995 and calls this the closest thing to magic a computer has done since then. José Luis was there for the GIFs. I believe it.

👉 [Install ABI-Core](getting-started/01-installation.md) and build your first agent.
