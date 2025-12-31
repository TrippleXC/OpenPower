import arcade
from src.client.window import MainWindow

def main():
    print("OpenPower starting...")
    
    window = MainWindow()
    
    # The setup method initializes the default view (currently EditorView).
    window.setup()
    
    arcade.run()

if __name__ == "__main__":
    main()
