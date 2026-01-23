#include <SFML/Graphics.hpp>
#include <iostream>

int main() {
    // 1. Create the Window
    auto window = sf::RenderWindow(sf::VideoMode({800, 600}), "Purple Sprite Animation");
    window.setFramerateLimit(60);

    // 2. Load the Texture
    sf::Texture texture;
    // Ensure "circle_sprite_sheet.png" is in the same folder
    if (!texture.loadFromFile("circle_sprite_sheet.png")) {
        std::cerr << "Error: Could not load circle_sprite_sheet.png" << std::endl;
        return -1;
    }

    // 3. Setup the Sprite
    sf::Sprite sprite(texture);

    // Animation Settings
    const int frameWidth = 64;   
    const int frameHeight = 64;  
    const int numFrames = 4;     
    int currentFrame = 0;
    
    // Timer
    sf::Clock clock;
    const float frameTime = 0.1f; 
    float currentTime = 0;

    // 4. Game Loop
    while (window.isOpen()) {
        while (const auto event = window.pollEvent()) {
            if (event->is<sf::Event::Closed>()) {
                window.close();
            }
            else if (const auto* keyPressed = event->getIf<sf::Event::KeyPressed>()) {
                if (keyPressed->code == sf::Keyboard::Key::Escape) {
                    window.close();
                }
            }
        }

        // 5. Update Animation
        currentTime += clock.restart().asSeconds();
        if (currentTime >= frameTime) {
            currentTime = 0; 
            currentFrame++;  

            if (currentFrame >= numFrames) {
                currentFrame = 0; 
            }
            sprite.setTextureRect(sf::IntRect({currentFrame * frameWidth, 0}, {frameWidth, frameHeight}));
        }

        // 6. Draw
        window.clear(sf::Color::Black);
        window.draw(sprite);
        window.display();
    }

    return 0;
}