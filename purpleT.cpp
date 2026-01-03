#include <SFML/Graphics.hpp>
#include <SFML/Window.hpp>
#include <optional>
#include <cmath>
#include <vector>
#include <iostream>
#include <ctime>

const float PI = 3.14159265f;
const int WIDTH = 800;
const int HEIGHT = 600;

float getVecLength(sf::Vector2f v) { return std::sqrt(v.x * v.x + v.y * v.y); }

enum class GameState { SWIMMING, FIRING, STRUGGLING, RETRACTING };

struct Particle {
    sf::RectangleShape shape;
    sf::Vector2f velocity;
    float lifetime;
};

class ParticleSystem {
public:
    std::vector<Particle> particles;

    void emit(sf::Vector2f pos) {
        for (int i = 0; i < 20; ++i) {
            Particle p;
            p.shape.setSize({ 4.f, 4.f });
            p.shape.setFillColor(sf::Color::White);
            p.shape.setPosition(pos);
            float angle = (std::rand() % 360) * PI / 180.f;
            float speed = (std::rand() % 300) + 100.f;
            p.velocity = { std::cos(angle) * speed, std::sin(angle) * speed };
            p.lifetime = 0.5f; 
            particles.push_back(p);
        }
    }

    void update(float dt) {
        for (auto it = particles.begin(); it != particles.end();) {
            it->lifetime -= dt;
            it->shape.move(it->velocity * dt);
            if (it->lifetime <= 0) it = particles.erase(it);
            else ++it;
        }
    }

    void draw(sf::RenderWindow& window) {
        for (auto& p : particles) window.draw(p.shape);
    }
};

class Target {
public:
    sf::CircleShape shape;
    sf::Vector2f velocity;
    float radius = 10.f;
    bool isCaught = false;

    Target() {
        shape.setRadius(radius);
        shape.setFillColor(sf::Color::Yellow);
        shape.setOrigin({radius, radius});
        reset();
    }

    void reset() {
        shape.setPosition({ 700.f, (float)(std::rand() % 500 + 50) });
        velocity = { -160.f, 120.f };
        isCaught = false;
    }

    void update(float dt) {
        if (isCaught) return;
        sf::Vector2f pos = shape.getPosition();
        if (pos.x - radius <= 0 || pos.x + radius >= WIDTH) velocity.x *= -1;
        if (pos.y - radius <= 0 || pos.y + radius >= HEIGHT) velocity.y *= -1;
        shape.move(velocity * dt);
    }

    void draw(sf::RenderWindow& window) {
        window.draw(shape);
    }
};

class Player {
public:
    Player() {
        radius = 12.f;
        shape.setRadius(radius);
        shape.setFillColor(sf::Color(75, 0, 130)); 
        shape.setOrigin({radius, radius});
        shape.setPosition({100.f, 300.f});

        harpoonHead.setSize({20.f, 6.f});
        harpoonHead.setFillColor(sf::Color::Yellow);
        harpoonHead.setOrigin({0.f, 3.f});

        barBg.setSize({100.f, 12.f});
        barBg.setFillColor(sf::Color(50, 50, 50));
        barFg.setFillColor(sf::Color::Cyan);
    }

    void handleInput(float dt, Target& target, ParticleSystem& ps) {
        sf::Vector2f moveVec(0.f, 0.f);
        bool joy = sf::Joystick::isConnected(0);

        if (state != GameState::STRUGGLING && state != GameState::RETRACTING) {
            if (joy) {
                float lx = sf::Joystick::getAxisPosition(0, sf::Joystick::Axis::X);
                float ly = sf::Joystick::getAxisPosition(0, sf::Joystick::Axis::Y);
                if (std::abs(lx) > 15.f) moveVec.x = lx / 100.f;
                if (std::abs(ly) > 15.f) moveVec.y = ly / 100.f;

                float rx = sf::Joystick::getAxisPosition(0, sf::Joystick::Axis::U);
                float ry = sf::Joystick::getAxisPosition(0, sf::Joystick::Axis::V);
                if (std::abs(rx) > 20.f || std::abs(ry) > 20.f) {
                    aimAngle = std::atan2(ry, rx) * 180.f / PI;
                }
            }
            if (sf::Keyboard::isKeyPressed(sf::Keyboard::Key::W)) moveVec.y -= 1.f;
            if (sf::Keyboard::isKeyPressed(sf::Keyboard::Key::S)) moveVec.y += 1.f;
            if (sf::Keyboard::isKeyPressed(sf::Keyboard::Key::A)) moveVec.x -= 1.f;
            if (sf::Keyboard::isKeyPressed(sf::Keyboard::Key::D)) moveVec.x += 1.f;

            bool fireTriggered = sf::Keyboard::isKeyPressed(sf::Keyboard::Key::Space) || (joy && sf::Joystick::isButtonPressed(0, 0));
            if (fireTriggered && state == GameState::SWIMMING) {
                state = GameState::FIRING;
                harpoonPos = shape.getPosition();
                float rad = aimAngle * PI / 180.f;
                harpoonVel = { std::cos(rad) * 1000.f, std::sin(rad) * 1000.f };
            }
        }

        if (state == GameState::STRUGGLING) {
            struggleProgress -= 55.f * dt; 
            static bool canTap = true;
            bool mash = sf::Keyboard::isKeyPressed(sf::Keyboard::Key::Space) || (joy && sf::Joystick::isButtonPressed(0, 0));
            if (mash) {
                if (canTap) { struggleProgress += 16.f; canTap = false; }
            } else { canTap = true; }

            if (struggleProgress >= 100.f) state = GameState::RETRACTING;
            if (struggleProgress <= 0.f) { state = GameState::RETRACTING; target.isCaught = false; }
            harpoonPos = target.shape.getPosition();
        }

        updatePhysics(moveVec, dt, target, ps);
    }

    void updatePhysics(sf::Vector2f moveVec, float dt, Target& target, ParticleSystem& ps) {
        float len = getVecLength(moveVec);
        if (len != 0.f) shape.move((moveVec / len) * 280.f * dt);

        if (state == GameState::FIRING) {
            harpoonPos += harpoonVel * dt;
            if (getVecLength(harpoonPos - target.shape.getPosition()) < (radius + target.radius)) {
                state = GameState::STRUGGLING;
                target.isCaught = true;
                struggleProgress = 30.f;
            }
            if (getVecLength(harpoonPos - shape.getPosition()) > 500.f) state = GameState::RETRACTING;
        }

        if (state == GameState::RETRACTING) {
            sf::Vector2f dir = shape.getPosition() - harpoonPos;
            float dist = getVecLength(dir);
            float speed = target.isCaught ? 1400.f : 900.f;

            if (dist < 15.f) {
                state = GameState::SWIMMING;
                if (target.isCaught) {
                    ps.emit(shape.getPosition()); 
                    target.reset();
                }
            } else {
                harpoonPos += (dir / dist) * speed * dt;
            }
            if (target.isCaught) target.shape.setPosition(harpoonPos);
        }

        harpoonHead.setPosition(harpoonPos);
        if (state == GameState::RETRACTING) {
            sf::Vector2f dir = shape.getPosition() - harpoonPos;
            harpoonHead.setRotation(sf::radians(std::atan2(dir.y, dir.x)));
        } else {
            harpoonHead.setRotation(sf::degrees(aimAngle));
        }
    }

    void draw(sf::RenderWindow& window) {
        if (state != GameState::SWIMMING) {
            // SFML 3.0 Vertex initialization using initializer lists
            sf::Vertex line[] = { 
                { shape.getPosition(), sf::Color::Yellow }, 
                { harpoonPos, sf::Color::Yellow } 
            };
            window.draw(line, 2, sf::PrimitiveType::Lines);
            window.draw(harpoonHead);
        }
        if (state == GameState::STRUGGLING) {
            barBg.setPosition(shape.getPosition() + sf::Vector2f(-50.f, -45.f));
            barFg.setPosition(barBg.getPosition());
            barFg.setSize({ struggleProgress, 12.f });
            window.draw(barBg);
            window.draw(barFg);
        }
        window.draw(shape);
    }

private:
    sf::CircleShape shape;
    sf::RectangleShape harpoonHead, barBg, barFg;
    sf::Vector2f harpoonPos, harpoonVel;
    float radius, aimAngle = 0.f, struggleProgress = 0.f;
    GameState state = GameState::SWIMMING;
};

int main() {
    std::srand(static_cast<unsigned>(time(NULL)));
    sf::RenderWindow window(sf::VideoMode({WIDTH, HEIGHT}), "Harpoon Gun Prototype");
    window.setFramerateLimit(60);
    sf::Clock clock;

    Player player;
    Target target;
    ParticleSystem ps;

    while (window.isOpen()) {
        float dt = clock.restart().asSeconds();
        std::optional<sf::Event> event;
        while ((event = window.pollEvent())) {
            if (event->is<sf::Event::Closed>()) window.close();
        }

        target.update(dt);
        player.handleInput(dt, target, ps);
        ps.update(dt);

        window.clear(sf::Color(15, 30, 55));
        target.draw(window);
        player.draw(window);
        ps.draw(window);
        window.display();
    }
    return 0;
}