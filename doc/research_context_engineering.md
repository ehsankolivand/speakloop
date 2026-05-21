# CLAUDE.md and Context Engineering — A Practical Guide for Android Developers

> **Date anchor:** 2026-05-03 **Reader:** Senior Android developer, English B1, no prior knowledge of either topic.

---

## 1. Start here — what this guide is and what you will know at the end

This guide answers one question: how do I make Claude Code useful on a real Android codebase, day after day? It teaches two things. First, **context engineering** — the discipline of choosing what an AI model sees in one turn. Second, **CLAUDE.md** — a small text file that is the most concrete way to apply that discipline in Claude Code.

When you finish this guide, you will be able to write a `CLAUDE.md` for your own Android project tomorrow morning. You will know where the file lives, what to put in it, what to leave out, and when to update it. You will also understand _why_ the file works, so you can keep it healthy over time.

**In short:** learn the idea, then learn the file, then write your own.

---

## 2. The problem, in plain words

This section answers: why does any of this matter?

Claude Code starts each session with a clean memory. It does not remember yesterday. If you tell it on Monday that your project uses Hilt, not Koin, it will forget on Tuesday. If you tell it your tests run with `./gradlew :app:testDebugUnitTest`, you will type that again next week. This wastes time. Worse, when you forget to repeat one rule, the agent makes a mistake that looks small but breaks something.

The same problem appears in another way. You can paste a lot into the chat. The model has a large context window — the space of tokens it can read in one turn. But research shows model accuracy drops as that space fills up. Anthropic calls this **context rot**, and points to a 2025 study from Chroma Research showing performance falls on simple tasks as input grows. So you cannot just dump everything in. You must choose.

**In short:** the agent forgets between sessions and gets confused inside a session. Both problems need a fix.

---

## 3. What is context, really

This section answers: what does the model actually see?

In Anthropic's words, **context** is "the set of tokens included when sampling from a large-language model." A token is a small piece of text. Everything that reaches the model in one turn is context. Nothing else exists for the model in that turn.

Here are the layers, in the order they usually arrive:

|Layer|What it is|Who controls it|
|---|---|---|
|System prompt|Top-level instructions for the model|The tool (Claude Code) plus your settings|
|Tool definitions|Names and descriptions of tools the model can call|The tool|
|Project memory (CLAUDE.md)|Persistent project rules you wrote|You|
|User message|What you typed this turn|You|
|Tool results|Output of files read, commands run|The agent loop|
|Conversation history|Earlier turns in this session|The agent loop|

A simple diagram of one turn:

```
+---------------------------------------------------------+
|                    CONTEXT WINDOW                       |
|                                                         |
|  [System prompt]  [Tools]  [CLAUDE.md content]          |
|  [Earlier turns and their tool results]                 |
|  [Your new message]                                     |
|                                                         |
|              ---> Model reads all of this --->          |
+---------------------------------------------------------+
```

**In short:** context is everything the model sees in one turn. Every layer takes space. Space is finite.

---

## 4. What is context engineering

This section answers: what is this discipline, exactly?

The canonical source is Anthropic's engineering blog post _Effective context engineering for AI agents_, published 29 September 2025. The post defines it like this:

> "**Context engineering** refers to the set of strategies for curating and maintaining the optimal set of tokens (information) during LLM inference, including all the other information that may land there outside of the prompts."

In plain words: context engineering is the work of choosing which tokens go into the window, in what order, and which do not. It also covers what you remove as the session grows.

How does this differ from prompt engineering? Anthropic frames context engineering as the "natural progression" of prompt engineering. Prompt engineering is about writing one good instruction. Context engineering is about managing the whole state — system prompt, tools, files the agent has read, message history, memory — across many turns. Prompt engineering is one part of context engineering, not the whole thing.

A short rule: **prompt engineering is what you write once. Context engineering is what stays right across a long session.**

**In short:** context engineering is curating tokens for the whole life of an agent, not just one prompt.

---

## 5. The four context failure modes

This section answers: what does it look like when context goes wrong?

The clearest names for these failures come from Drew Breunig, in two posts: _How Long Contexts Fail_ (22 June 2025) and _How to Fix Your Context_ (26 June 2025). Simon Willison's notes from 29 June 2025 helped popularize the four-mode framing. Anthropic itself does not use these exact words; Anthropic talks about "context rot" and lost attention. But the four-mode list is the most precise vocabulary in the field today.

**Context poisoning.** A wrong fact enters the context, and the model keeps using it. Example: in turn three, the agent wrote a hallucinated function name, `RoomDb.openSync()`. That name does not exist. Now the agent quotes it in turns four through ten, and every plan it makes is built on a phantom API.

**Context distraction.** The context grows so long that the model leans on its own history instead of its training. The Gemini Pokémon agent showed this past about 100,000 tokens — it began repeating earlier moves rather than planning new ones. In coding, you see this when an agent keeps editing the same file the same wrong way, even after you correct it.

**Context confusion.** Extra information that is not needed for this task pulls the model off course. Example: you load all 80 tools from many MCP servers — services that expose tools to Claude — when the task only needs `read_file` and `edit_file`. The model now spends attention reading tool descriptions for tools it will never call, and may pick the wrong one. Research cited by Breunig shows tool selection accuracy drops sharply past about 30 tools.

**Context clash.** Two pieces of context disagree. Example: your `CLAUDE.md` says "use Koin for DI." A README in a sub-module says "use Hilt." A user message says "always reply in JSON." A tool result is XML. The model picks one rule, somewhat at random, and you cannot predict which.

**In short:** wrong facts compound (poisoning); long history dominates (distraction); irrelevant content pollutes (confusion); contradictions break trust (clash).

---

## 6. The five principles of good context

This section answers: what rules keep context healthy?

These five rules are derived from the Anthropic post and the Claude Code memory docs. Each rule has one short example.

**1. Smallest set of high-signal tokens.** Anthropic's guiding principle: "find the smallest possible set of high-signal tokens that maximize the likelihood of some desired outcome." Cut anything that does not earn its place.

- _Before:_ a 1,200-line `CLAUDE.md` that lists every dependency version.
- _After:_ a 180-line `CLAUDE.md` with a one-line pointer: "See `gradle/libs.versions.toml` for versions."

**2. Stable content first, dynamic content last.** Stable text near the start of the prompt also matches how prompt caching works (see Section 15). Anthropic's request order is: tools, then system, then messages. Place fixed material at the front. Place variable material at the end.

- _Before:_ paste today's task before the project rules.
- _After:_ keep the project rules in `CLAUDE.md` (loaded first), then paste today's task in your message (last).

**3. Just-in-time loading over upfront dumping.** Do not load everything you might need. Load identifiers, then fetch on demand. The Anthropic post: "agents built with the 'just in time' approach maintain lightweight identifiers (file paths, stored queries, web links, etc.) and use these references to dynamically load data into context at runtime using tools."

- _Before:_ paste the full content of `BillingRepository.kt` into the message.
- _After:_ say "Read `feature-billing/src/main/.../BillingRepository.kt`" and let the agent open it.

**4. Clear boundaries between instructions and data.** Use Markdown headings or XML tags to mark sections. The Anthropic docs recommend dividing prompts into sections like `<background_information>`, `<instructions>`, or `## Tool guidance`.

- _Before:_ a long paragraph mixing rules, file paths, and example code.
- _After:_ `## Build commands`, `## Conventions`, `## Do not do`, each as its own list.

**5. Compact when the window grows.** When history is long, summarize it. Claude Code's `/compact` does this for you: it asks the model to summarize the conversation and starts a new window with that summary. The key point: project-root `CLAUDE.md` is re-injected after `/compact`, but nested `CLAUDE.md` files in subdirectories are not — they reload only when the agent next reads a file in that subdirectory.

- _Before:_ a 200-turn session that drifts and forgets.
- _After:_ run `/compact` at a logical break, then continue with a clean window.

**In short:** small, stable-first, just-in-time, well-structured, and compacted when needed.

---

## 7. Now, CLAUDE.md — what it is

This section answers: what file are we actually talking about?

`CLAUDE.md` is a plain Markdown file that gives Claude Code persistent instructions for a project, your personal workflow, or your whole organization. The official Claude Code memory documentation says: "You write these files in plain text; Claude reads them at the start of every session."

There is more than one place a `CLAUDE.md` can live. The docs list four scopes, ordered from most general to most specific:

|Scope|Location|Shared with|
|---|---|---|
|Managed policy|`/Library/Application Support/ClaudeCode/CLAUDE.md` (macOS), `/etc/claude-code/CLAUDE.md` (Linux/WSL), `C:\Program Files\ClaudeCode\CLAUDE.md` (Windows)|Everyone in the organization|
|Project|`./CLAUDE.md` or `./.claude/CLAUDE.md`|The team, via Git|
|User|`~/.claude/CLAUDE.md`|Just you, all projects|
|Local|`./CLAUDE.local.md` (add to `.gitignore`)|Just you, this project|

How loading works (verbatim from the docs, restated):

- Claude Code walks up the directory tree from your working directory. It loads every `CLAUDE.md` and `CLAUDE.local.md` it finds along the way.
- All discovered files are **concatenated**, not overridden. Files closer to the working directory are read **last**.
- Within a directory, `CLAUDE.local.md` is appended after `CLAUDE.md`.
- A `CLAUDE.md` in a **subdirectory** below your working directory is **not loaded at launch**. It loads on demand when Claude reads a file inside that subdirectory.
- Block-level HTML comments (`<!-- ... -->`) are stripped before the content is injected into context. Use them for human-only notes.
- Imports work with `@path/to/file` syntax. Imported files load at launch with the parent. Maximum import depth is 5 hops.
- `AGENTS.md` is **not** read by Claude Code. If your repo has one, create a `CLAUDE.md` that imports it: `@AGENTS.md`.

What is automatic and what is not, exactly:

- **Automatic:** loading at session start; concatenation across the directory tree; re-injection of project-root `CLAUDE.md` after `/compact`; auto memory writes (in v2.1.59+, on by default).
- **Not automatic:** updating the file when conventions change; pruning stale content; deciding what belongs in project memory versus user memory versus a skill.

The docs add an important reality check: "CLAUDE.md content is delivered as a user message after the system prompt, not as part of the system prompt itself. Claude reads it and tries to follow it, but there's no guarantee of strict compliance, especially for vague or conflicting instructions." This is why the file must be specific.

**In short:** `CLAUDE.md` is a Markdown file Claude Code reads at the start of every session, from several scopes at once, in a fixed order, with documented loading rules.

---

## 8. Why CLAUDE.md is context engineering in practice

This section answers: how does the file connect to the discipline?

`CLAUDE.md` is the cleanest tool you have for applying the five principles every working day:

- It is **the smallest, highest-signal block** of project knowledge — when you keep it short.
- It is **stable**, so it sits at the front of the prompt and caches well (Section 15).
- It can **point** to deeper docs instead of inlining them, supporting just-in-time loading.
- It uses **Markdown headings** as boundaries between instruction sections.
- It is **compaction-safe** at the project root: it is re-injected automatically after `/compact`.

So `CLAUDE.md` is not a separate thing from context engineering. It is the most direct, version-controlled, team-shared way to do context engineering on a real codebase. Most of your context-engineering work as an Android developer happens inside this file.

**In short:** the file is where the discipline lives day to day.

---

## 9. Anatomy of a good CLAUDE.md

This section answers: what sections should the file have?

Below is the structure most strong examples follow. Each part has one short reason and one Android-flavored line so you can picture it.

**Project overview (2–3 sentences).** Why: the agent must know what the project is before it edits anything. Example: "WalletFlow is an Android wallet app written in Kotlin and Jetpack Compose. It manages user accounts, transactions, and budgeting."

**Architecture summary.** Why: the agent must know which module depends on which. Example: "Three layers: `:app` → `:feature-*` → `:core-*`. Features never import other features. They go through `:core-domain`."

**Build and test commands.** Why: the agent should run the right command, not invent one. Example: "Build: `./gradlew :app:assembleDebug`. Unit tests: `./gradlew testDebugUnitTest`. Format: `./gradlew ktlintFormat`."

**Conventions and patterns.** Why: the agent should not invent a style. Example: "Use `StateFlow`, not `LiveData`. Composables are PascalCase. ViewModels expose immutable state."

**Known traps and gotchas.** Why: this is where past pain becomes future safety. Example: "Do not call `Dispatchers.Main` directly in repositories. Use `dispatcherProvider.main` so tests can swap it."

**Things the agent should not do.** Why: explicit "no" rules are more reliable than implicit ones. Example: "Never edit files under `build/` or `gradle/wrapper/`. Never bump library versions without asking."

**Pointers to deeper documents.** Why: the file stays small; long docs live elsewhere and load only when needed. Example: "For module-specific rules, see each module's own `CLAUDE.md`. For release process, see `docs/release.md`."

**In short:** seven small parts, each one short, each one specific.

---

## 10. A complete real example

This section answers: what does a good Android `CLAUDE.md` look like end to end?

Below is a complete `CLAUDE.md` for a fictional Android wallet app called **WalletFlow**, similar to a real project. Each section has a short comment under it explaining why it is written that way. You can copy this file and adapt it. It is about 200 lines.

```markdown
# WalletFlow — Project Memory for Claude Code

<!-- Comment for humans only. This file is read by Claude Code at the
start of every session. Keep it under 200 lines. Update it on Fridays. -->

## 1. What this project is

WalletFlow is an Android app for personal wallets. Users add accounts,
record transactions, and see budgets. It is published on Google Play.
The codebase is a multi-module Gradle project written in Kotlin with
Jetpack Compose. Minimum SDK 26, target SDK 35.

<!-- Why: two or three sentences are enough. The agent now knows the
domain, the platform, and the scope. Do not write a marketing pitch. -->

## 2. Tech stack (canonical list)

- Language: Kotlin only (no Java in new code).
- UI: Jetpack Compose with Material 3. No XML layouts in new screens.
- DI: Hilt.
- Database: Room.
- Networking: Retrofit + OkHttp + kotlinx.serialization.
- Async: Coroutines and Flow. No RxJava. No LiveData.
- Build: Gradle with Kotlin DSL and a version catalog at
  `gradle/libs.versions.toml`.
- Tests: JUnit4, Robolectric, Turbine, MockK, Espresso for UI tests.

<!-- Why: a fixed list reduces context confusion. The agent stops
inventing alternatives like Koin or LiveData. -->

## 3. Module layout

Top-level Gradle modules:

- `:app` — application module. Wires DI, navigation, and the entry
  Activity. Imports features only.
- `:feature-accounts`, `:feature-transactions`, `:feature-budget` —
  one module per user-facing feature. Each has `ui`, `data`, `di`.
- `:core-domain` — pure Kotlin. Use cases and domain models. No
  Android imports here.
- `:core-data` — Room entities, DAOs, repositories.
- `:core-network` — Retrofit services and DTOs.
- `:core-ui` — design system: theme, colors, reusable composables.
- `:core-testing` — fakes, fixtures, test rules. `testFixtures` only.

Dependency rule: features depend on `:core-*`. Features never depend
on other features. `:core-domain` depends on nothing else in the repo.

<!-- Why: the agent now knows what may import what. This prevents the
single most common mistake: a feature importing another feature. -->

## 4. Build and test commands

Run these from the repo root:

- Format: `./gradlew ktlintFormat`
- Lint: `./gradlew ktlintCheck detekt`
- Build debug APK: `./gradlew :app:assembleDebug`
- Unit tests (one module): `./gradlew :feature-accounts:testDebugUnitTest`
- All unit tests: `./gradlew testDebugUnitTest`
- Instrumented tests on a connected device: `./gradlew connectedDebugAndroidTest`
- Generate Room schemas (when entities change): `./gradlew :core-data:kspDebugKotlin`

Always run `ktlintFormat` and `testDebugUnitTest` before claiming a
change is done.

<!-- Why: precise commands. The agent stops guessing "gradle test"
and stops asking "how do I run tests in this repo?". -->

## 5. Conventions

### Kotlin style

- File names match the top-level class: `AccountRepository.kt`.
- Public functions get KDoc only when behavior is non-obvious.
- No `!!`. Use `requireNotNull` with a message, or model nullability.
- Prefer `val` over `var`. Make data classes immutable.

### Compose

- Composables are PascalCase. Stateless composables take state as a
  parameter and emit events as lambdas.
- One `*Screen` composable per route. The screen reads its
  ViewModel via `hiltViewModel()` and forwards state down.
- Do not call suspending functions inside composables. Use
  `LaunchedEffect` or move the call to the ViewModel.
- Theme tokens come from `:core-ui`. Do not hardcode colors.

### State

- ViewModels expose `StateFlow<UiState>`. UiState is a sealed
  interface or a single data class with nullable fields.
- Side effects use `Channel<UiEffect>` exposed as `Flow<UiEffect>`,
  collected with `collectAsStateWithLifecycle` or `LaunchedEffect`.

### Data

- Repositories expose `Flow` for reads and `suspend` for writes.
- Room is the source of truth for transactions. Network is a sync
  source. Offline-first.
- Never expose Room entities to the UI layer. Map to domain models
  in the repository.

### DI

- One Hilt module per feature, in `feature-x/di/FeatureXModule.kt`.
- Bind interfaces with `@Binds`. Provide concrete classes with
  `@Provides` only when construction needs configuration.

<!-- Why: each rule is short, concrete, and verifiable. Vague rules
like "write clean code" do not change behavior. -->

## 6. Known traps

- The Room migration from v7 to v8 added a non-null column with a
  default. If you change `TransactionEntity`, write a migration test
  in `:core-data` using `MigrationTestHelper`.
- `BudgetCalculator.recompute()` is called from a `WorkManager` job.
  Do not make it suspend. Wrap async work inside instead.
- Espresso tests fail on API 26 emulators if `WindowInsets` are
  toggled. Use the `EdgeToEdgeRule` from `:core-testing`.
- ProGuard removes `kotlinx.serialization` classes if you add a new
  serializable type without `@Serializable`. The CI catches this on
  release builds, not debug.

<!-- Why: this section is the file's most valuable part over time.
Every entry here is paid for in past pain. -->

## 7. Things to never do

- Never edit `build/`, `.gradle/`, or `gradle/wrapper/`.
- Never change versions in `libs.versions.toml` without an explicit
  request from a human.
- Never add a new third-party library without asking. We prefer
  AndroidX and Kotlin standard library.
- Never use `runBlocking` in production code. Tests only.
- Never commit anything under `app/release/` or signed artifacts.
- Never disable a test to make CI green. Fix it or mark it
  `@Ignore` with a TODO and a ticket reference.

<!-- Why: explicit prohibitions are the cheapest way to prevent
high-cost mistakes. -->

## 8. Pointers (do not inline)

- Module-specific details live in each module's own `CLAUDE.md`.
  Those load only when Claude reads files in that module.
- Release process: `docs/release.md`.
- Backend API contract: `docs/api.md`.
- Architecture decision records: `docs/adr/`.

<!-- Why: keeps this file small. The deep docs load only when
needed, supporting just-in-time context. -->

## 9. How to use this file

If you find yourself correcting Claude on something twice, add it
here. If something here is wrong, fix it here first, in the same
commit as the code change. Treat this file as part of the codebase.
```

**In short:** one short header per concern, real Android commands, a "do not do" list, and pointers instead of inlined docs.

---

## 11. How to write one for your own project — a step-by-step

This section answers: what do I do tomorrow morning?

1. **Spend ten minutes listing what you wish the agent already knew.** Open a notepad. Write every fact you would tell a new teammate on day one: stack, modules, commands, traps. Do not edit yet.
2. **Group the list into the anatomy from Section 9.** Project overview, stack, modules, commands, conventions, traps, "never do," pointers.
3. **Write the first draft. Keep it under 400 lines.** The docs target is 200 lines; 400 is a hard ceiling. If you go longer, your file is hiding rules you do not need.
4. **Run `/init` if you have nothing.** This Claude Code command analyzes your repo and suggests a starting `CLAUDE.md`. If a file already exists, `/init` suggests improvements rather than overwriting it. Set `CLAUDE_CODE_NEW_INIT=1` for an interactive multi-phase flow.
5. **Use it for one week.** Keep a small `notes.md` in your home folder. Every time the agent does something the file should have prevented, write one line there.
6. **On Friday, update the file based on those notes.** Add new traps, new "never do" rules, new commands. Delete anything stale. Commit it.
7. **Repeat.** The file becomes stronger every week.

**In short:** list, group, draft short, use, observe, update.

---

## 12. Common mistakes

This section answers: what goes wrong, and how do I fix it?

**Too long.** Symptom: the agent ignores rules at the bottom of the file. Cause: the file is 800 lines, full of background. The Claude Code docs say "files over 200 lines consume more context and may reduce adherence." Fix: trim to 200 lines, move long content to separate files referenced by `@import`, or to `.claude/rules/` with `paths` frontmatter so they load only for matching files.

**Too vague.** Symptom: the agent writes "clean code" that does not match your style. Cause: rules like "write clean code" or "test your changes" cannot be checked. Fix: replace each vague rule with a concrete one. "Use 2-space indentation," "Run `./gradlew ktlintFormat` before commits."

**Mixing data and instructions.** Symptom: the agent quotes a config value as a rule, or follows a code snippet as instruction. Cause: data and rules sit in the same paragraph. Fix: use Markdown headings to separate them. Put rules under `## Conventions`, examples in fenced code blocks, data in a referenced file.

**Stale.** Symptom: the agent uses a library you removed three months ago. Cause: nobody updated the file. Fix: review every Friday. Tie updates to PRs that change conventions. If a rule changes, the same PR updates `CLAUDE.md`.

**Duplicated across files.** Symptom: the same rule appears in `CLAUDE.md`, the README, and a wiki, in three slightly different versions. Cause: copy-paste. This causes context clash (Section 5). Fix: keep one source of truth. Reference it from the others.

**Telling instead of showing.** Symptom: the agent follows the letter of a rule but misses the spirit. Cause: the rule is text without an example. Fix: pair every non-obvious rule with one short example block.

**In short:** keep it short, concrete, separated, fresh, single-source, and shown by example.

---

## 13. CLAUDE.md vs other tools — when to use what

This section answers: where should this knowledge live?

|Tool|Loaded when|Use it for|
|---|---|---|
|`CLAUDE.md` (project)|Every session, automatic|Facts and rules that apply to every session in this project. Build commands, conventions, "never do" list.|
|`CLAUDE.md` (user, `~/.claude/CLAUDE.md`)|Every session, all your projects|Personal preferences across projects. "I prefer concise explanations."|
|`CLAUDE.local.md`|Every session, this project, only your machine|Sandbox URLs, test accounts, local secrets-free notes. Add to `.gitignore`.|
|`.claude/rules/*.md`|At launch (or when matching files open, with `paths`)|Topic-scoped rules for big projects. "API rules," "testing rules." Loads with same priority as `.claude/CLAUDE.md` unless `paths` is set.|
|Slash commands (`.claude/commands/*.md`)|When you type `/name`|Repeatable workflows you trigger by name. "Run a code review." "Create a feature module."|
|Skills (`.claude/skills/`, `~/.claude/skills/`)|When triggered by Claude or by you|Procedural knowledge with conditional triggers across projects. Loaded on demand.|
|Auto memory|Every session, machine-local, first 200 lines or 25KB of `MEMORY.md`|Things Claude learned itself. Build commands it discovered, debugging notes. Plain Markdown you can edit. Requires Claude Code v2.1.59+.|
|`--append-system-prompt`|Every invocation that uses the flag|When you need an instruction at the system-prompt level. Best for scripts and CI.|
|Inline in the message|Just this turn|One-off context for one task. "For this PR only, ignore the lint rule about line length."|

A short rule of thumb: ask yourself, _"would I want this in every session, in any session in this project, in any project, or just now?"_ The answer points to the right tool.

**In short:** match the lifetime of the rule to the scope of the tool.

---

## 14. Maintenance — keeping CLAUDE.md alive

This section answers: how do I keep the file useful over months?

**How often to revisit.** Every Friday for fifteen minutes. Also every time you finish a sprint or a release.

**Signs it has rotted.**

- The agent breaks a rule that is in the file. Either the rule is unclear, or the rule conflicts with another rule.
- A new teammate reads the file and asks questions it should answer.
- You repeat the same correction in chat more than twice.

**How to compact it.** Read it top to bottom. For each line, ask: "If I delete this, will the agent get worse?" If no, delete it. Move long examples into `docs/` and reference them. Use `<!-- ... -->` for human-only notes; the docs confirm they are stripped before injection so they cost zero context tokens.

**How to split it past 400 lines.** Three options, in order:

1. Move topic blocks into `.claude/rules/` files. Use `paths` frontmatter to load each file only when working on matching files. Example: a `testing.md` rule that loads only for `**/*Test.kt`.
2. Move stable shared content into a separate file and import it with `@docs/conventions.md`. Imported files still load at launch, so this is for organization, not for size.
3. Add **nested `CLAUDE.md` files** in subdirectories. These do not load at launch. They load on demand when Claude reads a file in that subdirectory. This is ideal for a monorepo where each `feature-*` module has its own rules.

**Nested files in monorepos.** Place `feature-billing/CLAUDE.md` next to the module's source. When the agent opens any file in `feature-billing/`, the module's `CLAUDE.md` joins context for that subdirectory's work. The root `CLAUDE.md` keeps the rules that apply everywhere. The module's file keeps the rules specific to that module.

**One subtle point.** Project-root `CLAUDE.md` survives `/compact` — Claude re-injects it from disk after compaction. **Nested** `CLAUDE.md` files in subdirectories are not re-injected; they reload only the next time Claude reads a file in that subdirectory. So put rules you must never lose at the project root.

**In short:** review weekly, delete what does not earn its place, split by path, and remember that nested files have different reload rules.

---

## 15. Caching and cost — the hidden payoff

This section answers: does this save money?

Yes. Anthropic's prompt caching is built around a stable prefix. When the same starting tokens appear in two requests, the second request reads them from cache instead of re-encoding them. Per the Claude API docs, cache reads are billed at roughly **0.1× the base input price**, while cache writes cost **1.25× base** for the 5-minute TTL or **2× base** for the 1-hour TTL.

`CLAUDE.md` content sits early in the prompt — after the system prompt, before today's user message. That position is exactly the stable prefix the cache rewards. As long as you do not edit `CLAUDE.md` between turns, every turn after the first reads it from cache.

Two practical numbers from public reports:

- A team building an agent on Claude reported overall savings of **59%–70%** on input cost once caching was tuned, with multi-step agent tasks being the most cacheable workloads.
- Anthropic itself reports latency reductions of up to **85%** for long cached prompts.

A rough mental model for an agent loop with an 8,000-token prefix on Claude Sonnet at $3 per million input tokens:

- Without caching, every turn re-bills the full prefix.
- With caching, every turn after the first pays about 10% of that prefix.
- Break-even on the 5-minute TTL is well under one read.

So a short, **stable** `CLAUDE.md` is not just a quality choice. It is also a cost choice. If you edit `CLAUDE.md` mid-session, you invalidate the cache and pay full price for the next turn. Edit between sessions, not during them, when possible.

Two limits worth knowing:

- Prompt caching has a minimum prefix size that depends on the model (around 1,024 to 4,096 tokens). Below it, caching silently does nothing.
- Cache entries expire after 5 minutes (default) or 1 hour (extended), and cache hits within the window refresh the entry at no extra cost.

**In short:** stable `CLAUDE.md` content caches; cached input is billed at about 10% of base; do not edit mid-session.

---

## 16. A 30-minute starter checklist

Run this on your project today. It produces a working `CLAUDE.md` in half an hour.

- [ ] Open the project root in a terminal.
- [ ] Run `claude` to start a session, then `/init` to generate a starter `CLAUDE.md`. Review what it wrote; do not accept blindly.
- [ ] Add a 2–3 sentence project overview at the top.
- [ ] Add a "Tech stack" section as a fixed list.
- [ ] Add a "Module layout" section with the dependency rule between layers.
- [ ] Add a "Build and test commands" section with the exact Gradle commands you actually run.
- [ ] Add a "Conventions" section with three to seven concrete rules per area: Kotlin, Compose, state, data, DI.
- [ ] Add a "Known traps" section with at least three real gotchas from your project's history.
- [ ] Add a "Never do" section with at least three explicit prohibitions.
- [ ] Add a "Pointers" section linking to deeper docs in `docs/`.
- [ ] Confirm the file is under 200 lines. If longer, move detail into `.claude/rules/` or referenced docs.
- [ ] Run `/memory` in Claude Code and confirm your `CLAUDE.md` is listed as loaded.
- [ ] Commit. Tell your team it is now part of the codebase.

**In short:** thirty minutes, eight short sections, under 200 lines, committed.

---

## 17. Sources and claim ledger

Every non-obvious claim in this guide maps to a source below. Confidence is **high** when the claim comes directly from official Anthropic documentation, **medium** when it comes from a named practitioner with public attribution, **low** when only third-party blogs say it.

|#|Claim|Source URL|Source date|Confidence|Notes|
|---|---|---|---|---|---|
|1|Anthropic defines context engineering as "strategies for curating and maintaining the optimal set of tokens (information) during LLM inference."|https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents|2025-09-29|high|Direct quote from official Anthropic engineering blog.|
|2|Anthropic frames context engineering as the "natural progression" of prompt engineering.|Same as #1|2025-09-29|high|Direct quote.|
|3|"Context rot": model recall accuracy degrades as context length grows.|Same as #1 (citing Chroma research)|2025-09-29|high|Anthropic cites a Chroma study on context rot.|
|4|Anthropic guidance: "find the smallest possible set of high-signal tokens."|Same as #1|2025-09-29|high|Direct quote.|
|5|Anthropic recommends organizing prompts into sections like `<background_information>`, `<instructions>`, `## Tool guidance`.|Same as #1|2025-09-29|high|Direct quote.|
|6|Just-in-time loading: agents maintain lightweight identifiers (file paths, queries) and load on demand.|Same as #1|2025-09-29|high|Direct quote and example given for Claude Code.|
|7|Compaction summarizes the conversation and reinitiates the window with the summary.|Same as #1|2025-09-29|high|Direct description of Claude Code compaction.|
|8|The four context failure modes — poisoning, distraction, confusion, clash — are Drew Breunig's terminology, not Anthropic's.|https://www.dbreunig.com/2025/06/22/how-contexts-fail-and-how-to-fix-them.html and https://www.dbreunig.com/2025/06/26/how-to-fix-your-context.html|2025-06-22 and 2025-06-26|high|Three modes named in the first post; "context clash" added in the second post. Confirmed by Simon Willison's link post (2025-06-29) at https://simonwillison.net/2025/Jun/29/how-to-fix-your-context/.|
|9|Tool-selection accuracy drops above ~30 tools; some smaller models fail past ~20.|https://www.dbreunig.com/2025/06/26/how-to-fix-your-context.html|2025-06-26|medium|Breunig cites third-party research (DeepSeek-v3 evaluation, "Less is More" paper).|
|10|`CLAUDE.md` is read at the start of every session.|https://code.claude.com/docs/en/memory|accessed 2026-05-03|high|Official Claude Code documentation.|
|11|Locations: managed policy paths; project `./CLAUDE.md` or `./.claude/CLAUDE.md`; user `~/.claude/CLAUDE.md`; local `./CLAUDE.local.md`.|Same as #10|accessed 2026-05-03|high|Official Claude Code documentation.|
|12|Loading walks up the directory tree; files are concatenated; root-down order; `CLAUDE.local.md` is appended after `CLAUDE.md` in the same directory.|Same as #10|accessed 2026-05-03|high|Verbatim from "How CLAUDE.md files load."|
|13|Subdirectory `CLAUDE.md` files are not loaded at launch; they load on demand when Claude reads files in that subdirectory.|Same as #10|accessed 2026-05-03|high|Verbatim.|
|14|Block-level HTML comments in `CLAUDE.md` are stripped before injection.|Same as #10|accessed 2026-05-03|high|Verbatim.|
|15|`@path/to/file` import syntax; max depth 5 hops; imports load at launch.|Same as #10|accessed 2026-05-03|high|Verbatim.|
|16|Claude Code reads `CLAUDE.md`, not `AGENTS.md`. Workaround is `@AGENTS.md` import.|Same as #10|accessed 2026-05-03|high|Verbatim.|
|17|Target file size: under 200 lines per `CLAUDE.md`.|Same as #10|accessed 2026-05-03|high|Verbatim.|
|18|`CLAUDE.md` is delivered as a user message after the system prompt, not as part of it. No guarantee of strict compliance.|Same as #10|accessed 2026-05-03|high|Verbatim.|
|19|Project-root `CLAUDE.md` is re-injected after `/compact`; nested files are not re-injected automatically.|Same as #10|accessed 2026-05-03|high|Verbatim from "Instructions seem lost after `/compact`" section.|
|20|`/init` generates a starter `CLAUDE.md`; `CLAUDE_CODE_NEW_INIT=1` enables an interactive multi-phase flow.|Same as #10|accessed 2026-05-03|high|Verbatim.|
|21|Auto memory requires Claude Code v2.1.59+; on by default; first 200 lines or 25KB of `MEMORY.md` loaded each session; machine-local.|Same as #10|accessed 2026-05-03|high|Verbatim.|
|22|`.claude/rules/*.md` supports `paths` frontmatter to scope rules to file globs.|Same as #10|accessed 2026-05-03|high|Verbatim.|
|23|`claudeMdExcludes` lets you skip ancestor `CLAUDE.md` files in monorepos.|Same as #10|accessed 2026-05-03|high|Verbatim.|
|24|Prompt caching pricing: 5-min cache writes 1.25× base, 1-hour writes 2× base, cache reads roughly 0.1× base.|https://platform.claude.com/docs/en/build-with-claude/prompt-caching|accessed 2026-05-03|high|Official Anthropic API documentation.|
|25|Default cache TTL is 5 minutes; 1-hour TTL is available at higher write cost.|Same as #24|accessed 2026-05-03|high|Verbatim.|
|26|Minimum prefix size for caching depends on model (~1,024 to ~4,096 tokens).|Same as #24, plus https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html|accessed 2026-05-03|high|Stated in Claude API docs and AWS Bedrock docs.|
|27|Anthropic reports latency reductions up to 85% for long cached prompts.|Anthropic prompt caching announcement, referenced via https://spring.io/blog/2025/10/27/spring-ai-anthropic-prompt-caching-blog/|2025-10-27 article citing Anthropic|medium|Spring blog cites Anthropic's published number; original Anthropic announcement is the primary source.|
|28|One production team reported 59–70% input cost savings after tuning prompt caching for an agent.|https://projectdiscovery.io/blog/how-we-cut-llm-cost-with-prompt-caching|2025|medium|Named-team blog post with measured numbers; not Anthropic's own data.|
|29|A "simple definition" of an agent: "LLMs autonomously using tools in a loop."|https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents (citing https://simonwillison.net/2025/Sep/18/agents/)|2025-09-29 (Anthropic) and 2025-09-18 (Willison)|high|Anthropic explicitly attributes this definition to Simon Willison.|
|30|The Claude Code memory docs distinguish what to put in `CLAUDE.md` vs auto memory vs skills vs slash commands.|https://code.claude.com/docs/en/memory and https://code.claude.com/docs/en/best-practices|accessed 2026-05-03|high|Two official Claude Code docs pages.|
|31|Hedvig Insurance's open-source Android repo uses a `CLAUDE.md` that documents modules, build commands, and conventions in a real Kotlin/Compose project.|https://github.com/HedvigInsurance/android/blob/develop/CLAUDE.md|accessed 2026-05-03|medium|Real open-source example; quality is the team's, not Anthropic's. Used here only for shape, not for rules.|
|32|Anthropic explicitly notes that `CLAUDE.md` files are dropped into context up front, while tools like glob and grep allow just-in-time retrieval.|https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents|2025-09-29|high|Direct mention in the post.|

**Disagreements I surfaced:**

- Anthropic does not officially use the four-mode failure naming (poisoning / distraction / confusion / clash). That naming is Drew Breunig's. Both can be cited; I used Breunig's terminology and credited him. This is **interpretation** when projecting it onto Claude Code specifically.
- Some third-party posts claim `CLAUDE.md` is "loaded as part of the system prompt." This is incorrect per the official docs, which say it is delivered as a user message after the system prompt. I used the official version.
- Cost-saving numbers vary widely by workload. Anthropic's 85% latency figure and project teams' 59–70% cost figures are reported, not guaranteed.

---

## 18. Glossary

One-line definitions for terms used in this guide.

- **Context window** — the maximum amount of tokens a model can read in one turn.
- **System prompt** — the top-level instruction block that frames a model's behavior in a session.
- **Prompt caching** — an Anthropic API feature that stores a stable prompt prefix so later requests pay much less for those tokens.
- **Agentic** — describes a model that uses tools in a loop to complete tasks, not just answer one message.
- **MCP** — Model Context Protocol; a standard way for tools and data sources to expose capabilities to Claude.
- **Sub-agent** — a separate Claude session spawned by a main agent to handle a focused sub-task with its own clean context window.
- **Just-in-time context** — loading information only when it is needed, instead of all at once.
- **Compaction** — summarizing a long conversation so it fits back into a smaller, fresher window.
- **Primary source** — the original publisher of a claim, such as the Anthropic engineering blog or the Claude Code official docs, rather than a third-party summary.

**In short:** if a term in this guide is unclear, this list is your first stop.