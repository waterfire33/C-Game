import turtle
import time
import os
import random
import math
import subprocess
import atexit

# 1. SOUND & MUTE LOGIC
sounds_on = True
sound_processes = []

def cleanup_sounds():
    """Kill all sound processes when game exits"""
    for p in sound_processes:
        try:
            p.terminate()
        except:
            pass

atexit.register(cleanup_sounds)

def toggle_mute():
    global sounds_on
    sounds_on = not sounds_on

def paddle_sound():
    if sounds_on:
        global sound_processes
        sound_processes = [p for p in sound_processes if p.poll() is None]
        try:
            if os.path.exists("bounce.ogg"):
                p = subprocess.Popen(['afplay', 'bounce.ogg'], 
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                sound_processes.append(p)
        except:
            pass

def wall_sound():
    if sounds_on:
        global sound_processes
        sound_processes = [p for p in sound_processes if p.poll() is None]
        try:
            if os.path.exists("wall.ogg"):
                p = subprocess.Popen(['afplay', 'wall.ogg'], 
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                sound_processes.append(p)
        except:
            pass

def score_sound():
    if sounds_on:
        global sound_processes
        sound_processes = [p for p in sound_processes if p.poll() is None]
        try:
            if os.path.exists("score.ogg"):
                p = subprocess.Popen(['afplay', 'score.ogg'], 
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                sound_processes.append(p)
        except:
            pass

# 2. SCREEN SETUP & FULLSCREEN
win = turtle.Screen()
win.title("Starfield Pong")
win.bgcolor("black")
root = win.getcanvas().winfo_toplevel()
root.attributes("-fullscreen", True)
win.update() 

# Get dynamic dimensions
W_HALF = win.window_width() / 2
H_HALF = win.window_height() / 2
win.tracer(0)

# 3. STARFIELD GENERATION
stars = []
for _ in range(100):
    star = turtle.Turtle()
    star.shape("circle")
    star.color("white")
    star.penup()
    star.goto(random.randint(int(-W_HALF), int(W_HALF)), random.randint(int(-H_HALF), int(H_HALF)))
    size = random.uniform(0.05, 0.2)
    star.shapesize(size, size)
    star.speed_val = size * 5
    stars.append(star)

# 4. GAME STATE
score_a, score_b = 0, 0
winning_score = 11
game_active = False 
ghost_mode = False
paddle_boost_hits = {"A": 0, "B": 0}
last_hitter = None
powerup_active = False
ghost_end = 0
freeze_end_a = 0
freeze_end_b = 0
speed_boost_count = 0
balls = []  # List to track multiple balls
second_ball_spawn_time = 0  # Timer for delayed second ball
cursor_hidden = False
powerup_cycle = ["size", "ghost", "freeze", "split"]  # Cycle through powerups
powerup_index = 0  # Current powerup in cycle
powerup_collision_cooldown = 0  # Prevent immediate powerup collision after serve

keys_pressed = {"w": False, "s": False, "Up": False, "Down": False}

def set_key_true(key): keys_pressed[key] = True
def set_key_false(key): keys_pressed[key] = False

def on_mouse_move(event):
    global cursor_hidden
    if cursor_hidden:
        win.getcanvas().config(cursor="")
        cursor_hidden = False

# 5. OBJECTS
net = turtle.Turtle()
net.color("gray"); net.penup(); net.goto(0, H_HALF); net.setheading(270); net.width(2); net.hideturtle()
for _ in range(int(win.window_height()/40)): net.pendown(); net.forward(20); net.penup(); net.forward(20)

PADDLE_X = W_HALF - 50

paddle_a = turtle.Turtle()
paddle_a.shape("square"); paddle_a.color("white"); paddle_a.shapesize(5, 1); paddle_a.penup(); paddle_a.goto(-PADDLE_X, 0)

paddle_b = turtle.Turtle()
paddle_b.shape("square"); paddle_b.color("white"); paddle_b.shapesize(5, 1); paddle_b.penup(); paddle_b.goto(PADDLE_X, 0)

ball = turtle.Turtle()
ball.shape("circle"); ball.color("white"); ball.penup()

ball2 = turtle.Turtle()
ball2.shape("circle"); ball2.color("red"); ball2.penup(); ball2.hideturtle()

pwr = turtle.Turtle()
pwr.shape("circle"); pwr.shapesize(4, 4); pwr.penup(); pwr.hideturtle()

score_display_a = turtle.Turtle()
score_display_a.color("white"); score_display_a.penup(); score_display_a.hideturtle(); score_display_a.goto(-150, H_HALF - 150)

score_display_b = turtle.Turtle()
score_display_b.color("white"); score_display_b.penup(); score_display_b.hideturtle(); score_display_b.goto(150, H_HALF - 150)

menu_pen = turtle.Turtle()
menu_pen.color("white"); menu_pen.penup(); menu_pen.hideturtle(); menu_pen.goto(0, 0)
menu_pen.write("PRESS SPACE TO START", align="center", font=("Courier", 30, "bold"))

# 6. LOGIC FUNCTIONS
def update_scores():
    score_display_a.clear(); score_display_b.clear()
    score_display_a.write(str(score_a), align="center", font=("Courier", 80, "bold"))
    score_display_b.write(str(score_b), align="center", font=("Courier", 80, "bold"))

def start_or_reset():
    global score_a, score_b, game_active, ghost_mode, paddle_boost_hits, balls, cursor_hidden, second_ball_spawn_time, keys_pressed, powerup_index
    if not game_active:
        score_a, score_b = 0, 0
        game_active = True
        ghost_mode = False
        paddle_boost_hits = {"A": 0, "B": 0}
        paddle_a.shapesize(5, 1); paddle_b.shapesize(5, 1)
        balls = [ball]  # Start with one ball
        ball.color("white")  # Ensure ball starts white
        ball2.hideturtle()
        second_ball_spawn_time = 0  # Reset spawn timer
        powerup_index = 2  # Start with freeze powerup (index 2: size, ghost, freeze, split)
        keys_pressed = {"q": False, "z": False, "i": False, "n": False, "w": False, "s": False, "Up": False, "Down": False}  # Reset all keys
        win.getcanvas().config(cursor="none")
        cursor_hidden = True
        menu_pen.clear()
        update_scores()
        serve_ball()

def serve_ball():
    global last_hitter, ghost_mode, speed_boost_count, powerup_collision_cooldown
    last_hitter = None
    ghost_mode = False
    speed_boost_count = 0
    powerup_collision_cooldown = time.time() + 0.5  # 0.5 second cooldown
    ball.color("white")
    ball.goto(0, 0)
    ball.dx = random.choice([12.0, -12.0])
    ball.dy = random.uniform(-4.0, 4.0)

def spawn_powerup():
    global powerup_active, pwr_type, powerup_index
    if not powerup_active and random.randint(1, 500) == 1:
        # Get current powerup from cycle
        pwr_type = powerup_cycle[powerup_index]
        powerup_index = (powerup_index + 1) % len(powerup_cycle)  # Move to next, loop back
        
        if pwr_type == "size":
            pwr.color("green")
        elif pwr_type == "ghost":
            pwr.color("orange")
        elif pwr_type == "freeze":
            pwr.color("light blue")
        else:  # split
            pwr.color("red")
        
        pwr.goto(0, 0)
        pwr.showturtle()
        powerup_active = True

# 7. BINDINGS
win.listen()
win.getcanvas().bind("<Motion>", on_mouse_move)
win.onkeypress(lambda: set_key_true("q"), "q")
win.onkeypress(lambda: set_key_true("z"), "z")
win.onkeypress(lambda: set_key_true("i"), "i")

win.onkeypress(lambda: set_key_true("n"), "n")
win.onkeyrelease(lambda: set_key_false("q"), "q")
win.onkeyrelease(lambda: set_key_false("z"), "z")
win.onkeyrelease(lambda: set_key_false("i"), "i")
win.onkeyrelease(lambda: set_key_false("n"), "n")
win.onkeypress(toggle_mute, "m")
win.onkeypress(start_or_reset, "space")
win.onkeypress(lambda: root.attributes("-fullscreen", False), "Escape")

# 8. MAIN LOOP
P_SPEED = 30
while True:
    win.update()
    time.sleep(0.01)

    for star in stars:
        star.setx(star.xcor() - star.speed_val)
        if star.xcor() < -W_HALF:
            star.goto(W_HALF, random.randint(int(-H_HALF), int(H_HALF)))

    if game_active:
        # Check freeze status and update paddle colors
        paddle_a_frozen = time.time() < freeze_end_a
        paddle_b_frozen = time.time() < freeze_end_b
        
        # Update paddle A color
        if paddle_a_frozen:
            paddle_a.color("light blue")
        else:
            paddle_a.color("white")
        
        # Update paddle B color
        if paddle_b_frozen:
            paddle_b.color("light blue")
        else:
            paddle_b.color("white")
        
        if not paddle_a_frozen:
            if keys_pressed["q"] and paddle_a.ycor() < (H_HALF - 50): paddle_a.sety(paddle_a.ycor() + P_SPEED)
            if keys_pressed["z"] and paddle_a.ycor() > -(H_HALF - 50): paddle_a.sety(paddle_a.ycor() - P_SPEED)
        if not paddle_b_frozen:
            if keys_pressed["i"] and paddle_b.ycor() < (H_HALF - 50): paddle_b.sety(paddle_b.ycor() + P_SPEED)
            if keys_pressed["n"] and paddle_b.ycor() > -(H_HALF - 50): paddle_b.sety(paddle_b.ycor() - P_SPEED)

        # Move all balls
        for b in balls[:]:
            b.setx(b.xcor() + b.dx); b.sety(b.ycor() + b.dy)

            if b.ycor() > (H_HALF - 15):
                b.sety(H_HALF - 15)
                b.dy *= -1
                wall_sound()
            elif b.ycor() < -(H_HALF - 15):
                b.sety(-(H_HALF - 15))
                b.dy *= -1
                wall_sound()

            # Check scoring
            if b.xcor() > W_HALF:
                score_a += 1
                score_sound(); update_scores()
                if b == ball2:
                    balls.remove(ball2); ball2.hideturtle()
                else:
                    serve_ball()
            elif b.xcor() < -W_HALF:
                score_b += 1
                score_sound(); update_scores()
                if b == ball2:
                    balls.remove(ball2); ball2.hideturtle()
                else:
                    serve_ball()

        if powerup_active:
            pwr.sety((H_HALF - 100) * math.sin(time.time() * 2))
            # Only check collision if cooldown has expired
            if time.time() >= powerup_collision_cooldown:
                for b in balls:
                    if b.distance(pwr) < 60:
                        pwr.hideturtle(); powerup_active = False
                        if pwr_type == "size":
                            if last_hitter == "A": 
                                paddle_a.shapesize(10, 1); paddle_boost_hits["A"] = 2
                            elif last_hitter == "B": 
                                paddle_b.shapesize(10, 1); paddle_boost_hits["B"] = 2
                        elif pwr_type == "ghost":
                            ghost_mode = True; ghost_end = time.time() + 3
                        elif pwr_type == "freeze":
                            if last_hitter == "A":
                                freeze_end_b = time.time() + 0.40
                            elif last_hitter == "B":
                                freeze_end_a = time.time() + 0.40
                        else:  # split
                            if len(balls) == 1:  # Only split once
                                ball.color("red")
                                # Set up second ball but don't show it yet
                                ball2.goto(ball.xcor(), ball.ycor())
                                ball2.dx = ball.dx
                                ball2.dy = -ball.dy  # Opposite Y direction
                                ball2.color("red")
                                second_ball_spawn_time = time.time() + 1.5  # Spawn in 1.5 seconds
                        break
        else:
            spawn_powerup()

        # Check if second ball should spawn
        if second_ball_spawn_time > 0 and time.time() >= second_ball_spawn_time:
            ball2.showturtle()
            balls.append(ball2)
            second_ball_spawn_time = 0  # Reset timer

        if ghost_mode:
            if time.time() > ghost_end:
                ghost_mode = False; ball.color("white")
            else:
                ball.color("#222222")

        # Paddle B Collision with Momentum
        for b in balls:
            if (b.xcor() > paddle_b.xcor() - 20 and b.xcor() < paddle_b.xcor()) and (b.dx > 0):
                hit_range = 110 if paddle_boost_hits["B"] > 0 else 60
                if abs(b.ycor() - paddle_b.ycor()) < hit_range:
                    b.setx(paddle_b.xcor() - 20)
                    b.dx *= -1.05
                    
                    # End ghost mode on paddle collision
                    if ghost_mode:
                        ghost_mode = False
                    
                    # Check for moving hit
                    if (keys_pressed["i"] or keys_pressed["n"]) and speed_boost_count < 3:
                        b.dx *= 1.2  # Add 20% extra speed
                        speed_boost_count += 1
                        b.color("yellow")
                    else:
                        b.color("white")

                    # Cap speed at 15.0
                    if abs(b.dx) > 15.0:
                        b.dx = -15.0 if b.dx < 0 else 15.0

                    b.dy = ((b.ycor() - paddle_b.ycor()) / 50.0) * abs(b.dx)
                    if abs(b.dy) < 1.5: b.dy = 1.5 if b.dy >= 0 else -1.5
                    last_hitter = "B"; paddle_sound()
                    if paddle_boost_hits["B"] > 0:
                        paddle_boost_hits["B"] -= 1
                        if paddle_boost_hits["B"] == 0: paddle_b.shapesize(5, 1)

        # Paddle A Collision with Momentum
        for b in balls:
            if (b.xcor() < paddle_a.xcor() + 20 and b.xcor() > paddle_a.xcor()) and (b.dx < 0):
                hit_range = 110 if paddle_boost_hits["A"] > 0 else 60
                if abs(b.ycor() - paddle_a.ycor()) < hit_range:
                    b.setx(paddle_a.xcor() + 20)
                    b.dx *= -1.05
                    
                    # End ghost mode on paddle collision
                    if ghost_mode:
                        ghost_mode = False
                    
                    # Check for moving hit
                    if (keys_pressed["q"] or keys_pressed["z"]) and speed_boost_count < 3:
                        b.dx *= 1.2  # Add 20% extra speed
                        speed_boost_count += 1
                        b.color("yellow")
                    else:
                        b.color("white")

                    # Cap speed at 15.0
                    if abs(b.dx) > 15.0:
                        b.dx = -15.0 if b.dx < 0 else 15.0

                    b.dy = ((b.ycor() - paddle_a.ycor()) / 50.0) * abs(b.dx)
                    if abs(b.dy) < 1.5: b.dy = 1.5 if b.dy >= 0 else -1.5
                    last_hitter = "A"; paddle_sound()
                    if paddle_boost_hits["A"] > 0:
                        paddle_boost_hits["A"] -= 1
                        if paddle_boost_hits["A"] == 0: paddle_a.shapesize(5, 1)

        if score_a >= winning_score or score_b >= winning_score:
            game_active = False
            menu_pen.goto(0, 0)
            msg = "PLAYER A WINS!" if score_a >= winning_score else "PLAYER B WINS!"
            menu_pen.write(f"{msg}\nSPACE TO RESTART", align="center", font=("Courier", 30, "bold"))