# AI Copilot Instructions for VSCODE C++ SFML Project

## Project Overview
This is an **SFML-based interactive game** written in C++17 featuring a harpoon fishing mechanic. The main game files (`purple2.cpp`, `purple3.cpp`) implement a player-controlled character that hunts a target using a harpoon weapon system with physics, collision detection, particle effects, and audio.

## Build & Run Workflow
**Command**: Use the configured "Build and Run SFML" task (auto-configured in VS Code).
**Build Command**: `g++ -std=c++17 '${file}' -o '${fileDirname}/${fileBasenameNoExtension}' -I/opt/homebrew/include -L/opt/homebrew/lib -lsfml-graphics -lsfml-window -lsfml-system -lsfml-audio -lsfml-network`
- Requires SFML 3.0+ installed via Homebrew at `/opt/homebrew/lib`
- Outputs executable to same directory as source file
- Audio files: expects `Boom3.wav` and `Shoot11.wav` in Downloads or local directory

## Architecture & Key Components
The game uses a **component-based, single-file architecture**:
- **Player**: Controls via WASD movement, arrow keys or joystick aiming, space/trigger to fire
- **Target**: Enemy that bounces around and can be caught
- **ParticleSystem**: Handles visual explosions on collision/death (30 particles per emission)
- **GameState Enum**: `SWIMMING` → `FIRING` → `STRUGGLING` → `RETRACTING` (manages weapon lifecycle)

### Critical Patterns
- **Vector math**: Normalize with `getVecLength()` helper, use `sf::Vector2f` for all positions/velocities
- **Collision detection**: Simple distance-based (radius + radius check)
- **Timing**: Delta-time (`dt`) clamped to 0.1s max to prevent physics instability
- **Audio**: Created with `std::optional<sf::Sound>` wrapper; `ParticleSystem` holds raw sound pointers, Player manages shoot sound
- **Death mechanics**: Sets `isDead=true` for 3s, visual explosion via particle emit, enemy resets, player keeps position

## Input Handling
Located in `Player::handleInput()` - supports **dual input**:
- **Keyboard**: WASD (move), Arrows (aim), Space (fire/struggle)
- **Joystick**: Left stick (move), Z/R axes (aim), Right trigger (fire), 15% deadzone for sticks, 20% for aim sticks

## File Organization
- **purple.cpp**: Simple sprite animation demo (not main game)
- **purple2.cpp**, **purple3.cpp**: Identical game implementations (likely for version control/experiments)
- **purpleT.cpp**, **purple3.cpp**: Smaller test files
- **MAIN.CPP**: Basic player class example
- **Build outputs**: Executables in workspace root, MAIN binary in `/output/`

## SFML 3.0 Migration Notes
- Event handling: Use `window.pollEvent()` with `std::optional` pattern
- Key input: `sf::Keyboard::Key::*` enum (not bare integers)
- Window: `sf::VideoMode({width, height})` constructor
- Joystick: `sf::Joystick::getAxisPosition(id, axis)` returns float 0-100 (deadzones must be applied manually)
- Shapes: Use `sf::CircleShape`, `sf::RectangleShape` with `setOrigin()` for rotations

## Common Modifications
- **Game constants**: WIDTH, HEIGHT at top of file; PI = 3.14159265f
- **Physics tuning**: Player speed 280.0, harpoon fire speed via angle/velocity, retract speed 900-1400
- **Particle emission**: Hardcoded 30 particles; angle/speed randomized
- **Audio feedback**: Explosion pitch randomized (0.8-1.2), separate sounds for boom and shoot
