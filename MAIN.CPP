#include <SFML/Graphics.hpp>
#include <SFML/Window.hpp>
#include <optional>

// 1. Encapsulate logic in a Player class
class Player {
public:
    Player() {
        shape.setRadius(5.f);
        shape.setFillColor(sf::Color::White);
        shape.setPosition({400.f, 300.f});
    }

    void handleInput() {
        float speed = 5.f;
        // SFML 3.0 uses Key for movement
        if (sf::Keyboard::isKeyPressed(sf::Keyboard::Key::Up))    shape.move({0.f, -speed});
        if (sf::Keyboard::isKeyPressed(sf::Keyboard::Key::Down))  shape.move({0.f, speed});
        if (sf::Keyboard::isKeyPressed(sf::Keyboard::Key::Left))  shape.move({-speed, 0.f});
        if (sf::Keyboard::isKeyPressed(sf::Keyboard::Key::Right)) shape.move({speed, 0.f});
    }

    void draw(sf::RenderWindow& window) {
        window.draw(shape);
    }

private:
    sf::CircleShape shape;
};

int main() {
    // Create the window
    sf::RenderWindow window(sf::VideoMode({800, 600}), "SFML 3.0 Tahoe");
    window.setFramerateLimit(60);

    Player player;

    while (window.isOpen()) {
        // Fix: Added extra parentheses to silence the [-Wparentheses] warning
        std::optional<sf::Event> event;
        while ((event = window.pollEvent())) {
            if (event->is<sf::Event::Closed>()) {
                window.close();
            }
        }

        // Update logic
        player.handleInput();

        // Draw logic
        window.clear(sf::Color::Black);
        player.draw(window);
        window.display();
    }

    return 0;
}