from kivy.app import App
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.widget import Widget
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle, Line, Ellipse

import random

# ----------------------------- КОНСТАНТЫ -----------------------------
COLS = 10
ROWS = 20
DOOR_ROW = 9          # высота двери (клеток от дна, нижний ряд двери)
DOOR_HEIGHT = 2       # двери высотой 2 клетки

# Типы «строительного мусора» — аналоги I, O, L, J, Z, S, T
SHAPES = {
    "I": {"cells": [(0, 0), (1, 0), (2, 0), (3, 0)], "color": (0.55, 0.55, 0.6),  "kind": "rebar"},
    "O": {"cells": [(0, 0), (1, 0), (0, 1), (1, 1)], "color": (0.7, 0.35, 0.2),   "kind": "brick"},
    "L": {"cells": [(0, 0), (0, 1), (0, 2), (1, 0)], "color": (0.45, 0.45, 0.5),  "kind": "concrete"},
    "J": {"cells": [(1, 0), (1, 1), (1, 2), (0, 0)], "color": (0.4, 0.3, 0.25),   "kind": "wood"},
    "Z": {"cells": [(0, 1), (1, 1), (1, 0), (2, 0)], "color": (0.5, 0.35, 0.3),   "kind": "rust"},
    "S": {"cells": [(0, 0), (1, 0), (1, 1), (2, 1)], "color": (0.35, 0.35, 0.4),  "kind": "metal"},
    "T": {"cells": [(0, 1), (1, 1), (2, 1), (1, 0)], "color": (0.3, 0.3, 0.35),   "kind": "chain"},
}
SHAPE_KEYS = list(SHAPES.keys())


def rotate_cells(cells):
    """Поворот фигуры на 90° по часовой стрелке вокруг (0,0)."""
    rotated = [(y, -x) for (x, y) in cells]
    min_x = min(c[0] for c in rotated)
    min_y = min(c[1] for c in rotated)
    return [(x - min_x, y - min_y) for (x, y) in rotated]


# ----------------------------- ИГРОВОЕ ПОЛЕ -----------------------------
class TetrillerWidget(Widget):
    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        self.fall_speed = 0.6
        self.fall_timer = 0
        self.hero_speed = 0.25
        self.hero_timer = 0
        self.soft_drop = False
        self.paused = False
        self.game_over = False
        self.escaped = False

        self.grid = [[None for _ in range(COLS)] for _ in range(ROWS)]
        self.cur = None
        self.next_shape = random.choice(SHAPE_KEYS)
        self.spawn_piece()

        self.hero = {"x": COLS // 2, "dir": 1, "crouch": False, "y": 0}

        self.bind(pos=lambda *a: self.redraw(),
                  size=lambda *a: self.redraw())

    def spawn_piece(self):
        shape = self.next_shape
        self.next_shape = random.choice(SHAPE_KEYS)
        data = SHAPES[shape]
        cells = [tuple(c) for c in data["cells"]]
        max_x = max(c[0] for c in cells)
        x = (COLS - (max_x + 1)) // 2
        y = ROWS - 1 - max(c[1] for c in cells)
        self.cur = {
            "shape": shape, "cells": cells, "x": x, "y": y,
            "color": data["color"], "kind": data["kind"],
        }
        if self.collides(self.cur["cells"], self.cur["x"], self.cur["y"]):
            self.lose_life()

    def collides(self, cells, ox, oy):
        for (cx, cy) in cells:
            x, y = ox + cx, oy + cy
            if x < 0 or x >= COLS or y < 0:
                return True
            if y < ROWS and self.grid[y][x] is not None:
                return True
        return False

    def collides_with_hero(self, cells, ox, oy):
        hx, hy = self.hero["x"], self.hero["y"]
        hero_cells = [(hx, hy)] if self.hero["crouch"] else [(hx, hy), (hx, hy + 1)]
        for (cx, cy) in cells:
            if (ox + cx, oy + cy) in hero_cells:
                return True
        return False

    def move(self, dx):
        if not self.cur or self.paused or self.game_over:
            return
        nx = self.cur["x"] + dx
        if not self.collides(self.cur["cells"], nx, self.cur["y"]):
            self.cur["x"] = nx
            self.redraw()

    def rotate(self):
        if not self.cur or self.paused or self.game_over:
            return
        new_cells = rotate_cells(self.cur["cells"])
        for kick in (0, -1, 1, -2, 2):
            if not self.collides(new_cells, self.cur["x"] + kick, self.cur["y"]):
                self.cur["cells"] = new_cells
                self.cur["x"] += kick
                self.redraw()
                return

    def hard_drop(self):
        if not self.cur or self.paused or self.game_over:
            return
        while not self.collides(self.cur["cells"], self.cur["x"], self.cur["y"] - 1):
            self.cur["y"] -= 1
        self.lock_piece()

    def lock_piece(self):
        crushed = False
        if self.collides_with_hero(self.cur["cells"], self.cur["x"], self.cur["y"]):
            if not self.hero["crouch"]:
                self.hero["crouch"] = True
                if self.collides_with_hero(self.cur["cells"], self.cur["x"], self.cur["y"]):
                    crushed = True
            else:
                crushed = True

        for (cx, cy) in self.cur["cells"]:
            x, y = self.cur["x"] + cx, self.cur["y"] + cy
            if 0 <= y < ROWS and 0 <= x < COLS:
                self.grid[y][x] = {"color": self.cur["color"], "kind": self.cur["kind"]}
            else:
                crushed = True

        self.cur = None
        if crushed:
            self.lose_life()
        else:
            self.app.add_points(10)
            self.spawn_piece()
            self.update_hero_after_lock()

    def update_hero_after_lock(self):
        hx = self.hero["x"]
        self.hero["y"] = self.support_y(hx)
        if self.hero["crouch"]:
            top = self.hero["y"] + 1
            if top < ROWS and self.grid[top][hx] is None:
                self.hero["crouch"] = False

    def support_y(self, x):
        y = 0
        for ny in range(ROWS):
            if self.grid[ny][x] is not None:
                y = ny + 1
        return y

    def clear_full_rows(self):
        new_grid = [row for row in self.grid if any(c is None for c in row)]
        cleared = ROWS - len(new_grid)
        while len(new_grid) < ROWS:
            new_grid.append([None for _ in range(COLS)])
        self.grid = new_grid
        if cleared:
            self.app.add_points(cleared * 100)

    def hero_step(self):
        if self.game_over or self.escaped:
            return
        hx, hy = self.hero["x"], self.hero["y"]
        d = self.hero["dir"]
        nx = hx + d

        if (nx < 0 or nx >= COLS) and hy == DOOR_ROW:
            self.escape()
            return

        if nx < 0 or nx >= COLS:
            self.hero["dir"] = -d
            return

        new_support = self.support_y(nx)
        diff = new_support - hy

        if diff > 1 or diff < -1:
            self.hero["dir"] = -d
            return

        target_y = new_support
        need_full = not self.hero["crouch"]
        cells_needed = [(nx, target_y)]
        if need_full:
            cells_needed.append((nx, target_y + 1))

        for (x, y) in cells_needed:
            if y >= ROWS:
                continue
            if self.grid[y][x] is not None:
                if need_full:
                    if self.grid[target_y][nx] is None:
                        self.hero["crouch"] = True
                        need_full = False
                        break
                    else:
                        self.hero["dir"] = -d
                        return
                else:
                    self.hero["dir"] = -d
                    return

        self.hero["x"] = nx
        self.hero["y"] = target_y

        if self.hero["crouch"]:
            top = self.hero["y"] + 1
            if top >= ROWS or self.grid[top][nx] is None:
                self.hero["crouch"] = False

    def escape(self):
        self.escaped = True
        self.app.add_points(1000)
        for y in range(ROWS):
            for x in range(COLS):
                self.grid[y][x] = None
        self.hero = {"x": COLS // 2, "dir": 1, "crouch": False, "y": 0}
        self.cur = None
        self.spawn_piece()
        self.app.next_level()
        self.escaped = False

    def lose_life(self):
        self.game_over = True
        self.app.lose_life()

    def tick(self, dt):
        if self.paused or self.game_over:
            return
        self.fall_timer += dt
        speed = 0.05 if self.soft_drop else self.fall_speed
        if self.fall_timer >= speed:
            self.fall_timer = 0
            if self.cur:
                if self.collides(self.cur["cells"], self.cur["x"], self.cur["y"] - 1):
                    self.lock_piece()
                    self.clear_full_rows()
                else:
                    self.cur["y"] -= 1

        self.hero_timer += dt
        if self.hero_timer >= self.hero_speed:
            self.hero_timer = 0
            self.hero["y"] = self.support_y(self.hero["x"])
            top = self.hero["y"] + (0 if self.hero["crouch"] else 1)
            if top < ROWS and self.grid[top][self.hero["x"]] is not None and not self.hero["crouch"]:
                self.hero["crouch"] = True
            self.hero_step()

        self.redraw()

    def cell_size(self):
        return min(self.width / COLS, self.height / ROWS)

    def redraw(self):
        self.canvas.clear()
        cs = self.cell_size()
        ox = self.x + (self.width - cs * COLS) / 2
        oy = self.y + (self.height - cs * ROWS) / 2

        with self.canvas:
            Color(0.08, 0.08, 0.1)
            Rectangle(pos=(ox, oy), size=(cs * COLS, cs * ROWS))

            Color(0.15, 0.15, 0.18)
            for i in range(COLS + 1):
                Line(points=[ox + i * cs, oy, ox + i * cs, oy + cs * ROWS])
            for j in range(ROWS + 1):
                Line(points=[ox, oy + j * cs, ox + cs * COLS, oy + j * cs])

            Color(0.1, 0.6, 0.3, 0.45)
            Rectangle(pos=(ox - cs * 0.3, oy + DOOR_ROW * cs),
                      size=(cs * 0.3, cs * DOOR_HEIGHT))
            Rectangle(pos=(ox + cs * COLS, oy + DOOR_ROW * cs),
                      size=(cs * 0.3, cs * DOOR_HEIGHT))
            Color(0.3, 1, 0.5)
            Line(rectangle=(ox - cs * 0.3, oy + DOOR_ROW * cs,
                            cs * 0.3, cs * DOOR_HEIGHT), width=1.2)
            Line(rectangle=(ox + cs * COLS, oy + DOOR_ROW * cs,
                            cs * 0.3, cs * DOOR_HEIGHT), width=1.2)

            for y in range(ROWS):
                for x in range(COLS):
                    cell = self.grid[y][x]
                    if cell:
                        self._draw_block(ox + x * cs, oy + y * cs, cs, cell["color"], cell["kind"])

            if self.cur:
                gy = self.cur["y"]
                while not self.collides(self.cur["cells"], self.cur["x"], gy - 1):
                    gy -= 1
                Color(*self.cur["color"], 0.2)
                for (cx, cy) in self.cur["cells"]:
                    Rectangle(pos=(ox + (self.cur["x"] + cx) * cs,
                                   oy + (gy + cy) * cs),
                              size=(cs, cs))
                for (cx, cy) in self.cur["cells"]:
                    self._draw_block(ox + (self.cur["x"] + cx) * cs,
                                     oy + (self.cur["y"] + cy) * cs,
                                     cs, self.cur["color"], self.cur["kind"])

            self._draw_hero(ox, oy, cs)

            Color(0.5, 0.5, 0.55)
            Line(rectangle=(ox, oy, cs * COLS, cs * ROWS), width=1.5)

    def _draw_block(self, x, y, s, color, kind):
        r, g, b = color
        Color(r, g, b)
        Rectangle(pos=(x + 1, y + 1), size=(s - 2, s - 2))
        if kind == "brick":
            Color(r * 0.6, g * 0.6, b * 0.6)
            Line(points=[x, y + s / 2, x + s, y + s / 2])
            Line(points=[x + s / 2, y, x + s / 2, y + s / 2])
        elif kind == "rebar":
            Color(0.95, 0.85, 0.2)
            for i in range(3):
                px = x + (i + 1) * s / 4
                Line(points=[px, y + s, px, y + s + s * 0.3], width=1.3)
        elif kind == "concrete":
            Color(r * 0.7, g * 0.7, b * 0.7)
            Ellipse(pos=(x + s * 0.2, y + s * 0.2), size=(s * 0.15, s * 0.15))
            Ellipse(pos=(x + s * 0.6, y + s * 0.5), size=(s * 0.12, s * 0.12))
        elif kind == "wood":
            Color(r * 0.5, g * 0.5, b * 0.5)
            Line(points=[x, y + s * 0.3, x + s, y + s * 0.3])
            Line(points=[x, y + s * 0.7, x + s, y + s * 0.7])
        elif kind == "rust":
            Color(0.7, 0.3, 0.1)
            Ellipse(pos=(x + s * 0.3, y + s * 0.3), size=(s * 0.2, s * 0.2))
        elif kind == "metal":
            Color(min(1, r * 1.3), min(1, g * 1.3), min(1, b * 1.3))
            Line(points=[x + s * 0.1, y + s * 0.9, x + s * 0.9, y + s * 0.1])
        elif kind == "chain":
            Color(0.6, 0.6, 0.65)
            Ellipse(pos=(x + s * 0.25, y + s * 0.25), size=(s * 0.2, s * 0.2))
            Ellipse(pos=(x + s * 0.55, y + s * 0.55), size=(s * 0.2, s * 0.2))
        Color(0, 0, 0, 0.4)
        Line(rectangle=(x + 1, y + 1, s - 2, s - 2))

    def _draw_hero(self, ox, oy, cs):
        hx, hy = self.hero["x"], self.hero["y"]
        crouch = self.hero["crouch"]

        bx = ox + hx * cs
        by = oy + hy * cs
        height = cs if crouch else cs * 2

        Color(0.15, 0.35, 0.7)
        Rectangle(pos=(bx + cs * 0.15, by + cs * 0.05),
                  size=(cs * 0.7, height * 0.55))
        Color(0.95, 0.8, 0.6)
        head_y = by + height * 0.55
        head_size = cs * 0.45
        Ellipse(pos=(bx + cs * 0.275, head_y), size=(head_size, head_size))
        Color(1, 0.75, 0.1)
        Rectangle(pos=(bx + cs * 0.2, head_y + head_size * 0.55),
                  size=(cs * 0.6, head_size * 0.4))
        Ellipse(pos=(bx + cs * 0.2, head_y + head_size * 0.4),
                size=(cs * 0.6, head_size * 0.5))
        Color(0, 0, 0)
        eye_x = bx + (cs * 0.6 if self.hero["dir"] > 0 else cs * 0.3)
        Ellipse(pos=(eye_x, head_y + head_size * 0.15),
                size=(cs * 0.08, cs * 0.08))


# ----------------------------- БОКОВАЯ ПАНЕЛЬ -----------------------------
class SidePanel(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.padding = 10
        self.spacing = 8

        with self.canvas.before:
            Color(0.05, 0.05, 0.07)
            self.bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd, size=self._upd)

        self.title = Label(text="[b]TETRILLER[/b]", markup=True,
                           font_size=22, color=(1, 0.75, 0.1, 1),
                           size_hint=(1, 0.15))
        self.score_lbl = Label(text="Score: 0", font_size=18,
                               color=(1, 1, 1, 1), size_hint=(1, 0.1))
        self.level_lbl = Label(text="Level: 1", font_size=16,
                               color=(0.7, 0.9, 1, 1), size_hint=(1, 0.1))
        self.lives_lbl = Label(text="Lives: <3<3<3", font_size=16,
                               color=(1, 0.4, 0.4, 1), size_hint=(1, 0.1))
        self.next_lbl = Label(text="Next:", font_size=16,
                              color=(0.8, 0.8, 0.8, 1), size_hint=(1, 0.08))
        self.next_box = Widget(size_hint=(1, 0.25))
        self.help = Label(
            text="[size=12]<-(влево).->(вправо) двигать\n->(вверх) повернуть\n->(вниз) ускорить\nSpace — drop\nP — пауза[/size]",
            markup=True, color=(0.7, 0.7, 0.7, 1), size_hint=(1, 0.22))

        for w in (self.title, self.score_lbl, self.level_lbl, self.lives_lbl,
                  self.next_lbl, self.next_box, self.help):
            self.add_widget(w)

        self.next_box.bind(pos=lambda *a: self.draw_next(self._next_shape),
                           size=lambda *a: self.draw_next(self._next_shape))
        self._next_shape = "I"

    def _upd(self, *a):
        self.bg.pos = self.pos
        self.bg.size = self.size

    def draw_next(self, shape_key):
        self._next_shape = shape_key
        self.next_box.canvas.clear()
        if not shape_key:
            return
        cells = SHAPES[shape_key]["cells"]
        color = SHAPES[shape_key]["color"]
        max_x = max(c[0] for c in cells) + 1
        max_y = max(c[1] for c in cells) + 1
        cs = min(self.next_box.width / max(max_x, 4),
                 self.next_box.height / max(max_y, 4)) * 0.7
        ox = self.next_box.x + (self.next_box.width - cs * max_x) / 2
        oy = self.next_box.y + (self.next_box.height - cs * max_y) / 2
        with self.next_box.canvas:
            Color(*color)
            for (cx, cy) in cells:
                Rectangle(pos=(ox + cx * cs, oy + cy * cs),
                          size=(cs - 2, cs - 2))


# ----------------------------- ЭКРАН GAME OVER -----------------------------
class GameOverOverlay(RelativeLayout):
    def __init__(self, on_restart, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(0, 0, 0, 0.75)
            self.bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd, size=self._upd)

        self.box = BoxLayout(orientation="vertical", spacing=20,
                             size_hint=(0.6, 0.5),
                             pos_hint={"center_x": 0.5, "center_y": 0.5})
        self.box.add_widget(Label(text="[b]GAME OVER[/b]", markup=True,
                                  font_size=36, color=(1, 0.3, 0.3, 1)))
        btn = Button(text="New Game", font_size=24,
                     background_color=(0.2, 0.5, 0.8, 1))
        btn.bind(on_press=lambda *a: on_restart())
        self.box.add_widget(btn)
        self.add_widget(self.box)

    def _upd(self, *a):
        self.bg.pos = self.pos
        self.bg.size = self.size


# ----------------------------- ГЛАВНОЕ ПРИЛОЖЕНИЕ -----------------------------
class TetrillerRoot(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.score = 0
        self.lives = 3
        self.level = 1
        self.overlay = None

        self.game = TetrillerWidget(self, size_hint=(0.7, 1))
        self.panel = SidePanel(size_hint=(0.3, 1))
        self.add_widget(self.game)
        self.add_widget(self.panel)

        self._keyboard = Window.request_keyboard(self._kb_closed, self)
        self._keyboard.bind(on_key_down=self._on_key_down)
        self._keyboard.bind(on_key_up=self._on_key_up)

        Clock.schedule_interval(self.update, 1 / 60)

    def _kb_closed(self):
        if self._keyboard:
            self._keyboard.unbind(on_key_down=self._on_key_down)
            self._keyboard.unbind(on_key_up=self._on_key_up)
            self._keyboard = None

    def _on_key_down(self, keyboard, keycode, text, modifiers):
        key = keycode[1]
        if key == "left":
            self.game.move(-1)
        elif key == "right":
            self.game.move(1)
        elif key in ("up", "x"):
            self.game.rotate()
        elif key == "down":
            self.game.soft_drop = True
        elif key == "spacebar":
            self.game.hard_drop()
        elif key == "p":
            self.game.paused = not self.game.paused
        elif key == "enter" and self.game.game_over:
            self.new_game()
        return True

    def _on_key_up(self, keyboard, keycode):
        if keycode[1] == "down":
            self.game.soft_drop = False
        return True

    def add_points(self, n):
        self.score += n
        self.panel.score_lbl.text = f"Score: {self.score}"

    def lose_life(self):
        self.lives -= 1
        self.panel.lives_lbl.text = "Lives: " + ("<3" * max(self.lives, 0))
        if self.lives <= 0:
            self.show_game_over()
        else:
            Clock.schedule_once(lambda dt: self._reset_field(), 0.8)

    def _reset_field(self):
        self.game.grid = [[None for _ in range(COLS)] for _ in range(ROWS)]
        self.game.hero = {"x": COLS // 2, "dir": 1, "crouch": False, "y": 0}
        self.game.game_over = False
        self.game.cur = None
        self.game.spawn_piece()

    def next_level(self):
        self.level += 1
        self.panel.level_lbl.text = f"Level: {self.level}"
        self.game.fall_speed = max(0.1, 0.6 - (self.level - 1) * 0.05)

    def show_game_over(self):
        if not self.overlay:
            self.overlay = GameOverOverlay(on_restart=self.new_game)
            Window.add_widget(self.overlay)
            self.overlay.size = Window.size
            self.overlay.pos = (0, 0)
            Window.bind(size=lambda *a: setattr(self.overlay, "size", Window.size))

    def new_game(self):
        if self.overlay:
            Window.remove_widget(self.overlay)
            self.overlay = None
        self.score = 0
        self.lives = 3
        self.level = 1
        self.panel.score_lbl.text = "Score: 0"
        self.panel.level_lbl.text = "Level: 1"
        self.panel.lives_lbl.text = "Lives: ♥♥♥"
        self.game.fall_speed = 0.6
        self._reset_field()

    def update(self, dt):
        self.game.tick(dt)
        self.panel.draw_next(self.game.next_shape)


class TetrillerApp(App):
    title = "Tetriller"

    def build(self):
        Window.size = (700, 800)
        Window.clearcolor = (0.02, 0.02, 0.03, 1)
        return TetrillerRoot()


if __name__ == "__main__":
    TetrillerApp().run()
