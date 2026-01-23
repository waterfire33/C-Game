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
win.getcanvas().config(cursor="none")
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

keys_pressed = {"w": False, "s": False, "Up": False, "Down": False}

def set_key_true(key): keys_pressed[key] = True
def set_key_false(key): keys_pressed[key] = False

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
    global score_a, score_b, game_active, ghost_mode, paddle_boost_hits
    if not game_active:
        score_a, score_b = 0, 0
        game_active = True
        ghost_mode = False
        paddle_boost_hits = {"A": 0, "B": 0}
        paddle_a.shapesize(5, 1); paddle_b.shapesize(5, 1)
        menu_pen.clear()
        update_scores()
        serve_ball()

def serve_ball():
    global last_hitter, ghost_mode
    last_hitter = None
    ghost_mode = False
    ball.color("white")
    ball.goto(0, 0)
    ball.dx = random.choice([7.0, -7.0])
    ball.dy = random.uniform(-5.0, 5.0)

def spawn_powerup():
    global powerup_active, pwr_type
    if not powerup_active and random.randint(1, 500) == 1:
        pwr_type = random.choice(["size", "ghost"])
        pwr.color("cyan" if pwr_type == "size" else "orange")
        pwr.goto(0, 0)
        pwr.showturtle()
        powerup_active = True

# 7. BINDINGS
win.listen()
win.onkeypress(lambda: set_key_true("w"), "w")
win.onkeypress(lambda: set_key_true("s"), "s")
win.onkeypress(lambda: set_key_true("Up"), "Up")
win.onkeypress(lambda: set_key_true("Down"), "Down")
win.onkeyrelease(lambda: set_key_false("w"), "w")
win.onkeyrelease(lambda: set_key_false("s"), "s")
win.onkeyrelease(lambda: set_key_false("Up"), "Up")
win.onkeyrelease(lambda: set_key_false("Down"), "Down")
win.onkeypress(toggle_mute, "m")
win.onkeypress(start_or_reset, "space")
win.onkeypress(lambda: root.attributes("-fullscreen", False), "Escape")

# 8. MAIN LOOP
P_SPEED = 15
while True:
    win.update()
    time.sleep(0.01)

    for star in stars:
        star.setx(star.xcor() - star.speed_val)
        if star.xcor() < -W_HALF:
            star.goto(W_HALF, random.randint(int(-H_HALF), int(H_HALF)))

    if game_active:
        if keys_pressed["w"] and paddle_a.ycor() < (H_HALF - 50): paddle_a.sety(paddle_a.ycor() + P_SPEED)
        if keys_pressed["s"] and paddle_a.ycor() > -(H_HALF - 50): paddle_a.sety(paddle_a.ycor() - P_SPEED)
        if keys_pressed["Up"] and paddle_b.ycor() < (H_HALF - 50): paddle_b.sety(paddle_b.ycor() + P_SPEED)
        if keys_pressed["Down"] and paddle_b.ycor() > -(H_HALF - 50): paddle_b.sety(paddle_b.ycor() - P_SPEED)

        ball.setx(ball.xcor() + ball.dx); ball.sety(ball.ycor() + ball.dy)

        if ball.ycor() > (H_HALF - 15) or ball.ycor() < -(H_HALF - 15):
            ball.dy *= -1
            wall_sound()

        if powerup_active:
            pwr.sety((H_HALF - 100) * math.sin(time.time() * 2))
            if ball.distance(pwr) < 60:
                pwr.hideturtle(); powerup_active = False
                if pwr_type == "size":
                    if last_hitter == "A": 
                        paddle_a.shapesize(10, 1); paddle_boost_hits["A"] = 2
                    elif last_hitter == "B": 
                        paddle_b.shapesize(10, 1); paddle_boost_hits["B"] = 2
                else:
                    ghost_mode = True; ghost_end = time.time() + 3
        else:
            spawn_powerup()

        if ghost_mode:
            if time.time() > ghost_end:
                ghost_mode = False; ball.color("white")
            else:
                ball.color("#222222")

        if ball.xcor() > W_HALF:
            score_a += 1
            score_sound(); update_scores(); serve_ball()
        elif ball.xcor() < -W_HALF:
            score_b += 1
            score_sound(); update_scores(); serve_ball()

        # Paddle B Collision with Momentum
        if (ball.xcor() > paddle_b.xcor() - 20 and ball.xcor() < paddle_b.xcor()) and (ball.dx > 0):
            hit_range = 110 if paddle_boost_hits["B"] > 0 else 60
            if abs(ball.ycor() - paddle_b.ycor()) < hit_range:
                ball.setx(paddle_b.xcor() - 20)
                ball.dx *= -1.05
                
                # Check for moving hit
                if keys_pressed["Up"] or keys_pressed["Down"]:
                    ball.dx *= 1.2  # Add 20% extra speed
                    ball.color("yellow")
                elif not ghost_mode:
                    ball.color("white")

                ball.dy = ((ball.ycor() - paddle_b.ycor()) / 50.0) * abs(ball.dx)
                if abs(ball.dy) < 1.5: ball.dy = 1.5 if ball.dy >= 0 else -1.5
                last_hitter = "B"; paddle_sound()
                if paddle_boost_hits["B"] > 0:
                    paddle_boost_hits["B"] -= 1
                    if paddle_boost_hits["B"] == 0: paddle_b.shapesize(5, 1)

        # Paddle A Collision with Momentum
        if (ball.xcor() < paddle_a.xcor() + 20 and ball.xcor() > paddle_a.xcor()) and (ball.dx < 0):
            hit_range = 110 if paddle_boost_hits["A"] > 0 else 60
            if abs(ball.ycor() - paddle_a.ycor()) < hit_range:
                ball.setx(paddle_a.xcor() + 20)
                ball.dx *= -1.05
                
                # Check for moving hit
                if keys_pressed["w"] or keys_pressed["s"]:
                    ball.dx *= 1.2  # Add 20% extra speed
                    ball.color("yellow")
                elif not ghost_mode:
                    ball.color("white")

                ball.dy = ((ball.ycor() - paddle_a.ycor()) / 50.0) * abs(ball.dx)
                if abs(ball.dy) < 1.5: ball.dy = 1.5 if ball.dy >= 0 else -1.5
                last_hitter = "A"; paddle_sound()
                if paddle_boost_hits["A"] > 0:
                    paddle_boost_hits["A"] -= 1
                    if paddle_boost_hits["A"] == 0: paddle_a.shapesize(5, 1)

        if score_a >= winning_score or score_b >= winning_score:
            game_active = False
            menu_pen.goto(0, 0)
            msg = "PLAYER A WINS!" if score_a >= winning_score else "PLAYER B WINS!"
            menu_pen.write(f"{msg}\nSPACE TO RESTART", align="center", font=("Courier", 30, "bold"))