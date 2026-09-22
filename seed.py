import logging
from dotenv import load_dotenv
import db

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("made_for_nothing.seed")

SAMPLE_POSTS = [
    {
        "type": "writing",
        "title": "The Architecture of Deliberate Software",
        "slug": "architecture-of-deliberate-software",
        "excerpt": "Why modern software suffers from manufactured complexity, and how building for longevity requires rejecting the cult of churn.",
        "content_markdown": """# The Architecture of Deliberate Software

Most contemporary software is not built to endure. It is assembled under the pressure of quarterly cadences, designed to validate engagement metrics, and burdened with deep dependency graphs that crumble within a few years of neglect.

When we strip away the urgency of commercial velocity, an entirely different design space opens up.

---

## The Principle of Subtraction

Every dependency introduced to a project is a deferred liability. When evaluating an addition to a system, the primary question should not be:

> *\"What capability does this grant me today?\"*

Rather, it should be:

> *\"What maintenance burden does this impose five years from now?\"*

### Contrasting Approaches

| Dimension | Speculative Architecture | Deliberate Architecture |
| :--- | :--- | :--- |
| **Dependencies** | 1,000+ transitive packages | Minimal, standard library first |
| **Data Layer** | Distributed polyglot stores | Single ACID-compliant relational DB |
| **Rendering** | Hydrated client-side virtual DOM | Clean, server-rendered semantic HTML |
| **Longevity** | Requires quarterly refactoring | Runs unmodified for a decade |

## The Fallacy of Premature Abstraction

Complexity creeps in under the guise of future flexibility. We build plugin architectures before we have two implementations. We introduce message queues before our throughput exceeds a single SQLite transaction threshold.

```python
# The simplest implementation that satisfies the invariant
def retrieve_record(cursor, item_slug: str):
    cursor.execute(
        "SELECT id, title, content FROM posts WHERE slug = %s AND is_published = TRUE",
        (item_slug,)
    )
    return cursor.fetchone()
```

Writing code that can be understood in an afternoon by someone with no prior context is not laziness—it is the highest form of engineering respect.

---

## Conclusion

Building something *made for nothing* frees the engineer from superficial trends. It allows one to return to foundational primitives: text, relational models, semantic hypermedia, and unadorned typography.
""",
        "is_published": True,
        "show_on_landing": True,
        "tags": ["philosophy", "systems", "architecture", "minimalism"],
        "external_links": [
            {"title": "Worse is Better (Richard P. Gabriel)", "url": "https://www.dreamsongs.com/RiseOfWorseIsBetter.html"},
            {"title": "The Cathedral and the Bazaar", "url": "http://www.catb.org/~esr/writings/cathedral-bazaar/"}
        ],
        "seo_title": "The Architecture of Deliberate Software",
        "seo_description": "An essay on building enduring systems through subtraction and deliberate engineering.",
        "continue_reading_slugs": [
            "latency-bounds-in-distributed-crdt-consensus",
            "zero-framework-server-rendered-micro-benchmarks"
        ]
    },
    {
        "type": "research",
        "title": "Latency Bounds in Distributed CRDT Consensus",
        "slug": "latency-bounds-in-distributed-crdt-consensus",
        "excerpt": "A formal investigation into state-based vs operation-based conflict-free replicated data types under high network partition regimes.",
        "content_markdown": """# Latency Bounds in Distributed CRDT Consensus

Conflict-free Replicated Data Types (CRDTs) offer strong eventual consistency without centralized coordination. However, the trade-offs between state-based (CvRDT) and operation-based (CmRDT) variants diverge significantly when subjected to high-latency WAN environments.

## Mathematical Formulation

Let a replica state be modeled as a bounded join-semilattice:

$$S = \\langle S, \\sqcup, \\le, \\bot \\rangle$$

Where the merge operator $\\sqcup$ satisfies:
1. **Commutativity:** $x \\sqcup y = y \\sqcup x$
2. **Associativity:** $(x \\sqcup y) \\sqcup z = x \\sqcup (y \\sqcup z)$
3. **Idempotence:** $x \\sqcup x = x$

```python
class ObservedRemoveSet:
    def __init__(self):
        self.add_set = set()
        self.remove_set = set()

    def add(self, element, tag):
        self.add_set.add((element, tag))

    def remove(self, element, tag):
        self.remove_set.add((element, tag))

    def read(self):
        return {elem for (elem, tag) in self.add_set if (elem, tag) not in self.remove_set}
```

## Benchmark Observations

Under simulated 250ms intercontinental latency across 5 regional nodes:

* State dissemination overhead grew linearly with vector clock size ($O(n)$ where $n$ is cluster node count).
* Delta-state mutation compaction reduced payload overhead by **74.2%**.
* Convergence jitter was bounded within $3 \\times \\text{RTT}_{\\max}$.

## Open Questions

Investigating garbage collection thresholds for tombstone cleanup in long-lived causal graphs without pausing concurrent writes remains an active research direction.
""",
        "is_published": True,
        "show_on_landing": True,
        "tags": ["distributed-systems", "algorithms", "crdt", "concurrency"],
        "external_links": [
            {"title": "Shapiro et al. Conflict-Free Replicated Data Types (INRIA)", "url": "https://hal.inria.fr/inria-00609399/document"}
        ],
        "seo_title": "Latency Bounds in Distributed CRDT Consensus | Research",
        "seo_description": "Investigation into state-based vs operation-based CRDT latency in partitioned networks.",
        "continue_reading_slugs": [
            "zero-framework-server-rendered-micro-benchmarks",
            "monolith-single-binary-document-indexer"
        ]
    },
    {
        "type": "experiments",
        "title": "Zero-Framework Server-Rendered Micro-Benchmarks",
        "slug": "zero-framework-server-rendered-micro-benchmarks",
        "excerpt": "Benchmarking raw throughput and memory footprint of FastAPI + Jinja2 against hydrated client-side frameworks.",
        "content_markdown": """# Zero-Framework Server-Rendered Micro-Benchmarks

Can a minimal Python stack match the latency profile demanded by modern web standards while shedding JavaScript runtime bloat?

We evaluated a pure FastAPI + Jinja2 template pipeline against standard hydration stacks.

## Methodology

* **Hardware:** 4 vCPU, 8GB RAM, Linux kernel 6.5
* **Workload:** 10,000 requests at concurrency level 50
* **Payload:** 25KB article HTML with metadata, navigation, and code snippets

## Empirical Results

```
FastAPI + Jinja2 (Direct HTML):
  Throughput: 4,120 req/sec
  p50 Latency: 8.2 ms
  p99 Latency: 22.4 ms
  Client JS downloaded: 0 KB

Full SPA Hydration Stack:
  Throughput: 850 req/sec
  p50 Latency: 44.1 ms
  p99 Latency: 168.0 ms
  Client JS downloaded: 342 KB
```

### Key Takeaways

1. Server-rendered HTML delivers First Contentful Paint (FCP) nearly instantaneous with zero script execution overhead.
2. Battery consumption on low-power mobile devices decreases by approximately 60% due to the elimination of client-side DOM reconciliation.
""",
        "is_published": True,
        "show_on_landing": False,
        "tags": ["benchmarks", "fastapi", "performance", "web-standards"],
        "external_links": [
            {"title": "FastAPI Documentation", "url": "https://fastapi.tiangolo.com/"},
            {"title": "Jinja2 Documentation", "url": "https://jinja.palletsprojects.com/"}
        ],
        "seo_title": "FastAPI + Jinja2 Performance Micro-Benchmarks",
        "seo_description": "Empirical comparison of server-rendered HTML vs SPA frameworks.",
        "continue_reading_slugs": [
            "architecture-of-deliberate-software",
            "monolith-single-binary-document-indexer"
        ]
    },
    {
        "type": "projects",
        "title": "Monolith: Single-Binary Document Indexer",
        "slug": "monolith-single-binary-document-indexer",
        "excerpt": "A lightweight, zero-configuration full-text search indexing tool designed for personal archives and local notebooks.",
        "content_markdown": """# Monolith: Single-Binary Document Indexer

**Monolith** is a focused command-line utility built to index personal Markdown archives, academic papers, and plain text notes without requiring Elasticsearch or heavy JVM dependencies.

## Key Features

* **Instant Inverted Indexing:** Indexes 50,000 documents in under 1.2 seconds.
* **BM25 Scoring:** Built-in probabilistic relevance ranking with term frequency and document length normalization.
* **Zero Configuration:** Reads a directory and outputs a compact portable index file.
* **Interactive TUI:** Fuzzy interactive terminal viewer for browsing search hits in context.

## Quickstart

```bash
# Index a directory of notes
monolith index --source ~/notes --output ~/.monolith.idx

# Search with relevance ranking
monolith search "distributed consensus" --index ~/.monolith.idx
```

## Architecture

The index uses a serialized roaring bitmap structure for document postings lists, enabling sub-millisecond set intersections even on resource-constrained embedded systems.
""",
        "is_published": True,
        "show_on_landing": True,
        "tags": ["open-source", "search", "tools", "cli"],
        "external_links": [
            {"title": "Information Retrieval: BM25 Algorithm", "url": "https://en.wikipedia.org/wiki/Okapi_BM25"}
        ],
        "seo_title": "Monolith: Single-Binary Document Indexer",
        "seo_description": "Zero-dependency full-text indexing engine for personal knowledge bases.",
        "continue_reading_slugs": [
            "architecture-of-deliberate-software",
            "reading-notes-thinking-in-systems"
        ]
    },
    {
        "type": "books",
        "title": "Reading Notes: Thinking in Systems by Donella Meadows",
        "slug": "reading-notes-thinking-in-systems",
        "excerpt": "Core principles, leverage points, and reflections on nonlinear dynamics in technical and organizational architectures.",
        "content_markdown": """# Reading Notes: Thinking in Systems by Donella Meadows

Donella Meadows' *Thinking in Systems: A Primer* remains one of the most transformative books on understanding systemic behavior, feedback loops, and unintended consequences.

## Core Concepts

### 1. Stocks, Flows, and Delays
* **Stock:** The foundation of any system; an accumulation of information or material built up over time.
* **Flow:** The rate of inflow or outflow that alters a stock.
* **Delay:** The lag between a signal and the system's reaction. Delays are frequently the unrecognized source of oscillation and catastrophic instability.

> *\"You think that because you understand 'one' that you must therefore understand 'two' because one and one makes two. But you forget that you must also understand 'and'.\"*

### 2. High-Leverage Intervention Points

Meadows ranks places to intervene in a system in increasing order of effectiveness:

1. **Parameters & Numbers:** Subsidies, taxes, standards (Least effective long-term).
2. **Buffer Sizes:** Stabilizing stocks relative to their flows.
3. **Information Flows:** Who has access to timely, uncorrupted feedback.
4. **System Rules:** Incentives, punishments, and constraints.
5. **Goals:** The purpose of the system.
6. **Paradigms:** The mindset out of which the system—its goals, structure, and rules—arises.

## Reflections for Software Architects

When a software architecture begins to fail under scale, our impulse is often to tune parameters: connection pool sizes, timeouts, buffer allocations. 

Yet Meadows shows that parameter adjustments rarely solve systemic instability. High leverage comes from altering information flows (e.g. backpressure protocols) and rethinking system goals (e.g. decoupling synchronization from storage).
""",
        "is_published": True,
        "show_on_landing": False,
        "tags": ["systems-thinking", "books", "marginalia", "mental-models"],
        "external_links": [
            {"title": "The Donella Meadows Project", "url": "https://donellameadows.org/"}
        ],
        "seo_title": "Thinking in Systems Reading Notes & Marginalia",
        "seo_description": "Summary and software engineering reflections on Donella Meadows' Thinking in Systems.",
        "continue_reading_slugs": [
            "architecture-of-deliberate-software",
            "latency-bounds-in-distributed-crdt-consensus"
        ]
    }
]


def run_seed():
    logger.info("Initializing database schema...")
    db.init_db()

    logger.info("Seeding editorial research posts...")
    for post_data in SAMPLE_POSTS:
        query = "SELECT id FROM posts WHERE slug = %s LIMIT 1"
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (post_data["slug"],))
                found = cur.fetchone()

        if found:
            post_id = found["id"] if isinstance(found, dict) else found[0]
            logger.info(f"Updating existing post: {post_data['slug']} (ID: {post_id})")
            db.update_post(post_id, post_data)
        else:
            logger.info(f"Creating post: {post_data['slug']}")
            db.create_post(post_data)

    logger.info("Seeding completed successfully!")


if __name__ == "__main__":
    run_seed()
