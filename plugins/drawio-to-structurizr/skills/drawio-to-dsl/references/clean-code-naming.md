# Clean Code applied to Structurizr DSL

Robert C. Martin's *Clean Code* is about source read by humans. A Structurizr
workspace **is** source: version-controlled, reviewed, and read far more often
than written. The rules transfer almost directly. Below is each relevant chapter
mapped to DSL, with the wrong and right form side by side.

---

## Ch. 2 — Meaningful Names

### Use intention-revealing names

An identifier must answer *why it exists* and *what it does*.

```
# Bad -- reveals nothing
c1 = container "Web Application"
fe = container "Web Application"
frontend = container "Web Application"

# Good -- states the role in this system
studentWebApplication = container "Web Application" "..." "React"
```

`frontend` is a *layer*, not a responsibility. Two frontends and the name
collapses. Name by the job it does.

### Avoid disinformation

Never leave a name that contradicts reality.

```
# Bad -- it is a monolith
paymentMicroservice = container "Monolith"

# Good
monolithicBackend = container "Monolithic Backend" "..." "Spring Boot"
```

Also avoid names that differ only in noise: `courseService` vs `courseServiceData`
vs `courseServiceInfo` force the reader to diff characters.

### Make meaningful distinctions

```
# Bad -- number series carry no information
system1 = softwareSystem "Registry"
system2 = softwareSystem "Payments"

# Good
centralUniversityRegistry = softwareSystem "Central Registry"
paymentGateway = softwareSystem "Payment Gateway"
```

Drop noise words. `theDatabase`, `databaseObject`, `databaseData` all mean
`database`.

### Use pronounceable, searchable names

```
# Bad
mnltBk = container "Monolito"
db = container "Database"

# Good -- you can say these in a stand-up and grep them
monolithicBackend = container "Monolithic Backend"
enrolmentDatabase = container "Enrolment Database" "..." "PostgreSQL"
```

Single letters and abbreviations are unsearchable: grepping `db` matches every
word containing it.

### Avoid encodings and type prefixes

The DSL keyword already declares the type. Repeating it is Hungarian notation.

```
# Bad -- "System"/"Container" duplicate the keyword
paymentGatewaySystem = softwareSystem "Payment Gateway"
databaseContainer = container "Database"

# Good
paymentGateway = softwareSystem "Payment Gateway"
enrolmentDatabase = container "Enrolment Database"
```

### Class names are nouns, method names are verbs

Elements are things; relationships are actions.

```
# Bad -- vague verb, tells the reader nothing
monolithicBackend -> paymentGateway "Uses"

# Good -- intent plus protocol, reads as a sentence
monolithicBackend -> paymentGateway "Sends payment requests to" "HTTPS/JSON"
```

C4 explicitly calls out "Uses" as too generic. The label should complete the
sentence *"<source> ... <destination>"*.

### One word per concept

Pick one term per idea and never alternate. If the domain says *enrolment*, do
not mix in *registration* and *signup* for the same concept. Where the source
diagrams disagree, choose one, use it everywhere, and say so in your report.

### Use the domain's language

Prefer the author's vocabulary over invented synonyms. If their diagram says
`Monolito`, `monolithicBackend` respects it; `serverApp` erases it. Keep original
wording in `description` strings even when the identifier is anglicised.

---

## Ch. 3 — Functions → Views

**Do one thing.** A function should do one thing; a view should answer one
question for one audience. That is exactly the C4 premise: separate diagrams per
abstraction level.

```
# Bad -- two levels in one view, readable by nobody
container eCollege "Everything" {
    include *
    include element.type==Component
}

# Good -- one question each
systemContext eCollege "SystemContext" {
    include *
    autoLayout lr
    title "System Context diagram for eCollege"
}

container eCollege "Containers" {
    include *
    autoLayout lr
    title "Container diagram for eCollege"
}
```

**One level of abstraction per block.** Do not mix people, containers and
deployment nodes in a single declaration group.

**Small.** If a view needs a dozen `exclude` lines to be legible, the view is
doing too much — split it, or use a `filtered` view.

---

## Ch. 4 — Comments

> "The proper use of comments is to compensate for our failure to express
> ourselves in code."

The DSL has a first-class field for meaning: `description`. Reach for it before a
comment.

```
# Bad -- comment carries what the model should
# this is the student facing app
webApplication = container "Web Application"

# Good -- self-describing model
webApplication = container "Web Application" "Student-facing UI for enrolment and payments" "React"
```

Comments that **are** justified:

- `# TODO(unresolved): connector "Sends emails to" -- reattach in draw.io`
- `# inferred: endpoints recovered from geometry, confirm direction`
- A warning about a non-obvious constraint the DSL cannot express.

Never leave commented-out DSL. Delete it; git remembers.

---

## Ch. 5 — Formatting

**The newspaper metaphore**: headline first, details later. Read top to bottom:
people → the system in scope → its containers → external systems →
relationships → views → styles.

**Vertical openness between concepts.** Blank lines separate groups; no blank
lines inside a tightly related group.

```
model {
    student = person "Student" "..."
    professor = person "Professor" "..."

    eCollege = softwareSystem "eCollege" "..." {
        webApplication = container "Web Application" "..." "React"
        monolithicBackend = container "Monolithic Backend" "..." "Spring Boot"
    }

    paymentGateway = softwareSystem "Payment Gateway" "..." {
        tags "External"
    }

    student -> eCollege.webApplication "Enrols in courses using" "HTTPS"
}
```

**Vertical distance**: declare relationships close to the elements they concern,
or in one clearly separated block. Do not scatter them.

**Indentation**: four spaces, consistent. Structurizr's own formatter uses four.

---

## Ch. 7 — Error Handling: don't return null

> "Don't return null. Don't pass null."

The model equivalent: do not emit a half-known relationship. A connector whose
endpoints are unknown must not become a guessed dependency — that is the DSL
version of returning null and letting the caller crash later. Flag it loudly and
leave it out.

---

## Ch. 9/10 — Single Responsibility → file structure

One reason to change per file. For a workspace that outgrows one file, split with
`!include` and keep each fragment single-purpose:

```
workspace "eCollege" "..." {
    !identifiers hierarchical

    model {
        !include model/people.dsl
        !include model/ecollege.dsl
        !include model/external-systems.dsl
        !include model/relationships.dsl
    }

    views {
        !include views/context.dsl
        !include views/containers.dsl
        !include views/styles.dsl
    }
}
```

Keep a single file while it stays readable — splitting a 60-line workspace is
premature. Split when a file starts having more than one reason to change.

---

## DRY

Style once, by tag, never per element:

```
# Bad -- repeated per element, drifts immediately
externalRegistry = softwareSystem "Registry" { tags "External" }
# ...then styling each element individually

# Good -- one rule governs every external
styles {
    element "External" {
        background #999999
        color #ffffff
    }
}
```

Prefer a `theme` over hand-rolling a full palette.

---

## The Boy Scout Rule

> "Leave the campground cleaner than you found it."

While converting, fix genuine modelling errors — an external system mistyped as a
Container, a missing technology, a generic "Uses" label. But **report every fix**.
A silent correction is indistinguishable from a bug you introduced.
