# Engine Layer (Simulation Logic)

The Engine is the generic machinery that orchestrates the execution of the simulation.

## 🎯 Responsibilities
* **ECS Orchestration:** Managing the System Dependency Graph and executing `ISystem.update()` in topological order.
* **Simulation Loop:** Driving the `step()` cycle (Input Processing -> Logic Update -> Event Dispatch).
* **Mod Discovery:** Scanning and registering systems and logic from the `modules/` directory.

## 🛡️ The Golden Rule
The Engine must remain **content-agnostic**. It knows *how* to run a system, but not *what* the system does.

| ✅ Correct Usage | ❌ Incorrect Usage |
| :--- | :--- |
| Calling generic `system.update(state, dt)`. | Hardcoding specific logic for `EconomySystem`. |
| Handling system-level exceptions to prevent crashes. | Importing `arcade` or `imgui` (No UI in Engine). |
| Sorting systems based on their `dependencies`. | Defining rules for population growth. |