# OpenPower: Technical Specification & Architecture

> **⚠️ NOTE: Work in Progress**
> This document describes the **target architecture** for version 1.0.
> Not all features listed below (specifically networking and full modding support) are fully implemented yet.
> Current status: **Single-player prototype phase.**

**OpenPower** is a modular, data-driven grand strategy engine written in Python. It is designed as a modern, open-source spiritual successor to *SuperPower 2*.

The engine moves away from traditional Object-Oriented Programming (OOP) and Entity-Component-Systems (ECS) in favor of **Data-Oriented Design (DOD)**. By leveraging **Polars**, the engine processes game state as massive in-memory tables, allowing for vectorized performance that rivals C++ engines while maintaining the moddability of Python.

---

## 1. Technology Stack

* **Language:** Python 3.10+
* **Core Engine:** [Polars](https://pola.rs/) (High-performance DataFrames, written in Rust).
* **Rendering:** [Arcade](https://api.arcade.academy/) (OpenGL 3.3+).
* **UI:** [imgui-bundle](https://github.com/pthom/imgui_bundle) (Dear ImGui bindings).
* **Data Configuration:** [rtoml](https://pypi.org/project/rtoml/) (Fastest Rust-based TOML parser).
* **Bulk Data:** TSV/CSV (Standard Library) for map regions and population grids.
* **Serialization:** [Apache Arrow](https://arrow.apache.org/) (via Polars IPC) for instant Save/Load.

---

## 2. Target Project Structure

The project follows a **Client-Server** architecture (even in single-player) and adheres to **Composition over Inheritance**.

```text
OpenPower/
├── modules/                  # --- CONTENT DATABASE ---
│   └── base/
│       ├── data/             # Human-readable Source (TSV, TOML)
│       └── assets/           # Binary Assets (Textures, Audio)
│
└── src/                      # --- SOURCE CODE ---
    ├── shared/               # [PROTOCOL] Common definitions
    │   ├── schema.py         # Polars DataFrame structures
    │   └── actions.py        # Command Pattern (Action Definitions)
    │
    ├── engine/               # [LOGIC] Pure Simulation Library
    │   ├── systems/          # Stateless Logic Functions (Economy, War)
    │   └── simulator.py      # Main Tick Function (State + Action -> NewState)
    │
    ├── server/               # [HOST] Game Session Management
    │   ├── state.py          # GameState Container (Polars Store)
    │   ├── io/               # Loader (TSV->DF) & Exporter (DF->TSV)
    │   └── session.py        # Logic Orchestrator
    │
    └── client/               # [VIEW] Visualization Only
        ├── network_client.py # Network Abstraction (Mock for now)
        ├── renderers/        # Map & Unit Rendering
        └── ui/               # ImGui Interface (Editor & Gameplay)

```

---

## 3. Data Architecture: The "Compiler" Approach

We treat game data as a compilation process: **Human Source -> Machine State**.

### A. Source: TOML & TSV (For Humans)

Optimized for readability and version control (Git).

* **Entities (Countries, Units):** **TOML**. Hierarchical data (e.g., `UKR.toml`).
* **Arrays (Regions, Population):** **TSV**. Compact spreadsheet data for 10,000+ rows.

### B. Runtime: Polars DataFrames (For Logic)

Optimized for SIMD vectorization and CPU cache locality.

* **Initialization:** `loader.py` compiles all module files into `GameState`.
* **Indexing:** Data is processed by **Columns**, not Rows.

### C. Storage: Apache Arrow (For Speed)

* **Save Game:** Direct memory dump of DataFrames to disk (`.arrow`).
* **Speed:** Instant Save/Load (zero parsing required).

---

## 4. Networking & Logic Flow (Command Pattern)

> **Status:** Networking is currently **not implemented**. The architecture is designed to support it seamlessly in the future via the `Action` system.

The Logic (`engine`) is strictly separated from the View (`client`) via a **Command Pattern**.

1. **Client:** The user clicks "Raise Taxes". The client **does not** change the data. Instead, it sends an `ActionSetTax` object to the Server.
2. **Server:** Receives the Action, validates it, and pushes it to the Engine.
3. **Engine:** In the next tick, the Engine applies the Action to the `GameState` using pure functions.
4. **Sync:** The updated `GameState` (or delta) is sent back to the Client for rendering.

```python
# Conceptual Example of an Action
@dataclass
class ActionSetTax(GameAction):
    country_tag: str
    new_rate: float

```

---

## 5. Development Workflow

1. **Setup:** `pip install -r requirements.txt`.
2. **Run Game:** `python main.py`.
3. **Edit Map (Data-Driven):**
* Open `modules/base/data/map/regions.tsv` in Excel/LibreOffice.
* Change terrain, owner, or population.
* Restart the game (or reload via Editor).


4. **Editor Mode:**
* In-game Editor allows modifying DataFrames visually.
* Changes are written back to `.tsv` files via `server.io.exporter`.