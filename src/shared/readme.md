# Shared Layer (Contracts & Utils)

Common definitions and utilities used by the Client, Server, and Engine to prevent circular dependencies.

## 🎯 Responsibilities
* **Data Contracts:** Defining `GameAction`, `GameEvent`, and Configuration schemas.
* **Core Utilities:** Pure functional tools like `SimulationTimer` or `PathUtils`.
* **Path Resolution:** Handling cross-platform file paths and mod-based asset discovery.

## 🛡️ The Golden Rule
Shared code must be **pure and lightweight**. It must never import from `client`, `server`, or `engine`.

| ✅ Correct Usage | ❌ Incorrect Usage |
| :--- | :--- |
| Defining an `ActionSetGameSpeed` dataclass. | Implementing the code that changes the speed. |
| A `SimulationTimer` that calculates time dilation. | Storing a global `current_game_state` reference. |
| Defining global constants like `GAME_EPOCH`. | Importing heavy simulation-specific libraries. |