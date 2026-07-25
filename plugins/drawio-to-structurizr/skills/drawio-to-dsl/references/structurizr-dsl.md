# Structurizr DSL reference

Condensed from [docs.structurizr.com/dsl](https://docs.structurizr.com/dsl/language).
Everything here is valid in the [Structurizr playground](https://playground.structurizr.com/),
Structurizr Lite, and the CLI.

## Skeleton

```
workspace "Name" "Description" {

    !identifiers hierarchical

    model {
        // people, systems, containers, components, relationships
    }

    views {
        // one view per question, then styles
    }

    configuration {
        scope softwaresystem
    }
}
```

## Model

### Elements

```
person <name> [description] [tags]
softwareSystem <name> [description] [tags] { ... }
container <name> [description] [technology] [tags] { ... }
component <name> [description] [technology] [tags] { ... }
group <name> { ... }
```

Positional order matters: for a `container`, the **third** string is technology,
the fourth is tags. Assign an identifier with `=`:

```
student = person "Student" "Enrols in courses and pays fees"

eCollege = softwareSystem "eCollege" "Course enrolment platform" {
    webApplication = container "Web Application" "Student-facing UI" "React"
    database = container "Enrolment Database" "Stores enrolments" "PostgreSQL" {
        tags "Database"
    }
}
```

Inside a block you may also set fields explicitly, which is clearer when several
are present:

```
container "Monolithic Backend" {
    description "Implements enrolment, billing and reporting"
    technology "Java, Spring Boot"
    tags "Backend"
    url https://wiki.example.com/backend
    properties {
        owner "Platform team"
    }
}
```

### Relationships

```
<source> -> <destination> [description] [technology] [tags]
```

```
student -> eCollege.webApplication "Enrols in courses using" "HTTPS"
eCollege.monolithicBackend -> paymentGateway "Sends payment requests to" "HTTPS/JSON"
```

With `!identifiers hierarchical`, nested elements are addressed by path
(`eCollege.webApplication`) and identifiers cannot collide across systems. Use it.

### Identifier rules

- `camelCase`, no spaces, no leading digit
- Unique within its scope
- Referencing an undeclared identifier is a parse error — every relationship and
  view must name declared elements

## Views

```
systemLandscape [key] [description] { ... }
systemContext <softwareSystem> [key] [description] { ... }
container <softwareSystem> [key] [description] { ... }
component <container> [key] [description] { ... }
dynamic <scope> [key] [description] { ... }
deployment <scope> <environment> [key] [description] { ... }
filtered <baseKey> include|exclude <tags> [key] [description]
image [scope] [key] { ... }
```

Inside a view:

```
container eCollege "Containers" "Container diagram for eCollege" {
    include *
    exclude "student -> eCollege.database"
    autoLayout lr 300 300
    title "Container diagram for eCollege"
    description "Runtime building blocks and their protocols"
}
```

- `include *` pulls in everything relevant to the scope — the usual default
- `autoLayout [tb|bt|lr|rl] [rankSeparation] [nodeSeparation]`
- **Without `autoLayout`, elements have no coordinates and render stacked at the
  origin.** Manual positions live in the workspace JSON, not the DSL, so a DSL
  file moved between tools loses them. Include `autoLayout` unless the user
  explicitly wants to arrange by hand
- View keys must be unique; prefer meaningful keys (`Containers`) over `Diagram2`

## Styles

```
styles {
    element "Element" {
        shape roundedBox
        fontSize 22
        metadata true
    }
    element "Person" {
        shape person
        background #08427b
        color #ffffff
    }
    element "Database" {
        shape cylinder
    }
    element "External" {
        background #999999
        color #ffffff
    }
    relationship "Relationship" {
        thickness 2
        routing orthogonal
        fontSize 20
    }
}
```

Shapes: `box`, `roundedBox`, `circle`, `ellipse`, `hexagon`, `cylinder`, `pipe`,
`person`, `robot`, `folder`, `webBrowser`, `mobileDevicePortrait`,
`mobileDeviceLandscape`, `component`.

Styles apply **by tag**. Tag once, style once — never restyle per element.

A theme replaces most hand-rolled styling:

```
theme default
# or
themes https://static.structurizr.com/themes/default/theme.json
```

## Documentation and decisions

```
!docs docs
!adrs decisions
```

## Modularity

```
!include model/people.dsl
!constant ORGANISATION "Universidad"
!identifiers hierarchical
```

`!include` takes a file, directory or URL. Paths are relative to the including
file.

## Extending declared elements

```
!element eCollege.database {
    tags "Database,Critical"
}

!elements "element.type==Container" {
    tags "Runtime"
}
```

## Configuration

```
configuration {
    scope softwaresystem   # or landscape, or none
}
```

`scope softwaresystem` is right for a workspace describing one system; it enables
Structurizr's completeness checks. Use `landscape` for multi-system workspaces.

## Common parse errors

| Error | Cause |
| --- | --- |
| `Unexpected tokens` | Extra positional string — remember arg 3 of `container` is technology |
| `The element ... does not exist` | Identifier referenced before declaration, or a typo |
| `A view with the key ... already exists` | Duplicate view key |
| Elements stacked at origin | No `autoLayout` and no stored coordinates |
| `Unbalanced braces` | Missing `}` — indent consistently to catch this by eye |
