# Modules (Content & Gameplay)

This is where the actual game content and specific mechanics are implemented.

## 🎯 Responsibilities
* **Gameplay Mechanics:** Concrete implementations of `ISystem` (Politics, Economy, AI).
* **Static Assets:** TSV data tables, map textures, audio, and localizations.
* **System Registration:** Defining how the mod hooks into the core Engine.

## 🛡️ The Golden Rule
The Engine should be able to run without any modules (though it would do nothing). All "Game Rules" live here.

| ✅ Correct Usage | ❌ Incorrect Usage |
| :--- | :--- |
| Using `SimulationTimer` to calculate daily consumption. | Modifying the core `simulator.py` to add a mechanic. |
| Adding a new `oil_reserve` column to `regions.tsv`. | Hardcoding UI panels inside a logic system. |
| Emitting a `EventNewDay` for other systems to hear. | Blocking the main thread with `time.sleep()`. |