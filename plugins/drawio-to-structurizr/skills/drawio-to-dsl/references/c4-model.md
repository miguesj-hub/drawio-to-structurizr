# The C4 model — abstractions, diagrams and notation rules

Reference for converting draw.io drawings into a correct C4 model.
Source: [c4model.com](https://c4model.com) (Simon Brown).

## The core idea

> A software system is made up of one or more containers (applications and data
> stores), each of which contains one or more components, which in turn are
> implemented by one or more code elements.

C4 is **notation independent** and **tooling independent**. It prescribes the
*abstractions* and that diagrams must stand alone; it does not prescribe colours
or shapes. This is why a draw.io drawing and a Structurizr workspace can hold the
same model.

## Abstractions

| Abstraction | Definition | Examples |
| --- | --- | --- |
| **Person** | A human: actor, role, persona. Never a system | Student, Professor, Accountant, Administrator |
| **Software System** | The highest level of abstraction; something that delivers value. The unit of ownership | eCollege, Payment Gateway, Central Registry |
| **Container** | An application or data store — **something that must be running** for the system to work. A separately deployable/runnable unit | Web app, SPA, mobile app, API, database, file system, message broker |
| **Component** | A grouping of related functionality behind an interface, inside a container. **Not** separately deployable | Enrolment controller, Payment service, Invoice repository |
| **Code** | Classes, interfaces, objects, functions. Usually omitted — generate it if needed | — |

### What is NOT a container

This is the most common modelling error. A container must be a runnable/deployable
thing. These are **not** containers:

- A layer or tier ("business layer", "data access layer") — those are components
- A namespace, package or module
- A third-party system you merely call — that is an **external software system**
- A cloud service you deploy onto — that is a deployment node

### Internal vs external

An element inside the system boundary is part of the system. Anything outside is
**external** and should be modelled as a `softwareSystem` (or `person`),
regardless of how it was drawn. Externals are conventionally greyed out.

A container drawn *outside* the system boundary is a contradiction: containers
belong to exactly one software system. Retype it as an external software system.

## Diagram types

### Level 1 — System Context

- **Scope**: one software system
- **Contains**: the system in scope, plus the people and systems it interacts with
- **Audience**: everybody, technical and non-technical
- **Excludes**: containers, components, technology choices

### Level 2 — Container

- **Scope**: one software system
- **Contains**: the containers inside it, plus adjacent people and external systems
- **Audience**: technical people inside and outside the team
- **Must show**: technology per container, and the protocol on each relationship

### Level 3 — Component

- **Scope**: one container
- **Contains**: the components inside that container
- **Audience**: the team building it
- **Note**: one component diagram *per container*, not one per system

### Level 4 — Code

- **Scope**: one component. UML-ish, usually generated, usually skipped

### Supplementary

| Type | Purpose |
| --- | --- |
| **System Landscape** | Multiple systems in an enterprise; wider than one system's context |
| **Dynamic** | Runtime collaboration for one scenario, with numbered steps |
| **Deployment** | How containers map onto infrastructure per environment |

## Notation rules

These are the rules a converted workspace must satisfy.

### Elements

Every box must make explicit:

- **Name**
- **Element type** — Person, Software System, Container, Component. In
  Structurizr the keyword supplies this and `metadata true` renders it
- **Description** — a short statement of responsibility, not a restatement of the name
- **Technology** — **required for every container and component**

### Relationships

- **Unidirectional.** Draw two lines rather than a double-headed arrow
- **Specifically labelled.** "Uses", "Calls", "Talks to" are explicitly called out
  as too vague. State the intent: "Sends payment requests to"
- **Technology/protocol named**, especially between containers (the
  inter-process communication mechanism): `"HTTPS/JSON"`, `"SMTP"`, `"JDBC"`
- **Direction matches the label.** `A -> B "Sends emails to"` means A sends. If
  the label reads backwards relative to the arrow, one of them is wrong
- Label should complete: *"<source> … <destination>"*

### Diagram-level

- **Title**: state type and scope — "System Context diagram for eCollege"
- **Legend/key**: explain shapes, colours, line styles, arrowheads
- **Acronyms**: understandable to the whole audience, or defined in the legend
- **Colour**: not prescribed. Use consistently; consider colour-blind readers.
  Never encode meaning in colour alone

### Ambiguity

The overriding rule: a diagram must **stand alone**. If a reader needs the author
present to interpret it, it has failed — regardless of how correct the model is.

## Checklist for a converted workspace

- [ ] Every person is a `person`, never a system
- [ ] Every container is genuinely deployable/runnable
- [ ] Every container and component declares a technology
- [ ] Nothing outside the boundary is typed as a container
- [ ] Every relationship has a specific verb-phrase label
- [ ] Inter-container relationships name a protocol
- [ ] No bidirectional arrows
- [ ] Each view has an explicit title stating type and scope
- [ ] Abstraction levels are not mixed within a view
- [ ] Externals are tagged and styled distinctly
