#include <SFML/Graphics.hpp>
#include <vector>
#include <optional> // SFML 3 uses std::optional for events + intersections

struct RoomExit {
    int left = -1, right = -1, up = -1, down = -1;
};

struct Room {
    int id = 0;
    sf::Color bg = sf::Color::Black;
    std::vector<sf::FloatRect> walls;
    RoomExit exits;
};

struct Player {
    sf::Vector2f pos {120.f, 80.f};
    sf::Vector2f size {10.f, 10.f};
    float speed = 120.f; // pixels/sec
    int facing = 1; // 1=right, -1=left, 2=down, -2=up

    sf::FloatRect rect() const { return sf::FloatRect(pos, size); }
};

struct World {
    std::vector<Room> rooms;
    int currentRoom = 0;

    Room& room() { return rooms[currentRoom]; }
};

static bool hitsWall(const sf::FloatRect& rect, const Room& room) {
    for (const auto& w : room.walls) {
        if (rect.findIntersection(w).has_value()) return true;
    }
    return false;
}

static void moveWithCollision(Player& p, const Room& room, sf::Vector2f delta) {
    // X axis
    sf::Vector2f next = p.pos;
    next.x += delta.x;
    sf::FloatRect rx(next, p.size);
    if (!hitsWall(rx, room)) p.pos.x = next.x;

    // Y axis
    next = p.pos;
    next.y += delta.y;
    sf::FloatRect ry(next, p.size);
    if (!hitsWall(ry, room)) p.pos.y = next.y;
}

static void handleRoomTransition(Player& p, World& w, const sf::Vector2u& win) {
    auto& room = w.room();

    if (p.pos.x + p.size.x < 0 && room.exits.left != -1) {
        w.currentRoom = room.exits.left;
        p.pos.x = static_cast<float>(win.x) - 2.f;
    }
    if (p.pos.x > static_cast<float>(win.x) && room.exits.right != -1) {
        w.currentRoom = room.exits.right;
        p.pos.x = -p.size.x + 2.f;
    }
    if (p.pos.y + p.size.y < 0 && room.exits.up != -1) {
        w.currentRoom = room.exits.up;
        p.pos.y = static_cast<float>(win.y) - 2.f;
    }
    if (p.pos.y > static_cast<float>(win.y) && room.exits.down != -1) {
        w.currentRoom = room.exits.down;
        p.pos.y = -p.size.y + 2.f;
    }
}

// Adds boundary walls around the room, with a doorway gap only if an exit exists.
static void addBorderWallsWithDoors(Room& r, sf::Vector2u win, float thick = 8.f, float door = 48.f) {
    const float W = static_cast<float>(win.x);
    const float H = static_cast<float>(win.y);

    const float doorX = (W - door) * 0.5f;
    const float doorY = (H - door) * 0.5f;

    auto add = [&](sf::Vector2f pos, sf::Vector2f size) {
        r.walls.push_back(sf::FloatRect(pos, size));
    };

    // TOP
    if (r.exits.up == -1) {
        add({0.f, 0.f}, {W, thick});
    } else {
        add({0.f, 0.f}, {doorX, thick});
        add({doorX + door, 0.f}, {W - (doorX + door), thick});
    }

    // BOTTOM
    if (r.exits.down == -1) {
        add({0.f, H - thick}, {W, thick});
    } else {
        add({0.f, H - thick}, {doorX, thick});
        add({doorX + door, H - thick}, {W - (doorX + door), thick});
    }

    // LEFT
    if (r.exits.left == -1) {
        add({0.f, 0.f}, {thick, H});
    } else {
        add({0.f, 0.f}, {thick, doorY});
        add({0.f, doorY + door}, {thick, H - (doorY + door)});
    }

    // RIGHT
    if (r.exits.right == -1) {
        add({W - thick, 0.f}, {thick, H});
    } else {
        add({W - thick, 0.f}, {thick, doorY});
        add({W - thick, doorY + door}, {thick, H - (doorY + door)});
    }
}

int main() {
    sf::RenderWindow window(sf::VideoMode({320u, 210u}), "Adventure Clone");
    window.setFramerateLimit(60);

    World world;
    world.rooms.reserve(9);

    auto makeRoom = [](int id, sf::Color bg) {
        Room r;
        r.id = id;
        r.bg = bg;
        return r;
    };

    for (int i = 0; i < 9; i++) {
        sf::Color bg =
            (i < 3) ? sf::Color(30, 30, 60) :
            (i < 6) ? sf::Color(20, 60, 20) :
                      sf::Color(60, 30, 30);

        world.rooms.push_back(makeRoom(i, bg));
    }

    auto idx = [](int x, int y) { return y * 3 + x; };
    const auto winSize = window.getSize();

    // exits + border walls
    for (int y = 0; y < 3; y++) {
        for (int x = 0; x < 3; x++) {
            int id = idx(x, y);
            auto& r = world.rooms[id];

            r.exits.left  = (x > 0) ? idx(x - 1, y) : -1;
            r.exits.right = (x < 2) ? idx(x + 1, y) : -1;
            r.exits.up    = (y > 0) ? idx(x, y - 1) : -1;
            r.exits.down  = (y < 2) ? idx(x, y + 1) : -1;

            addBorderWallsWithDoors(r, winSize);
        }
    }

    // internal walls
    for (int y = 0; y < 3; y++) {
        for (int x = 0; x < 3; x++) {
            int id = idx(x, y);
            auto& r = world.rooms[id];

            if (id == 0) {
                r.walls.push_back(sf::FloatRect({40.f, 40.f}, {240.f, 10.f}));
                r.walls.push_back(sf::FloatRect({40.f, 40.f}, {10.f, 130.f}));
            } else if (id == 4) {
                // CENTER ROOM FIX:
                // Instead of a fully closed box, we make a small opening at the bottom.
                // Top wall
                r.walls.push_back(sf::FloatRect({70.f, 60.f},  {180.f, 10.f}));

                // Bottom wall split into two parts (gap in the middle)
                // Box bottom y = 140, thickness = 10
                // Gap centered; make it wide enough for player (player is 10px wide)
                const float boxLeft = 70.f;
                const float boxRight = 70.f + 180.f;
                const float bottomY = 140.f;
                const float thick = 10.f;

                const float gapW = 26.f; // opening width (player is 10, so this is comfy)
                const float gapX = (boxLeft + boxRight - gapW) * 0.5f;

                // left piece of bottom wall
                r.walls.push_back(sf::FloatRect({boxLeft, bottomY}, {gapX - boxLeft, thick}));
                // right piece of bottom wall
                r.walls.push_back(sf::FloatRect({gapX + gapW, bottomY}, {boxRight - (gapX + gapW), thick}));

                // Side walls
                r.walls.push_back(sf::FloatRect({70.f, 60.f},  {10.f, 90.f}));
                r.walls.push_back(sf::FloatRect({240.f, 60.f}, {10.f, 90.f}));

                // Pillar
                r.walls.push_back(sf::FloatRect({150.f, 95.f}, {20.f, 20.f}));
            } else if (id == 8) {
                r.walls.push_back(sf::FloatRect({30.f, 100.f}, {260.f, 10.f}));
            }
        }
    }

    world.currentRoom = 4;

    Player player;
    player.pos = {155.f, 105.f};

    sf::Clock clock;
    while (window.isOpen()) {

        while (const std::optional<sf::Event> event = window.pollEvent()) {
            if (event->is<sf::Event::Closed>()) window.close();
        }

        float dt = clock.restart().asSeconds();

        sf::Vector2f move(0.f, 0.f);
        if (sf::Keyboard::isKeyPressed(sf::Keyboard::Key::Left))  { move.x -= 1.f; }
        if (sf::Keyboard::isKeyPressed(sf::Keyboard::Key::Right)) { move.x += 1.f; }
        if (sf::Keyboard::isKeyPressed(sf::Keyboard::Key::Up))    { move.y -= 1.f; }
        if (sf::Keyboard::isKeyPressed(sf::Keyboard::Key::Down))  { move.y += 1.f; }

        if (move.x != 0 && move.y != 0) move *= 0.7071f;

        moveWithCollision(player, world.room(), move * player.speed * dt);
        handleRoomTransition(player, world, window.getSize());

        window.clear(world.room().bg);

        for (const auto& w : world.room().walls) {
            sf::RectangleShape wall(w.size);
            wall.setPosition(w.position);
            wall.setFillColor(sf::Color(200, 200, 200));
            window.draw(wall);
        }

        sf::RectangleShape pr(player.size);
        pr.setPosition(player.pos);
        pr.setFillColor(sf::Color::Yellow);
        window.draw(pr);

        // minimap
        {
            const int gridW = 3, gridH = 3;
            const float cell = 10.f;
            sf::Vector2f origin(5.f, 5.f);

            for (int y = 0; y < gridH; y++) {
                for (int x = 0; x < gridW; x++) {
                    int id = y * gridW + x;
                    sf::RectangleShape c({cell, cell});
                    c.setPosition({origin.x + x * (cell + 2.f), origin.y + y * (cell + 2.f)});
                    c.setFillColor(id == world.currentRoom ? sf::Color::Yellow : sf::Color(120, 120, 120));
                    window.draw(c);
                }
            }
        }

        window.display();
    }
}
