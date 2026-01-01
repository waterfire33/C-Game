#include <SFML/Graphics.hpp>
#include <SFML/Window.hpp>
#include <optional>
#include <cmath>

/**
 * @class Player
 * @brief Handles player movement, PS5 haptics, and dynamic color changes on collision.
 * * This class encapsulates the circle shape and logic for reacting to both 
 * keyboard and joystick inputs. It includes boundary detection for an 800x600 window.
 */
class Player {
public:
    Player() {
        radius = 5.f;
        // Define colors for state changes
        purple = sf::Color(75, 0, 130);
        coolBlue = sf::Color(0, 191, 255); // Deep Sky Blue

        shape.setRadius(radius);
        shape.setFillColor(purple);
        shape.setPosition({400.f, 300.f}); // Start in center
    }

    /**
     * @brief Processes inputs, calculates movement, and handles wall collisions.
     */
    void handleInput() {
        float speed = 5.f;
        sf::Vector2f movement(0.f, 0.f);

        // --- 1. KEYBOARD INPUT ---
        if (sf::Keyboard::isKeyPressed(sf::Keyboard::Key::Up))    movement.y -= 1.f;
        if (sf::Keyboard::isKeyPressed(sf::Keyboard::Key::Down))  movement.y += 1.f;
        if (sf::Keyboard::isKeyPressed(sf::Keyboard::Key::Left))  movement.x -= 1.f;
        if (sf::Keyboard::isKeyPressed(sf::Keyboard::Key::Right)) movement.x += 1.f;

        // --- 2. PS5 CONTROLLER INPUT ---
        if (sf::Joystick::isConnected(0)) {
            float joyX = sf::Joystick::getAxisPosition(0, sf::Joystick::Axis::X);
            float joyY = sf::Joystick::getAxisPosition(0, sf::Joystick::Axis::Y);
            
            // Apply deadzone logic to prevent stick drift
            if (std::abs(joyX) > 15.f) movement.x = joyX / 100.f;
            if (std::abs(joyY) > 15.f) movement.y = joyY / 100.f;
        }

        // --- 3. NORMALIZATION ---
        // Prevents faster movement when moving diagonally
        float length = std::sqrt(movement.x * movement.x + movement.y * movement.y);
        if (length != 0.f) {
            movement = (movement / length) * speed;
        }

        // --- 4. COLLISION DETECTION & FEEDBACK ---
        sf::Vector2f nextPos = shape.getPosition() + movement;
        bool hitWall = false;

        // Check window boundaries (800x600)
        if (nextPos.x <= 0) { nextPos.x = 0; hitWall = true; }
        if (nextPos.x >= 800 - (radius * 2)) { nextPos.x = 800 - (radius * 2); hitWall = true; }
        if (nextPos.y <= 0) { nextPos.y = 0; hitWall = true; }
        if (nextPos.y >= 600 - (radius * 2)) { nextPos.y = 600 - (radius * 2); hitWall = true; }

        if (hitWall) {
            shape.setFillColor(coolBlue); // Change to Blue on hit
            
        } else {
            shape.setFillColor(purple); // Stay Purple while moving freely
        }

        shape.setPosition(nextPos);
    }

    /**
     * @brief Draws the player to the screen.
     */
    void draw(sf::RenderWindow& window) {
        window.draw(shape);
    }

private:
    sf::CircleShape shape;
    float radius;
    sf::Color purple;
    sf::Color coolBlue;
};

/**
 * @brief Entry point of the application.
 * Sets up the SFML window and runs the game loop at 60 FPS.
 */
int main() {
    // SFML 3.0 Window setup
    sf::RenderWindow window(sf::VideoMode({800, 600}), "PS5 Controller & Collision Test");
    window.setFramerateLimit(60);

    Player player;

    // Main Game Loop
    while (window.isOpen()) {
        std::optional<sf::Event> event;
        while ((event = window.pollEvent())) {
            if (event->is<sf::Event::Closed>()) {
                window.close();
            }
        }

        // Update logic
        player.handleInput();

        // Rendering logic
        window.clear(sf::Color::Black);
        player.draw(window);
        window.display();
    }

    return 0;
} 