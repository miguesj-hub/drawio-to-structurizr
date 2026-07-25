# Making the rendered diagram readable

Crossing lines are usually a *layout engine* problem, not a model problem. Work
through these in order — the first one is the trap that wastes the most time.

## 1. `autoLayout` asks for Graphviz, and silently falls back

This is the big one. `autoLayout` in the DSL produces
`"implementation": "Graphviz"` in the workspace. But Graphviz is an **external
binary**: if `dot` is not installed, Structurizr's web UI quietly falls through to
its built-in Dagre layout, which does far less crossing minimisation.

Nothing in the diagram says this happened. You just get a worse layout.

**Detect it.** Structurizr Lite logs the probe at startup:

```
Graphviz (dot): false      <-- falling back to Dagre
Graphviz (dot): true       <-- server-side Graphviz in use
```

The served page also carries the resolved flag, which is the ground truth:

```bash
curl -sL http://localhost:8080/workspace/diagrams \
  | grep -o "implementation === 'Graphviz' && [a-z]*" | head -1
# && false  -> Dagre
# && true   -> Graphviz
```

**Fix it.** Install Graphviz, then restart Lite so it re-probes:

```bash
brew install graphviz        # macOS
sudo apt install graphviz    # Debian/Ubuntu
```

Beware `PATH`: Lite probes by executing `dot`, and Homebrew's `/opt/homebrew/bin`
is often absent from a minimal environment. If `which dot` succeeds in your shell
but Lite still reports `false`, export `PATH` in whatever launches Lite.

**Ask before installing.** This is a system-level change. See the agent's tooling
step — offer the translate-only path instead if the user prefers.

## 2. Group related elements

`group` clusters elements visually *and* gives the layout engine a hint about what
belongs together, so it stops interleaving layers:

```
monolithicBackend = container "Monolithic Backend" "..." "Spring Boot" {

    group "API layer" {
        signInApi = component "SignIn API" "..." "..."
        paymentApi = component "Payment API" "..." "..."
    }

    group "Domain" {
        securityService = component "Security Component" "..." "..."
    }

    group "Adapters" {
        paymentGatewayAdapter = component "Payment Gateway Adapter" "..." "..."
    }
}
```

Groups are presentational: identifiers stay
`eCollege.monolithicBackend.signInApi`, unaffected by the group. Style them with
`element "Group"`.

## 3. Direction and separation

```
autoLayout tb 400 250
#          ^  ^   ^
#          |  |   nodeSeparation: gap within a rank
#          |  rankSeparation: gap between ranks
#          tb | bt | lr | rl
```

- **`tb`** suits layered flows (web → API → domain → adapters → external): the
  reading order matches the call direction. Produces wide diagrams.
- **`lr`** suits actor-centric views — people on the left, system in the middle,
  externals on the right. Good default for context and container views. Produces
  tall diagrams.
- **Raise `rankSeparation`** when *hub* elements congest. An element receiving
  several inbound relationships (a shared `securityService`, a central
  `notificationService`) is where crossings concentrate; more room between ranks
  is the cheapest fix. Try 400, then 600.

## 4. Relationship routing

```
relationship "Relationship" {
    routing direct      # or orthogonal, or curved
}
```

`orthogonal` draws right-angled lines, which in a dense graph reads as a maze and
makes every crossing conspicuous. `direct` usually looks cleaner once you have
more than ~15 elements. Try both; it costs one line.

## 5. Reduce what the view shows

A view with too much in it cannot be laid out well by any engine.

```
container eCollege "Containers" {
    include *
    exclude "student -> eCollege.platformDatabase"   # noisy derived relationship
}
```

Structurizr creates **implied** relationships: model a component-to-external
dependency and you get the container- and system-level ones for free. That is
usually what you want, but it can crowd higher-level views — `exclude` them there
rather than removing the specific relationship from the model.

If a component diagram is still unreadable, the container probably has too many
responsibilities. That is a finding about the architecture, worth saying out loud.

## 6. Manual positioning — and its cost

To place elements by hand, **omit `autoLayout`** from that view, then drag them in
Structurizr Lite, which saves as you go.

State the trade-off plainly before recommending it:

- Coordinates are written to the **workspace JSON** (`<name>.json`), **not the
  DSL**.
- So they do **not** travel with the `.dsl` file — not to
  playground.structurizr.com, not to a teammate, not to CI.
- Deleting the JSON to force a clean rebuild discards every manual position.
- Mixed approach: keep `autoLayout` and nudge afterwards. Positions persist, but
  are recomputed whenever the layout re-runs.

Automatic layout keeps the DSL as the single source of truth, which is the whole
point of diagrams-as-code. Prefer it unless the user explicitly wants pixel
control and accepts that it lives outside the DSL.

## Checklist

- [ ] Graphviz installed and confirmed `true`, or the user chose otherwise
- [ ] Layers wrapped in `group`
- [ ] `tb` for layered component views, `lr` for context/container
- [ ] `rankSeparation` raised if hub elements congest
- [ ] `routing direct` tried on dense views
- [ ] Derived relationships `exclude`d from views they crowd
- [ ] If positioning manually: the user knows positions live outside the DSL
