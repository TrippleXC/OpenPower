# Client Layer (Frontend)

The Client is responsible for the **Presentation** and **User Interaction** layers of the application.

## 🎯 Responsibilities
* **Rendering:** Visualizing the game state using shaders (Arcade/OpenGL) and UI components (ImGui).
* **Input Handling:** Capturing raw mouse/keyboard events and converting them into semantic `GameActions`.
* **View Management:** Managing screen transitions and states (MainMenu, GameView, EditorView).
* **Audio:** Triggering sounds and music based on `GameEvents`.

## 🛡️ The Golden Rule
The Client is a **passive observer**. It must never modify the `GameState` directly.

| ✅ Correct Usage | ❌ Incorrect Usage |
| :--- | :--- |
| Reading `state.get_table("regions")` for rendering. | Writing `state.tables["regions"][id] = value`. |
| Dispatching an `ActionSetTax` command. | Calculating tax revenue logic inside a UI button. |
| Smoothly interpolating unit movement for visual polish. | Calculating pathfinding or collision detection. |