# AnchorForge Studio

A local browser interface for the [Kitchen Party Protocol](https://github.com/jodydugas-ctrl/Kitchen-Party-Protocol) and its AnchorForge Organ. Tested against KPP commit `802d8ee29c2285bdb793053fc7d65c3304bcfd27` and AnchorForge Organ 0.3.0.

## Run

From the KPP checkout, use Node.js 22.12+ and Python 3.11–3.14.

```sh
cd examples/anchorforge-studio
npm ci
npm run dev
```

Studio uses the containing KPP checkout by default. Set `KPP_ROOT` to select
another compatible checkout with AnchorForge Organ 0.3.0.

Open http://127.0.0.1:3000. Environment settings can also go in `.env.local`. Set `KPP_PYTHON` to the Python executable if it differs from `python3`. For a production build, run `npm run build` and start with `NODE_ENV=production npm start`.

## Work in the GUI

- **Workbench** checks the current source with native KPP. It supports Anchor blueprints, structured designs, Recipe/3 and Recipe/4, AnchorForge specs, and portable handoffs. Topology and the Notepad command simulation are local previews. Native handoff inspection checks manifest and payload integrity in memory. The Python bridge syntax-checks and returns the original emitted Python bytes.
- **Converter** drafts responsibilities from code using the offline heuristic or optional Gemini assistance. Review and edit the AnchorForge input, then select **Propose Recipe with AnchorForge**. Download the native Recipe and matching review together. A conventional, artifact-delivery Recipe at fidelity 1 is the editable starting point. You can also load a complete `anchorforge.organ-spec/1` JSON file in the workbench.
- **KPP Workspace** reads the native build step of one existing workspace. Set `KPP_WORKSPACE` on the server, then refresh the tab to see phase, next obligation, and acceptance test. A native structural check does not exercise the candidate or grant Baker acceptance.

### Bring in a Recipe from Anchor Studio

In the Node-RED Anchor Studio workspace, save the project and choose **Contracts
→ Download saved KPP Recipe**. Open the JSON file in AnchorForge Studio's
workbench. Once the native check passes, **Prepare KPP work packet** renders the
declared contract and verification obligations. **Extend Recipe with
AnchorForge** accepts an `anchorforge.extension/1` document and returns a new
Recipe and matching review. The previous obligations stay intact. Pin an
approved extension in a new workspace when ready to build.

For a reviewed Recipe, use the KPP CLI to pin it in a fresh workspace, run scoped tests, and record Baker acceptance separately. For example, from the KPP checkout:

```sh
PYTHONPATH=src python3 -m kpp new --recipe /path/to/proposed-recipe.json --workspace /path/to/new-workspace
PYTHONPATH=src python3 -m kpp build-step --workspace /path/to/new-workspace
```

The Studio server binds to loopback by default. The server runs the checkout selected by the host and verifies the AnchorForge Organ carrier against its supported SHA-256 before loading it. Submitted code, blueprint payloads, and handoff payloads remain data. Gemini is optional and receives the source only when you use the AI extraction action.

## Component notices

This app incorporates the maintainer-supplied AnchorForge Studio source.
The imported Apache-2.0 notice in `src/App.tsx` is retained with the
[Apache 2.0 license text](LICENSE-APACHE-2.0.txt). KPP and MantleOS components
retain their existing [component notices](../../THIRD-PARTY-NOTICES.md).

## Proposed Transition Lab

The **Transition Lab** tab validates the proposed `anchor.transition-trace/1` JSON format through the native KPP Python bridge. It shows only **structural** consistency: declared Gate decisions, ordered before/after snapshots, effect evidence labels, and final-state continuity. It never executes an Anchor, verifies a model prediction, authenticates host observations, or grants Baker acceptance. See `../../docs/ANCHOR-TRANSITION-TRACE.md` and `../../examples/notepad-transition-trace.json` for the draft contract and example. The application source was originally adapted from the maintainer-provided AnchorForge Studio ZIP; this change extends the existing checked-in GUI rather than introducing another independent implementation.
