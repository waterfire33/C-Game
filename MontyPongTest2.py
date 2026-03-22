import turtle
import time
import random
import math
import os
import serial
import serial.tools.list_ports

# Try to import pygame for audio, but make it optional
try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    print("⚠️ pygame not available - running without sound")

# --- CONFIGURATION & CONSTANTS ---
SCREEN_WIDTH = 1200
SCREEN_HEIGHT = 800
WINNING_SCORE = 22

# GAMEPLAY BASE VALUES
BASE_PADDLE_SPEED = 950      # Snappier paddle movement
BASE_BALL_START_SPEED = 4.0  # Starts slower (was 8.0)
BASE_BALL_SPEED_CAP = 18.0   # Maximum speed limit

# Power-up Colors
COLOR_SIZE = "green"
COLOR_GHOST = "orange"
COLOR_FREEZE = "light blue"
COLOR_SPLIT = "red"

class ArduinoController:
    """Handles communication with Arduino for paddle control."""
    def __init__(self, port=None, baudrate=9600):
        self.serial = None
        self.last_val = 512 # Start in the middle (0-1023)
        
        # --- FIX: HARDCODED PORT FOR STABILITY ---
        # We explicitly set the port here to match your current Arduino connection.
        if port is None:
            port = "/dev/cu.usbserial-1130"

        try:
            # If the hardcoded port is not found, we try to auto-detect as a backup
            found_ports = [p.device for p in serial.tools.list_ports.comports()]
            if port not in found_ports:
                print(f"⚠️ Port {port} not found. Attempting auto-detect...")
                port = None # Reset to trigger auto-detect logic below

            if port is None:
                # Auto-detect logic
                ports = list(serial.tools.list_ports.comports())
                for p in ports:
                    # Look for likely candidates (usbmodem on Mac, COM on Windows, etc)
                    if "usbmodem" in p.device or "usbserial" in p.device or "COM" in p.device:
                        port = p.device
                        break
            
            if port:
                self.serial = serial.Serial(port, baudrate, timeout=0.01)
                # Wait a moment for connection to stabilize
                time.sleep(1.5)
                # Flush startup junk
                self.serial.reset_input_buffer()
                print(f"✅ Arduino connected on {port}")
            else:
                print("⚠️ No Arduino found (connect it to control Player 1)")

        except Exception as e:
            print(f"❌ Arduino connection failed: {e}")
            self.serial = None

    def read(self):
        """Reads the latest value from the Serial port. Returns last known value if connected."""
        if not self.serial or not self.serial.is_open:
            return None
            
        try:
            if self.serial.in_waiting > 0:
                data = self.serial.read(self.serial.in_waiting).decode('utf-8', errors='ignore')
                lines = data.strip().split('\n')
                
                # Update last_val only if we have fresh valid data
                for line in reversed(lines):
                    line = line.strip()
                    if line.isdigit():
                        self.last_val = int(line)
                        break
            
            # ALWAYS return the last known value so the paddle doesn't freeze
            return self.last_val
            
        except Exception:
            return self.last_val

class SoundManager:
    """Handles audio with absolute paths to fix loading errors on Mac."""
    def __init__(self):
        self.sounds_on = True
        self.sounds = {}
        self.volume = 1.0
        
        if not PYGAME_AVAILABLE:
            print("🔇 Audio disabled - pygame not available")
            self.sounds_on = False
            return
        
        # 1. FIND THE SCRIPT'S FOLDER
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        
        try:
            # Specific settings for Mac/CoreAudio to prevent latency
            pygame.mixer.pre_init(44100, -16, 2, 512)
            pygame.mixer.init()
            
            # 2. LOAD SOUNDS
            sound_files = ["bounce.ogg", "wall.ogg", "score.ogg"]
            for filename in sound_files:
                name = filename.split(".")[0]
                full_path = os.path.join(self.script_dir, filename)
                
                if os.path.exists(full_path):
                    self.sounds[name] = pygame.mixer.Sound(full_path)
                    print(f"✅ Loaded Sound: {filename}")
                else:
                    print(f"❌ SOUND MISSING: Could not find '{filename}' at {full_path}")
                    self.sounds[name] = None

            self.set_volume(self.volume)
                    
        except Exception as e:
            print(f"CRITICAL AUDIO ERROR: {e}")
            self.sounds_on = False

    def play(self, name):
        if self.sounds_on and self.sounds.get(name):
            try:
                self.sounds[name].play()
            except:
                pass 

    def set_volume(self, volume):
        self.volume = max(0.0, min(1.0, volume))
        for sound in self.sounds.values():
            if sound:
                sound.set_volume(self.volume)

    def toggle_mute(self):
        self.sounds_on = not self.sounds_on
        print(f"Sound {'ON' if self.sounds_on else 'OFF'}")


class GameObject(turtle.Turtle):
    """Base class for all game entities."""
    def __init__(self, shape, color, x, y):
        super().__init__()
        self.speed(0)
        self.shape(shape)
        self.color(color)
        self.penup()
        self.goto(x, y)


class Paddle(GameObject):
    def __init__(self, x, y):
        super().__init__("square", "white", x, y)
        self.shapesize(stretch_wid=5, stretch_len=1)
        self.frozen_until = 0

    def move(self, direction, dt, height_limit, speed):
        # Prevent movement if frozen
        if time.time() < self.frozen_until:
            self.color("light blue")
            return
        else:
            self.color("white")

        new_y = self.ycor() + (direction * speed * dt)
        
        # Boundary check to keep paddle on screen
        if -height_limit < new_y < height_limit:
            self.sety(new_y)


class Ball(GameObject):
    def __init__(self, start_speed, speed_cap):
        super().__init__("circle", "white", 0, 0)
        self.dx = 0
        self.dy = 0
        self.start_speed = start_speed
        self.speed_cap = speed_cap

    def serve(self):
        self.goto(0, 0)
        self.color("white")
        
        # Start Speed = 8.0 (Random Left or Right)
        direction_x = random.choice([1, -1])
        self.dx = direction_x * self.start_speed 
        self.dy = random.uniform(-3.0, 3.0)


class Star(GameObject):
    def __init__(self, w_half, h_half):
        super().__init__("circle", "white", 0, 0)
        self.reset_pos(w_half, h_half)
        size = random.uniform(0.05, 0.2)
        self.shapesize(size, size)
        self.speed_val = size * 300 

    def reset_pos(self, w_half, h_half):
        x = random.randint(-int(w_half), int(w_half))
        y = random.randint(-int(h_half), int(h_half))
        self.goto(x, y)

    def update(self, dt, w_half, h_half):
        self.setx(self.xcor() - (self.speed_val * dt))
        if self.xcor() < -w_half:
            self.goto(w_half, random.randint(-int(h_half), int(h_half)))


class Game:
    def __init__(self):
        # 1. Setup Screen
        self.win = turtle.Screen()
        self.win.title("Starfield Pong Pro")
        self.win.bgcolor("black")
        self.root = self.win.getcanvas().winfo_toplevel()
        self.root.attributes("-fullscreen", True)
        self.win.tracer(0)
        
        # Dimensions
        self.w_half = self.win.window_width() / 2
        self.h_half = self.win.window_height() / 2
        
        # 2. Managers
        self.sound = SoundManager()
        self.arduino = ArduinoController()
        
        # 3. Game Objects
        self.paddle_a = Paddle(-(self.w_half - 50), 0)
        self.paddle_b = Paddle(self.w_half - 50, 0)
        
        # Initial ball placeholder (cleared on start)
        self.balls = []
        
        # Starfield
        self.stars = [Star(self.w_half, self.h_half) for _ in range(80)]
        
        # Powerup Setup
        self.powerup = GameObject("circle", "green", 0, 0)
        self.powerup.hideturtle()
        self.powerup.shapesize(4, 4)
        
        # UI Setup
        self.pen = GameObject("square", "white", 0, 0)
        self.pen.hideturtle()
        self.menu_title_pen = GameObject("square", "white", 0, 0)
        self.menu_title_pen.hideturtle()
        self.menu_hint_pen = GameObject("square", "white", 0, 0)
        self.menu_hint_pen.hideturtle()
        self.settings_pen = GameObject("square", "white", 0, 0)
        self.settings_pen.hideturtle()
        self.score_pen_a = GameObject("square", "white", -150, self.h_half - 150)
        self.score_pen_a.hideturtle()
        self.score_pen_b = GameObject("square", "white", 150, self.h_half - 150)
        self.score_pen_b.hideturtle()

        # 4. Game State
        self.score_a = 0
        self.score_b = 0
        self.active = False
        self.menu_state = "main"
        self.ghost_mode = False
        self.ghost_end_time = 0
        self.last_hitter = None
        
        self.powerup_active = False
        self.powerup_type = ""
        self.powerup_cycle = ["size", "ghost", "freeze", "split"]
        self.powerup_idx = 0
        self.powerup_cooldown = 0
        self.speed_boost_count = 0

        # Settings
        self.key_bindings = {
            "p1_up": "q",
            "p1_down": "z",
            "p2_up": "i",
            "p2_down": "n"
        }
        self.action_state = {"p1_up": False, "p1_down": False, "p2_up": False, "p2_down": False}
        self.bound_keys = set()
        self.volume_percent = 100
        self.ball_speed_percent = 100
        self.movement_speed_percent = 100
        self.update_speed_settings()

        if not self.balls:
            self.balls = [Ball(self.ball_start_speed, self.ball_speed_cap)]

        # Input State
        self.keys = {}
        self.ui_elements = []

        self.setup_inputs()
        self.show_main_menu()

    def update_speed_settings(self):
        self.ball_speed_multiplier = max(0.1, self.ball_speed_percent / 100.0)
        self.movement_speed_multiplier = max(0.1, self.movement_speed_percent / 100.0)
        self.ball_start_speed = BASE_BALL_START_SPEED * self.ball_speed_multiplier
        self.ball_speed_cap = BASE_BALL_SPEED_CAP * self.ball_speed_multiplier

        for ball in self.balls:
            ball.start_speed = self.ball_start_speed
            ball.speed_cap = self.ball_speed_cap
            if abs(ball.dx) > ball.speed_cap:
                ball.dx = ball.speed_cap if ball.dx > 0 else -ball.speed_cap

    def update_score_display(self):
        self.score_pen_a.clear()
        self.score_pen_b.clear()
        self.score_pen_a.write(self.score_a, align="center", font=("Courier", 80, "bold"))
        self.score_pen_b.write(self.score_b, align="center", font=("Courier", 80, "bold"))

    def clear_ui(self):
        # Clear all UI text turtles
        self.pen.clear()
        self.menu_title_pen.clear()
        self.menu_hint_pen.clear()
        self.settings_pen.clear()
        self.score_pen_a.clear()
        self.score_pen_b.clear()
        
        # Hide and clear all button elements
        for t in getattr(self, "ui_elements", []):
            try:
                t.clear()
                t.hideturtle()
            except:
                pass
        self.ui_elements = []

    def set_game_objects_visible(self, visible):
        if visible:
            self.paddle_a.showturtle()
            self.paddle_b.showturtle()
            for star in self.stars:
                star.showturtle()
            if self.powerup_active:
                self.powerup.showturtle()
            else:
                self.powerup.hideturtle()
            for ball in self.balls:
                ball.showturtle()
        else:
            self.paddle_a.hideturtle()
            self.paddle_b.hideturtle()
            for star in self.stars:
                star.hideturtle()
            self.powerup.hideturtle()
            for ball in self.balls:
                ball.hideturtle()

    def create_button(self, label, x, y, width, height, callback):
        button = GameObject("square", "#111111", x, y)
        button.shapesize(stretch_wid=height / 20, stretch_len=width / 20)
        button.color("#222222")
        button.penup()
        button.goto(x, y)

        text = GameObject("square", "white", x, y - 10)
        text.hideturtle()
        text.penup()
        text.goto(x, y - 10)
        text.write(label, align="center", font=("Courier", 20, "bold"))

        def on_click(px, py):
            if (x - width / 2) <= px <= (x + width / 2) and (y - height / 2) <= py <= (y + height / 2):
                callback()

        button.onclick(on_click)

        self.ui_elements.append(button)
        self.ui_elements.append(text)

    def show_main_menu(self):
        self.menu_state = "main"
        self.active = False
        self.win.getcanvas().config(cursor="arrow")
        self.clear_ui()
        self.set_game_objects_visible(False)
        
        self.menu_title_pen.goto(0, 200)
        self.menu_title_pen.write("STARFIELD PONG PRO", align="center", font=("Courier", 36, "bold"))

        self.create_button("PLAY GAME", 0, 40, 300, 70, self.start_game)
        self.create_button("SETTINGS", 0, -60, 300, 70, self.show_settings_menu)

        self.menu_hint_pen.goto(0, -180)
        self.menu_hint_pen.write("Press SPACE to start", align="center", font=("Courier", 16, "normal"))

    def show_settings_menu(self):
        self.menu_state = "settings"
        self.active = False
        self.win.getcanvas().config(cursor="arrow")
        self.clear_ui()
        self.set_game_objects_visible(False)
        
        self.menu_title_pen.goto(0, 260)
        self.menu_title_pen.write("SETTINGS", align="center", font=("Courier", 32, "bold"))

        self.draw_settings_text()

        self.create_button("EDIT P1 KEYBINDS", 0, 120, 360, 60, self.edit_p1_keybinds)
        self.create_button("EDIT P2 KEYBINDS", 0, 40, 360, 60, self.edit_p2_keybinds)
        self.create_button("VOLUME", 0, -40, 260, 60, self.edit_volume)
        self.create_button("BALL SPEED %", 0, -120, 300, 60, self.edit_ball_speed)
        self.create_button("MOVE SPEED %", 0, -200, 300, 60, self.edit_move_speed)
        self.create_button("BACK", 0, -300, 200, 60, self.show_main_menu)

    def draw_settings_text(self):
        p1 = f"P1: {self.key_bindings['p1_up'].upper()} / {self.key_bindings['p1_down'].upper()}"
        p2 = f"P2: {self.key_bindings['p2_up'].upper()} / {self.key_bindings['p2_down'].upper()}"
        vol = f"Volume: {self.volume_percent}%"
        ball = f"Ball Speed: {self.ball_speed_percent}%"
        move = f"Move Speed: {self.movement_speed_percent}%"
        
        # Create a single turtle for all settings text
        text_display = GameObject("square", "white", 0, 190)
        text_display.hideturtle()
        text_display.write(p1, align="center", font=("Courier", 16, "normal"))
        
        text_display.goto(0, 165)
        text_display.write(p2, align="center", font=("Courier", 16, "normal"))
        
        text_display.goto(0, 140)
        text_display.write(vol, align="center", font=("Courier", 16, "normal"))
        
        text_display.goto(0, 115)
        text_display.write(ball, align="center", font=("Courier", 16, "normal"))
        
        text_display.goto(0, 90)
        text_display.write(move, align="center", font=("Courier", 16, "normal"))
        
        self.ui_elements.append(text_display)

    def normalize_key(self, key):
        if not key:
            return None
        key = key.strip()
        if not key:
            return None
        low = key.lower()
        if low == "space":
            return "space"
        if low == "up":
            return "Up"
        if low == "down":
            return "Down"
        if low == "left":
            return "Left"
        if low == "right":
            return "Right"
        if len(key) == 1:
            return low
        return key

    def edit_p1_keybinds(self):
        up = self.win.textinput("Player 1 Up", f"Enter key for P1 Up (current: {self.key_bindings['p1_up']})")
        down = self.win.textinput("Player 1 Down", f"Enter key for P1 Down (current: {self.key_bindings['p1_down']})")
        up = self.normalize_key(up)
        down = self.normalize_key(down)
        if up:
            self.key_bindings["p1_up"] = up
        if down:
            self.key_bindings["p1_down"] = down
        self.setup_inputs()
        self.show_settings_menu()

    def edit_p2_keybinds(self):
        up = self.win.textinput("Player 2 Up", f"Enter key for P2 Up (current: {self.key_bindings['p2_up']})")
        down = self.win.textinput("Player 2 Down", f"Enter key for P2 Down (current: {self.key_bindings['p2_down']})")
        up = self.normalize_key(up)
        down = self.normalize_key(down)
        if up:
            self.key_bindings["p2_up"] = up
        if down:
            self.key_bindings["p2_down"] = down
        self.setup_inputs()
        self.show_settings_menu()

    def edit_volume(self):
        val = self.win.textinput("Volume", "Set volume (0-100):")
        if val is not None:
            try:
                v = max(0, min(100, int(val)))
                self.volume_percent = v
                self.sound.set_volume(v / 100.0)
            except:
                pass
        self.show_settings_menu()

    def edit_ball_speed(self):
        val = self.win.textinput("Ball Speed", "Set ball speed % (50-200):")
        if val is not None:
            try:
                v = max(50, min(200, int(val)))
                self.ball_speed_percent = v
                self.update_speed_settings()
            except:
                pass
        self.show_settings_menu()

    def edit_move_speed(self):
        val = self.win.textinput("Move Speed", "Set movement speed % (50-200):")
        if val is not None:
            try:
                v = max(50, min(200, int(val)))
                self.movement_speed_percent = v
                self.update_speed_settings()
            except:
                pass
        self.show_settings_menu()

    def start_game(self):
        if not self.active and self.menu_state != "settings":
            self.score_a = 0
            self.score_b = 0
            self.active = True
            self.menu_state = "playing"
            self.clear_ui()
            self.set_game_objects_visible(True)
            
            # --- CLEAR OLD OBJECTS ---
            for b in self.balls:
                b.hideturtle()
            self.balls.clear()
            
            # Create fresh ball
            self.balls = [Ball(self.ball_start_speed, self.ball_speed_cap)]
            self.balls[0].serve()
            
            self.pen.clear()
            self.update_score_display()
            self.win.getcanvas().config(cursor="none")

    def handle_action(self, action, state):
        self.action_state[action] = state

    def setup_inputs(self):
        self.win.listen()
        # Clear old bindings
        for k in self.bound_keys:
            self.win.onkeypress(None, k)
            self.win.onkeyrelease(None, k)
        self.bound_keys.clear()

        # Bindings for Smooth Movement
        for action, key in self.key_bindings.items():
            self.win.onkeypress(lambda a=action: self.handle_action(a, True), key)
            self.win.onkeyrelease(lambda a=action: self.handle_action(a, False), key)
            self.bound_keys.add(key)

        self.win.onkeypress(self.start_game, "space")
        self.win.onkeypress(self.sound.toggle_mute, "m")
        self.win.onkeypress(lambda: self.root.attributes("-fullscreen", False), "Escape")

    def physics_step(self, dt):
        limit = self.h_half - 50
        paddle_speed = BASE_PADDLE_SPEED * self.movement_speed_multiplier
        
        # Arduino Control for Player 1
        # Now returns the last valid value (or None if never connected)
        arduino_val = self.arduino.read()
        
        if arduino_val is not None:
            # Map 0-1023 to Screen Y coordinates
            # Y range is roughly -limit to +limit
            target_y = ((arduino_val / 1023.0) * (limit * 2)) - limit
            
            # Optional: Invert if pot feels backwards
            # target_y = -target_y
            
            self.paddle_a.sety(target_y)
            
            # Keep within bounds
            if self.paddle_a.ycor() > limit: self.paddle_a.sety(limit)
            if self.paddle_a.ycor() < -limit: self.paddle_a.sety(-limit)
        
        # Keyboard Move Paddles (Player 1 can also use keys if they want)
        if self.action_state["p1_up"]: self.paddle_a.move(1, dt, limit, paddle_speed)
        if self.action_state["p1_down"]: self.paddle_a.move(-1, dt, limit, paddle_speed)
        
        # Player 2 controls
        if self.action_state["p2_up"]: self.paddle_b.move(1, dt, limit, paddle_speed)
        if self.action_state["p2_down"]: self.paddle_b.move(-1, dt, limit, paddle_speed)

        # Move Stars
        for star in self.stars:
            star.update(dt, self.w_half, self.h_half)

        # Powerup Animation
        if self.powerup_active:
            self.powerup.sety((self.h_half - 100) * math.sin(time.time() * 2))

        # Ball Logic
        for ball in self.balls:
            ball.setx(ball.xcor() + ball.dx)
            ball.sety(ball.ycor() + ball.dy)

            # Wall Collisions
            if ball.ycor() > (self.h_half - 15) or ball.ycor() < -(self.h_half - 15):
                ball.dy *= -1
                self.sound.play("wall")

            # Scoring
            if ball.xcor() > self.w_half:
                self.score_a += 1
                self.handle_score(ball)
            elif ball.xcor() < -self.w_half:
                self.score_b += 1
                self.handle_score(ball)

            # Paddle Collisions
            self.check_paddle_collision(ball, self.paddle_a, -1)
            self.check_paddle_collision(ball, self.paddle_b, 1)
            
            # Powerup Collision
            if self.powerup_active and time.time() > self.powerup_cooldown:
                if ball.distance(self.powerup) < 60:
                    self.activate_powerup()

    def handle_score(self, ball):
        self.sound.play("score")
        self.update_score_display()
        
        if len(self.balls) > 1:
            ball.hideturtle()
            self.balls.remove(ball)
        else:
            ball.serve()
            self.reset_round()

        if self.score_a >= WINNING_SCORE or self.score_b >= WINNING_SCORE:
            self.end_game()

    def reset_round(self):
        self.ghost_mode = False
        self.speed_boost_count = 0
        self.powerup_cooldown = time.time() + 0.5
        self.paddle_a.shapesize(5, 1)
        self.paddle_b.shapesize(5, 1)

    def check_paddle_collision(self, ball, paddle, side_multiplier):
        # side_multiplier: -1 for Left Paddle, 1 for Right Paddle
        collision_x = False
        if side_multiplier == -1: # Left
            collision_x = (ball.xcor() < paddle.xcor() + 20) and (ball.xcor() > paddle.xcor() - 20) and (ball.dx < 0)
        else: # Right
            collision_x = (ball.xcor() > paddle.xcor() - 20) and (ball.xcor() < paddle.xcor() + 20) and (ball.dx > 0)

        if collision_x:
            if abs(ball.ycor() - paddle.ycor()) < 60:
                # Fix Tunneling
                ball.setx(paddle.xcor() + (20 * -side_multiplier))
                
                # Reflect and slightly speed up
                ball.dx *= -1.05
                
                # Cap Speed
                if abs(ball.dx) > ball.speed_cap:
                    ball.dx = ball.speed_cap if ball.dx > 0 else -ball.speed_cap

                # Calculate Angle
                ball.dy = ((ball.ycor() - paddle.ycor()) / 50.0) * abs(ball.dx)
                
                self.sound.play("bounce")
                self.last_hitter = "A" if side_multiplier == -1 else "B"

    def activate_powerup(self):
        self.powerup_active = False
        self.powerup.hideturtle()
        
        p_type = self.powerup_type
        
        if p_type == "size":
            if self.last_hitter == "A": self.paddle_a.shapesize(10, 1)
            elif self.last_hitter == "B": self.paddle_b.shapesize(10, 1)
            
        elif p_type == "ghost":
            self.ghost_mode = True
            self.ghost_end_time = time.time() + 3
            
        elif p_type == "freeze":
            if self.last_hitter == "A": self.paddle_b.frozen_until = time.time() + 0.4
            elif self.last_hitter == "B": self.paddle_a.frozen_until = time.time() + 0.4
            
        elif p_type == "split":
            if len(self.balls) == 1:
                new_ball = Ball(self.ball_start_speed, self.ball_speed_cap)
                new_ball.goto(self.balls[0].xcor(), self.balls[0].ycor())
                new_ball.dx = self.balls[0].dx
                new_ball.dy = -self.balls[0].dy
                new_ball.color("red")
                self.balls.append(new_ball)

    def spawn_powerup_logic(self):
        if not self.powerup_active and self.active and random.randint(1, 500) == 1:
            self.powerup_type = self.powerup_cycle[self.powerup_idx]
            self.powerup_idx = (self.powerup_idx + 1) % len(self.powerup_cycle)
            
            if self.powerup_type == "size": self.powerup.color(COLOR_SIZE)
            elif self.powerup_type == "ghost": self.powerup.color(COLOR_GHOST)
            elif self.powerup_type == "freeze": self.powerup.color(COLOR_FREEZE)
            elif self.powerup_type == "split": self.powerup.color(COLOR_SPLIT)
            
            self.powerup.goto(0, 0)
            self.powerup.showturtle()
            self.powerup_active = True

    def end_game(self):
        self.active = False
        msg = "PLAYER A WINS!" if self.score_a >= WINNING_SCORE else "PLAYER B WINS!"
        self.pen.goto(0, 0)
        self.pen.write(f"{msg}\nSPACE TO RESTART", align="center", font=("Courier", 30, "bold"))

    def run(self):
        last_time = time.time()
        
        while True:
            # Delta Time Calculation
            current_time = time.time()
            dt = current_time - last_time
            last_time = current_time

            self.win.update()
            
            if self.active:
                self.physics_step(dt)
                self.spawn_powerup_logic()
                
                # Ghost Mode Visuals
                if self.ghost_mode:
                    if time.time() > self.ghost_end_time:
                        self.ghost_mode = False
                        for b in self.balls: b.color("white")
                    else:
                        for b in self.balls: b.color("#222222")

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    game = Game()
    game.run()