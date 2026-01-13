# Server Layer (State & Persistence)

The Server is the "Source of Truth" and handles the lifecycle of the game data.

## 🎯 Responsibilities
* **State Container:** Holding the authoritative `GameState` instance.
* **Persistence (I/O):** Loading static assets (TSV) and saving/loading user sessions (Parquet/JSON).
* **Session Lifecycle:** Managing game startup, mod resolution, and initial state compilation.
* **Atomic Writes:** Ensuring save files are written safely to disk.

## 🛡️ The Golden Rule
The Server cares about **Data Integrity**, not Data Processing.

| ✅ Correct Usage | ❌ Incorrect Usage |
| :--- | :--- |
| Parsing TSV files into Polars DataFrames. | Storing textures or GPU-side objects in the state. |
| Sanity checking data during load (e.g., no negative IDs). | Implementing simulation logic during the loading phase. |
| Holding the `ActionQueue` for the Engine to process. | Directly listening for keyboard/mouse inputs. |