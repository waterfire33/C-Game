#include <SFML/Graphics.hpp>
#include <SFML/Window.hpp>
#include <SFML/System.hpp>
#include <SFML/Audio.hpp>
#include <vector>
#include <cmath>
#include <cstdlib>
#include <ctime>
#include <algorithm>
#include <iostream>
#include <memory>
#include <optional> // Required for SFML 3.0
#include <cstdint>  // Required for std::uint8_t

// --- Constants ---
const unsigned int WIDTH = 800;
const unsigned int HEIGHT = 600;
const float PI = 3.14159265f;

// --- Helper Functions ---
float getVecLength(const sf::Vector2f& v) {
    return std::sqrt(v.x * v.x + v.y * v.y);
}

// --- Enums ---
enum class GameState { SWIMMING, FIRING, STRUGGLING, RETRACTING };

// --- Particle System ---
struct Particle {
    sf::Vector2f pos;
    sf::Vector2f vel;
    float lifetime;
};

class ParticleSystem {
public:
    std::vector<Particle> particles;
    sf::Sound* explosionSound = nullptr;

    void emit(sf::Vector2f pos) {
        // Sound is handled in Player class for timing control
        for (int i = 0; i < 30; ++i) {
            float angle = (static_cast<float>(rand()) / RAND_MAX * 360.0f) * PI / 180.0f;
            float speed = (static_cast<float>(rand()) / RAND_MAX * 300.0f) + 100.0f;
            
            Particle p;
            p.pos = pos;
            p.vel = { std::cos(angle) * speed, std::sin(angle) * speed };
            p.lifetime = 1.0f;
            particles.push_back(p);
        }
    }

    void update(float dt) {
        for (int i = particles.size() - 1; i >= 0; i--) {
            particles[i].lifetime -= dt;
            particles[i].pos += particles[i].vel * dt;
            particles[i].vel *= 0.92f; // Friction

            if (particles[i].lifetime <= 0) {
                particles.erase(particles.begin() + i);
            }
        }
    }

    void draw(sf::RenderWindow& window) {
        sf::RectangleShape rect({4.f, 4.f});
        for (const auto& p : particles) {
            rect.setPosition(p.pos);
            sf::Color c = sf::Color::White;
            c.a = static_cast<std::uint8_t>(std::max(0.0f, p.lifetime) * 255);
            rect.setFillColor(c);
            window.draw(rect);
        }
    }
};

// --- Target Class ---
class Target {
public:
    sf::Vector2f pos;
    sf::Vector2f vel;
    float radius = 10.0f;
    bool isCaught = false;

    Target() {
        reset();
    }

    void reset() {
        float randomY = (static_cast<float>(rand()) / RAND_MAX * 500.0f) + 50.0f;
        pos = { 700.0f, randomY };
        vel = { -160.0f, 120.0f };
        isCaught = false;
    }

    void update(float dt) {
        if (isCaught) return;

        if (pos.x - radius <= 0 || pos.x + radius >= WIDTH) vel.x *= -1;
        if (pos.y - radius <= 0 || pos.y + radius >= HEIGHT) vel.y *= -1;

        pos += vel * dt;
    }

    void draw(sf::RenderWindow& window) {
        sf::CircleShape circle(radius);
        circle.setOrigin({radius, radius});
        circle.setPosition(pos);
        circle.setFillColor(sf::Color::Yellow);
        window.draw(circle);
    }
};

// --- Player Class ---
class Player {
public:
    sf::Vector2f pos = { 100.0f, 300.0f };
    float radius = 12.0f;
    
    sf::Vector2f harpoonPos = { 100.0f, 300.0f };
    sf::Vector2f harpoonVel = { 0.0f, 0.0f };
    float aimAngle = 0.0f; 
    
    GameState state = GameState::SWIMMING;
    float struggleProgress = 0.0f;
    bool canTap = true;
    
    // Timing variables
    float explosionTimer = 0.0f; 
    bool explosionSoundPlayed = false;

    // --- DEATH VARIABLES ---
    bool isDead = false;
    float deathTimer = 0.0f;

    sf::Sound* shootSound = nullptr;

    void handleInput(float dt, Target& target, ParticleSystem& ps) {
        
        // --- DEATH CHECK ---
        if (isDead) {
            deathTimer -= dt;
            if (deathTimer <= 0.0f) {
                // RESPAWN TIME!
                isDead = false;
                // We do NOT reset position. Player stays where they died.
            }
            // Block all input while dead
            return; 
        }
        // -------------------

        sf::Vector2f moveVec(0.0f, 0.0f);
        sf::Vector2f aimVec(0.0f, 0.0f);
        bool fireTriggered = false;
        bool struggleButton = false;

        // --- 1. Keyboard Input ---
        if (sf::Keyboard::isKeyPressed(sf::Keyboard::Key::W)) moveVec.y -= 1;
        if (sf::Keyboard::isKeyPressed(sf::Keyboard::Key::S)) moveVec.y += 1;
        if (sf::Keyboard::isKeyPressed(sf::Keyboard::Key::A)) moveVec.x -= 1;
        if (sf::Keyboard::isKeyPressed(sf::Keyboard::Key::D)) moveVec.x += 1;

        if (sf::Keyboard::isKeyPressed(sf::Keyboard::Key::Up)) aimVec.y -= 1;
        if (sf::Keyboard::isKeyPressed(sf::Keyboard::Key::Down)) aimVec.y += 1;
        if (sf::Keyboard::isKeyPressed(sf::Keyboard::Key::Left)) aimVec.x -= 1;
        if (sf::Keyboard::isKeyPressed(sf::Keyboard::Key::Right)) aimVec.x += 1;

        if (sf::Keyboard::isKeyPressed(sf::Keyboard::Key::Space)) {
            fireTriggered = true;
            struggleButton = true;
        }

        // --- 2. Controller Input ---
        if (sf::Joystick::isConnected(0)) {
            float joyX = sf::Joystick::getAxisPosition(0, sf::Joystick::Axis::X);
            float joyY = sf::Joystick::getAxisPosition(0, sf::Joystick::Axis::Y);
            if (std::abs(joyX) > 15.f) moveVec.x += joyX / 100.f;
            if (std::abs(joyY) > 15.f) moveVec.y += joyY / 100.f;

            float aimX = sf::Joystick::getAxisPosition(0, sf::Joystick::Axis::Z);
            float aimY = sf::Joystick::getAxisPosition(0, sf::Joystick::Axis::R);

            if (std::abs(aimX) > 20.f || std::abs(aimY) > 20.f) {
                aimVec.x = aimX;
                aimVec.y = aimY;
            }

            float rightTrigger = sf::Joystick::getAxisPosition(0, sf::Joystick::Axis::V);
            if (rightTrigger > 50.0f) {
                fireTriggered = true;
                struggleButton = true;
            }
        }

        // --- Logic ---
        if (state != GameState::STRUGGLING && state != GameState::RETRACTING) {
            if (getVecLength(aimVec) > 0.1f) {
                float rawAngle = std::atan2(aimVec.y, aimVec.x) * 180.0f / PI;
                aimAngle = std::round(rawAngle / 45.0f) * 45.0f;
            }

            if (fireTriggered && state == GameState::SWIMMING) {
                if (canTap) {
                    state = GameState::FIRING;
                    harpoonPos = pos;
                    float rad = aimAngle * PI / 180.0f;
                    harpoonVel = { std::cos(rad) * 1000.0f, std::sin(rad) * 1000.0f };
                    
                    if (shootSound) {
                        float pitch = (static_cast<float>(rand()) / RAND_MAX * 0.2f) + 0.9f; 
                        shootSound->setPitch(pitch);
                        shootSound->play();
                    }
                    canTap = false;
                }
            } else if (!fireTriggered) {
                canTap = true;
            }
        }

        if (state == GameState::STRUGGLING) {
            // Freeze movement while struggling
            moveVec = {0.0f, 0.0f};

            struggleProgress -= 55.0f * dt;
            
            if (struggleButton) {
                if (canTap) {
                    struggleProgress += 32.0f; 
                    canTap = false; 
                }
            } else {
                canTap = true; 
            }

            // Target lost
            if (struggleProgress <= 0.0f) {
                state = GameState::RETRACTING;
                target.isCaught = false;
                explosionSoundPlayed = false; 
            }
            
            // Target CAUGHT (Bar Full)
            if (struggleProgress >= 100.0f) {
                
                // 1. Play Sound FIRST
                if (!explosionSoundPlayed) {
                     if (ps.explosionSound) {
                         float pitch = (static_cast<float>(rand()) / RAND_MAX * 0.4f) + 0.8f;
                         ps.explosionSound->setPitch(pitch);
                         ps.explosionSound->play();
                     }
                     explosionSoundPlayed = true;
                     explosionTimer = 0.001f; // 1ms delay
                }

                // 2. Count down
                explosionTimer -= dt;

                // 3. Trigger Visuals after delay
                if (explosionTimer <= 0.0f) {
                    ps.emit(target.pos); 
                    target.reset(); 
                    target.isCaught = false; 
                    state = GameState::RETRACTING;
                    struggleProgress = 0.0f;
                    explosionSoundPlayed = false; 
                }
            }
            
            if (target.isCaught) {
                harpoonPos = target.pos;
            }
        }

        updatePhysics(moveVec, dt, target, ps);
    }

    void updatePhysics(sf::Vector2f moveVec, float dt, Target& target, ParticleSystem& ps) {
        float len = getVecLength(moveVec);
        if (len > 0) {
            if (len > 1.0f) moveVec /= len; 
            pos += moveVec * 280.0f * dt;
        }
        
        // Bounds checking
        pos.x = std::max(radius, std::min((float)WIDTH - radius, pos.x));
        pos.y = std::max(radius, std::min((float)HEIGHT - radius, pos.y));

        // --- PLAYER DEATH CHECK ---
        float distToEnemy = getVecLength(pos - target.pos);
        if (distToEnemy < (radius + target.radius)) {
            // 1. Visual Explosion
            ps.emit(pos);
            
            // 2. Play Sound
            if (ps.explosionSound) {
                ps.explosionSound->setPitch(1.0f);
                ps.explosionSound->play();
            }
            
            // 3. Set Death State
            isDead = true;
            deathTimer = 3.0f; 
            
            // 4. Reset Game State (But KEEP player position)
            state = GameState::SWIMMING;
            harpoonPos = pos; 
            harpoonVel = {0.0f, 0.0f};
            struggleProgress = 0.0f;
            explosionSoundPlayed = false;
            
            // 5. Move Enemy Away (so we don't die instantly upon respawn)
            target.reset(); 
            target.isCaught = false;
        }
        // --------------------------

        if (state == GameState::FIRING) {
            harpoonPos += harpoonVel * dt;

            float dist = getVecLength(harpoonPos - target.pos);
            if (dist < (radius + target.radius)) {
                state = GameState::STRUGGLING;
                target.isCaught = true;
                struggleProgress = 30.0f;
            }

            // Max distance 250.0f
            float distFromPlayer = getVecLength(harpoonPos - pos);
            if (distFromPlayer > 250.0f) state = GameState::RETRACTING;
        }

        if (state == GameState::RETRACTING) {
            sf::Vector2f dir = pos - harpoonPos;
            float dist = getVecLength(dir);
            float speed = target.isCaught ? 1400.0f : 900.0f;

            if (dist < 15.0f) {
                state = GameState::SWIMMING;
                if (target.isCaught) {
                    ps.emit(pos); 
                    target.reset();
                }
            } else {
                harpoonPos += (dir / dist) * speed * dt;
            }

            if (target.isCaught) {
                target.pos = harpoonPos;
            }
        }
    }

    void draw(sf::RenderWindow& window) {
        // Draw harpoon if not dead and not swimming
        if (state != GameState::SWIMMING && !isDead) {
            sf::Vertex line[] = {
                sf::Vertex{pos, sf::Color::Yellow},
                sf::Vertex{harpoonPos, sf::Color::Yellow}
            };
            window.draw(line, 2, sf::PrimitiveType::Lines);

            sf::RectangleShape head({20.f, 6.f}); 
            head.setOrigin({0.f, 3.f});            
            head.setPosition(harpoonPos);
            head.setFillColor(sf::Color::Yellow);

            float rot = 0.f;
            if (state == GameState::RETRACTING) {
                rot = std::atan2(pos.y - harpoonPos.y, pos.x - harpoonPos.x) * 180.0f / PI;
            } else {
                rot = aimAngle;
            }
            head.setRotation(sf::degrees(rot)); 
            window.draw(head);
        }

        // Draw Player Body (Only if ALIVE)
        if (!isDead) {
            sf::CircleShape body(radius);
            body.setOrigin({radius, radius}); 
            body.setPosition(pos);
            body.setFillColor(sf::Color(75, 0, 130)); // Indigo
            window.draw(body);
        }

        // Draw Struggle Bar (Only if ALIVE)
        if (state == GameState::STRUGGLING && !isDead) {
            sf::RectangleShape bg({100.f, 12.f}); 
            bg.setPosition({pos.x - 50, pos.y - 45}); 
            bg.setFillColor(sf::Color(50, 50, 50));
            window.draw(bg);

            float fillWidth = std::max(0.0f, struggleProgress);
            sf::RectangleShape fill({fillWidth, 12.f}); 
            fill.setPosition({pos.x - 50, pos.y - 45}); 
            fill.setFillColor(sf::Color::Cyan);
            window.draw(fill);
        }
    }
};

// --- Main Loop ---
int main() {
    std::srand(static_cast<unsigned>(std::time(nullptr))); 

    sf::RenderWindow window(sf::VideoMode({WIDTH, HEIGHT}), "Harpoon Game C++"); 
    window.setFramerateLimit(60);

    Player player;
    Target target;
    ParticleSystem ps;

    // --- SOUND LOADING ---
    sf::SoundBuffer boomBuffer;
    sf::SoundBuffer shootBuffer;
    bool boomLoaded = false;
    bool shootLoaded = false;
    
    // 1. Load BOOM (Boom3.wav)
    if (boomBuffer.loadFromFile("/Users/macbook/Downloads/Boom3.wav")) {
        boomLoaded = true;
        std::cout << "Loaded Boom3.wav from Downloads" << std::endl;
    } else if (boomBuffer.loadFromFile("Boom3.wav")) {
        boomLoaded = true;
        std::cout << "Loaded Boom3.wav from local directory" << std::endl;
    } else {
        std::cout << "Could not find Boom3.wav!" << std::endl;
    }

    // 2. Load SHOOT (Shoot11.wav)
    if (shootBuffer.loadFromFile("/Users/macbook/Downloads/Shoot11.wav")) {
        shootLoaded = true;
        std::cout << "Loaded Shoot11.wav from Downloads" << std::endl;
    } else if (shootBuffer.loadFromFile("Shoot11.wav")) {
        shootLoaded = true;
        std::cout << "Loaded Shoot11.wav from local directory" << std::endl;
    } else {
        std::cout << "Could not find Shoot11.wav!" << std::endl;
    }

    std::optional<sf::Sound> explosionSound;
    if (boomLoaded) {
        explosionSound.emplace(boomBuffer); 
        ps.explosionSound = &explosionSound.value();
    }

    std::optional<sf::Sound> shootSound;
    if (shootLoaded) {
        shootSound.emplace(shootBuffer); 
        player.shootSound = &shootSound.value();
    }

    sf::Clock clock;

    while (window.isOpen()) {
        while (const std::optional event = window.pollEvent()) {
             if (event->is<sf::Event::Closed>()) {
                 window.close();
             }
        }

        float dt = clock.restart().asSeconds();
        if (dt > 0.1f) dt = 0.1f; 

        target.update(dt);
        player.handleInput(dt, target, ps);
        ps.update(dt);

        window.clear(sf::Color::Black); 
        
        target.draw(window);
        player.draw(window);
        ps.draw(window);

        window.display();
    }

    return 0;
}