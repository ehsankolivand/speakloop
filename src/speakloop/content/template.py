"""Canonical question-file template (015) — the single source of truth for the starter set.

`speakloop questions template` prints this to stdout so a user can redirect it to a file of
their choice (nothing is auto-created in the home directory). It lives next to `schema.py`
so the two move together; a unit test asserts it loads cleanly through `content.load()`.
"""

from __future__ import annotations

_TEMPLATE = """\
# speakloop question file — copy, edit, and point speakloop at it.
#   speakloop questions template > ~/.speakloop/qa.yaml   # personal override (auto-detected)
#   speakloop practice --qa-file ./my-questions.yaml      # one-off use of a specific file
# Check it any time:  speakloop questions validate <path>
# Precedence (first match wins): --qa-file / SPEAKLOOP_QA_FILE  >  ~/.speakloop/qa.yaml
#                                >  the in-repo content/questions.yaml.

schema_version: 1              # required; keep this at 1.

questions:
  # Each entry needs an `id`, a `question`, and an `ideal_answer`. Everything else is optional.
  - id: tcp-vs-udp             # required: kebab-case (lowercase letters, digits, hyphens), <= 40 chars
    question: |                # required: what you'll be asked (spoken aloud)
      Explain the difference between TCP and UDP, and when you'd choose each.
    ideal_answer: |            # required: a strong spoken answer to listen to and compare against
      TCP is connection-oriented and reliable: it sets up a connection, guarantees ordered
      delivery, and retransmits lost segments, at the cost of latency. UDP is connectionless
      and best-effort: no handshake, no ordering, no retransmits, but much lower overhead.
      Choose TCP when correctness matters more than latency, like APIs and file transfer.
      Choose UDP for latency-sensitive, loss-tolerant traffic, like live video, games, and DNS.
    type: definition           # optional: definition (default) | behavioral | hypothetical
    tags: [networking, fundamentals]   # optional: free-form labels (also bias transcription)
    difficulty: medium         # optional: easy | medium | hard

  - id: conflict-with-teammate
    question: |
      Tell me about a time you disagreed with a teammate on a technical decision.
    ideal_answer: |
      Use the STAR structure. Situation: we disagreed on whether to adopt a new framework.
      Task: I owned the recommendation. Action: I wrote a short trade-off doc, prototyped
      both options, and ran a thirty-minute review. Result: we chose the simpler option,
      shipped on time, and I wrote the decision down so it would not be re-litigated.
    type: behavioral

  - id: scale-read-heavy-api
    question: |
      Suppose a read-heavy API suddenly gets ten times its usual traffic. How would you keep
      it fast?
    ideal_answer: |
      First I would measure where the time actually goes. Then, in order: cache the hot reads
      with sensible invalidation, add read replicas, and put a CDN in front of cacheable
      responses. If writes are the bottleneck I would batch or queue them. I would load-test
      each change and watch tail latency, not just the average.
    type: hypothetical
    # voice_override: af_heart   # optional: pin a specific TTS voice for this question
"""


def template_text() -> str:
    """Return the canonical, commented, schema-valid question-file template."""
    return _TEMPLATE
