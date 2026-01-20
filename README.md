# Chili Framework for macOS

A complete C++ game development framework using SFML (Simple Fast Multimedia Library) on macOS. This is a macOS port of the popular Chili Framework, bringing Windows-based game development to Mac computers.

## 📋 Prerequisites

Before you begin, ensure you have the following installed on your macOS:

### 1. **Xcode Command Line Tools**
```bash
xcode-select --install
```

### 2. **Homebrew** (Package Manager)
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 3. **SFML 3.0+**
```bash
brew install sfml
```

### 4. **VS Code** (Optional but recommended)
Download from: https://code.visualstudio.com/

## 📁 Project Structure

```
ChiliFramework/
├── Chili.cpp           # Main header includes
├── ChiliImpl.cpp        # All class implementations
├── ChiliMain.cpp       # Entry point with event loop
├── Mainwindow.h        # Window class header
├── Game.h              # Game class header
├── Graphics.h          # Graphics class header
└── README.md           # This file
```

## 🚀 Quick Start

### Build the Project

```bash
cd /path/to/ChiliFramework
g++ -std=c++17 Chili.cpp ChiliImpl.cpp ChiliMain.cpp -o ChiliApp \
  -I/opt/homebrew/include -L/opt/homebrew/lib \
  -lsfml-graphics -lsfml-window -lsfml-system -lsfml-audio
```

### Run the Program

```bash
./ChiliApp
```

A window should open displaying a black screen with a white pixel at coordinates (100, 100).

## 📚 What's Included

### Core Classes

- **MainWindow** - Manages the application window
  - Creates and handles SFML render window
  - Event polling
  - Window state management

- **Graphics** - Handles all drawing operations
  - Clear frame
  - Display frame
  - Draw pixels
  - SFML rendering interface

- **Game** - Main game loop controller
  - Update model (game logic)
  - Compose frame (rendering)
  - Game state management

## 💻 System Architecture

```
ChiliMain.cpp (Entry Point)
    ↓
MainWindow (Window Management)
    ↓
Game (Game Loop)
    ├→ UpdateModel() (Logic)
    └→ ComposeFrame() (Graphics)
        └→ Graphics (Rendering)
            └→ SFML
```

## 🛠️ Building in VS Code

If you're using VS Code, you can use the built-in task:

1. Press `Cmd + Shift + B` to run the build task
2. Or select "Terminal" → "Run Build Task" → "Build and Run SFML"

## 🎮 Controls & Customization

The framework provides a foundation for:
- Window creation and event handling
- Graphics rendering
- Game loop management
- Audio support (SFML included)

Extend the `Game` class and `Graphics` class to add your own features!

## 📖 Next Steps

1. **Modify `Game::ComposeFrame()`** to add your graphics
2. **Implement `Game::UpdateModel()`** for game logic
3. **Add input handling** in `ChiliMain.cpp`
4. **Expand Graphics class** with more drawing functions

## 🔧 Troubleshooting

### Compilation Errors
- Ensure SFML is installed: `brew list sfml`
- Check paths: `-I/opt/homebrew/include -L/opt/homebrew/lib`

### Runtime Errors
- Window won't open: Check SFML installation
- Missing audio: Ensure `/opt/homebrew/lib` contains SFML libraries

### On M1/M2 Macs
- All commands should work out of the box
- SFML installs to `/opt/homebrew/` by default

## 📺 YouTube Series

This project is perfect for learning C++ game development on macOS! Follow along with the tutorial series.

## 📝 License

Free to use for educational purposes.

## 🤝 Contributing

Feel free to fork, modify, and improve this framework!

---

**Built with SFML 3.0+ and C++17 on macOS**
