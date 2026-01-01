#include <SFML/Graphics.hpp>
#include <SFML/Window.hpp>
#include <optional>
#include <cmath> // Required for sqrt()

class Player {
public:
    Player() {
        shape.setRadius(5.f);
        shape.setFillColor(sf::Color(75, 0, 130)); // Deep Purple
        shape.setPosition({400.f, 300.f});
    }

    void handleInput() {
        float speed = 5.f;
        sf::Vector2f movement(0.f, 0.f);

        // 1. Determine direction based on all keys pressed
        if (sf::Keyboard::isKeyPressed(sf::Keyboard::Key::Up))    movement.y -= 1.f;
        if (sf::Keyboard::isKeyPressed(sf::Keyboard::Key::Down))  movement.y += 1.f;
        if (sf::Keyboard::isKeyPressed(sf::Keyboard::Key::Left))  movement.x -= 1.f;
        if (sf::Keyboard::isKeyPressed(sf::Keyboard::Key::Right)) movement.x += 1.f;

        // 2. Normalize the movement vector
        // The length (magnitude) is calculated using the Pythagorean theorem: sqrt(x^2 + y^2)
        float length = std::sqrt(movement.x * movement.x + movement.y * movement.y);

        if (length != 0.f) {
            // Divide x and y by the length to get a "Unit Vector" (length of 1)
            // Then multiply by speed to get the constant desired speed
            movement = (movement / length) * speed;
        }

        shape.move(movement);
    }

    void draw(sf::RenderWindow& window) {
        window.draw(shape);
    }

private:
    sf::CircleShape shape;
};

int main() {
    sf::RenderWindow window(sf::VideoMode({800, 600}), "SFML 3.0 Normalized Movement");
    window.setFramerateLimit(60);

    Player player;

    while (window.isOpen()) {
        std::optional<sf::Event> event;
        while ((event = window.pollEvent())) {
            if (event->is<sf::Event::Closed>()) {
                window.close();
            }
        }

        player.handleInput();

        window.clear(sf::Color::Black);
        player.draw(window);
        window.display();
    }

    return 0;
}