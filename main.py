#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
物品位置管理工具 - Android 版 (Kivy)
功能与桌面版 item_finder.py 完全一致
"""

import os
import sqlite3
from datetime import datetime

from kivy.app import App
from kivy.resources import resource_add_path
from kivy.core.text import LabelBase

# ============ 中文字体配置（替换默认 Roboto 字体） ============
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
resource_add_path(os.path.join(_APP_DIR, "fonts"))
LabelBase.register('Roboto', fn_regular='wqy-microhei.ttc')

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.image import Image
from kivy.uix.spinner import Spinner
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.graphics import Color, Rectangle

# ============ 配置 ============
APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "items.db")
PHOTO_DIR = os.path.join(APP_DIR, "photos")
os.makedirs(PHOTO_DIR, exist_ok=True)

# ============ 数据库 ============
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, location TEXT NOT NULL, description TEXT,
        category TEXT DEFAULT '其他', photo_path TEXT,
        is_pinned INTEGER DEFAULT 0, search_count INTEGER DEFAULT 0,
        last_viewed TIMESTAMP, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS loans (
        id INTEGER PRIMARY KEY AUTOINCREMENT, item_id INTEGER,
        lent_to TEXT NOT NULL, lent_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expected_return TIMESTAMP, returned INTEGER DEFAULT 0,
        FOREIGN KEY (item_id) REFERENCES items(id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS reminders (
        id INTEGER PRIMARY KEY AUTOINCREMENT, item_id INTEGER,
        reminder_type TEXT, reminder_date TIMESTAMP, note TEXT,
        FOREIGN KEY (item_id) REFERENCES items(id)
    )''')
    conn.commit()
    conn.close()

class DB:
    @staticmethod
    def get_items(view="all", search="", category="全部"):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        query = "SELECT * FROM items WHERE 1=1"
        params = []
        if view == "pinned":
            query += " AND is_pinned = 1"
        elif view == "recent":
            query += " AND last_viewed IS NOT NULL ORDER BY last_viewed DESC LIMIT 20"
        else:
            query += " ORDER BY is_pinned DESC, search_count DESC, name"
        if search:
            query += " AND (name LIKE ? OR location LIKE ? OR description LIKE ?)"
            params.extend([f'%{search}%'] * 3)
        if category != "全部":
            query += " AND category = ?"
            params.append(category)
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()
        return rows

    @staticmethod
    def add_item(name, location, description, category, photo_path=None):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('INSERT INTO items (name,location,description,category,photo_path) VALUES (?,?,?,?,?)',
                  (name, location, description, category, photo_path))
        conn.commit()
        item_id = c.lastrowid
        conn.close()
        return item_id

    @staticmethod
    def update_item(item_id, name, location, description, category):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('UPDATE items SET name=?,location=?,description=?,category=? WHERE id=?',
                  (name, location, description, category, item_id))
        conn.commit()
        conn.close()

    @staticmethod
    def delete_item(item_id):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT photo_path FROM items WHERE id=?", (item_id,))
        r = c.fetchone()
        if r and r[0] and os.path.exists(r[0]):
            try:
                os.remove(r[0])
            except:
                pass
        c.execute("DELETE FROM items WHERE id=?", (item_id,))
        c.execute("DELETE FROM loans WHERE item_id=?", (item_id,))
        c.execute("DELETE FROM reminders WHERE item_id=?", (item_id,))
        conn.commit()
        conn.close()

    @staticmethod
    def view_item(item_id):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE items SET search_count=search_count+1, last_viewed=CURRENT_TIMESTAMP WHERE id=?", (item_id,))
        conn.commit()
        conn.close()

    @staticmethod
    def toggle_pin(item_id):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE items SET is_pinned=1-is_pinned WHERE id=?", (item_id,))
        conn.commit()
        conn.close()

    @staticmethod
    def get_stats():
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM items")
        total = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM items WHERE is_pinned=1")
        pinned = c.fetchone()[0]
        c.execute("SELECT SUM(search_count) FROM items")
        total_searches = c.fetchone()[0] or 0
        c.execute("SELECT category, COUNT(*) FROM items GROUP BY category ORDER BY COUNT(*) DESC")
        cats = c.fetchall()
        c.execute("SELECT name, search_count FROM items ORDER BY search_count DESC LIMIT 10")
        top = c.fetchall()
        conn.close()
        return total, pinned, total_searches, cats, top

    @staticmethod
    def get_loans():
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''SELECT l.id, i.name, l.lent_to, l.lent_date, l.expected_return
                     FROM loans l JOIN items i ON l.item_id=i.id
                     WHERE l.returned=0 ORDER BY l.lent_date DESC''')
        rows = c.fetchall()
        conn.close()
        return rows

    @staticmethod
    def add_loan(item_id, lent_to, expected_return):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('INSERT INTO loans (item_id,lent_to,expected_return) VALUES (?,?,?)',
                  (item_id, lent_to, expected_return or None))
        conn.commit()
        conn.close()

    @staticmethod
    def mark_returned(loan_id):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE loans SET returned=1 WHERE id=?", (loan_id,))
        conn.commit()
        conn.close()

    @staticmethod
    def get_reminders():
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''SELECT r.id, i.name, r.reminder_type, r.reminder_date, r.note
                     FROM reminders r JOIN items i ON r.item_id=i.id
                     WHERE r.reminder_date>=date('now') OR r.reminder_date IS NULL
                     ORDER BY r.reminder_date''')
        rows = c.fetchall()
        conn.close()
        return rows

    @staticmethod
    def add_reminder(item_id, rem_type, rem_date, note):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('INSERT INTO reminders (item_id,reminder_type,reminder_date,note) VALUES (?,?,?,?)',
                  (item_id, rem_type, rem_date, note))
        conn.commit()
        conn.close()

    @staticmethod
    def delete_reminder(rem_id):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM reminders WHERE id=?", (rem_id,))
        conn.commit()
        conn.close()


# ============ Kivy UI ============
class Card(BoxLayout):
    """卡片组件"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = dp(10)
        self.spacing = dp(5)
        self.size_hint_y = None
        self.bind(minimum_height=self.setter('height'))
        with self.canvas.before:
            Color(0.95, 0.95, 0.95, 1)
            self.rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self.update_rect, size=self.update_rect)

    def update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size


class ItemCard(Card):
    def __init__(self, item, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        item_id, name, location, description, category, photo_path, is_pinned, search_count, last_viewed, created_at = item

        # 标题行
        title_box = BoxLayout(size_hint_y=None, height=dp(30))
        pin_text = "[color=FFD700]★[/color] " if is_pinned else ""
        title_label = Label(text=f"{pin_text}{name}", font_size=dp(16), bold=True, color=(0.1,0.1,0.1,1), halign='left', valign='middle')
        title_label.bind(size=title_label.setter('text_size'))
        title_box.add_widget(title_label)
        self.add_widget(title_box)

        # 分类
        self.add_widget(Label(text=f"分类: {category}", font_size=dp(12), color=(0.2,0.4,0.8,1), halign='left', size_hint_y=None, height=dp(20)))

        # 位置
        self.add_widget(Label(text=f"位置: {location}", font_size=dp(14), color=(0.2,0.6,0.2,1), halign='left', size_hint_y=None, height=dp(22)))

        # 描述
        if description:
            self.add_widget(Label(text=description, font_size=dp(12), color=(0.4,0.4,0.4,1), halign='left', size_hint_y=None, height=dp(20)))

        # 统计
        stats = f"查找 {search_count} 次"
        if last_viewed:
            stats += f" | 最近: {last_viewed[:10]}"
        if search_count >= 5:
            stats += " [color=FF0000]经常找不到![/color]"
        self.add_widget(Label(text=stats, font_size=dp(11), color=(0.5,0.5,0.5,1), halign='left', size_hint_y=None, height=dp(18), markup=True))

        # 按钮行
        btn_box = BoxLayout(size_hint_y=None, height=dp(35), spacing=dp(5))
        btn_box.add_widget(Button(text="置顶" if not is_pinned else "取消置顶", font_size=dp(10), on_press=lambda x: app.toggle_pin(item_id)))
        btn_box.add_widget(Button(text="查看", font_size=dp(10), background_color=(0.2,0.7,0.2,1), on_press=lambda x: app.view_item(item_id)))
        btn_box.add_widget(Button(text="编辑", font_size=dp(10), on_press=lambda x: app.show_edit(item_id)))
        btn_box.add_widget(Button(text="借出", font_size=dp(10), on_press=lambda x: app.show_lend(item_id)))
        btn_box.add_widget(Button(text="提醒", font_size=dp(10), on_press=lambda x: app.show_reminder(item_id)))
        btn_box.add_widget(Button(text="删除", font_size=dp(10), background_color=(0.9,0.2,0.2,1), on_press=lambda x: app.confirm_delete(item_id)))
        self.add_widget(btn_box)


class MainScreen(Screen):
    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        self.build_ui()

    def build_ui(self):
        root = BoxLayout(orientation='vertical')

        # 顶部搜索栏
        top = BoxLayout(size_hint_y=None, height=dp(50), padding=dp(5))
        self.search_input = TextInput(hint_text="搜索...", multiline=False, size_hint_x=0.7)
        self.search_input.bind(text=self.on_search)
        top.add_widget(self.search_input)

        self.category_spinner = Spinner(text="全部", values=["全部","证件","电子设备","衣物","药品","书籍","季节性物品","其他"], size_hint_x=0.3)
        self.category_spinner.bind(text=self.on_category)
        top.add_widget(self.category_spinner)
        root.add_widget(top)

        # 内容区
        self.content = GridLayout(cols=1, spacing=dp(10), size_hint_y=None)
        self.content.bind(minimum_height=self.content.setter('height'))
        scroll = ScrollView()
        scroll.add_widget(self.content)
        root.add_widget(scroll)

        # 底部导航
        nav = BoxLayout(size_hint_y=None, height=dp(50))
        nav.add_widget(Button(text="全部", on_press=lambda x: self.switch_view("all")))
        nav.add_widget(Button(text="置顶", on_press=lambda x: self.switch_view("pinned")))
        nav.add_widget(Button(text="最近", on_press=lambda x: self.switch_view("recent")))
        nav.add_widget(Button(text="统计", on_press=lambda x: self.switch_view("stats")))
        nav.add_widget(Button(text="借出", on_press=lambda x: self.switch_view("loaned")))
        nav.add_widget(Button(text="提醒", on_press=lambda x: self.switch_view("reminders")))
        root.add_widget(nav)

        # 添加按钮（浮动）
        add_btn = Button(text="+", font_size=dp(24), size_hint=(None,None), size=(dp(50),dp(50)),
                         pos_hint={'right':0.98, 'top':0.15},
                         background_color=(0.2,0.5,0.9,1))
        add_btn.bind(on_press=self.app.show_add)
        root.add_widget(add_btn)

        self.add_widget(root)
        self.current_view = "all"
        self.load_items()

    def on_search(self, instance, value):
        self.load_items()

    def on_category(self, instance, value):
        self.load_items()

    def switch_view(self, view):
        self.current_view = view
        self.load_items()

    def load_items(self):
        self.content.clear_widgets()
        view = self.current_view
        search = self.search_input.text
        category = self.category_spinner.text

        if view == "stats":
            self.show_stats()
        elif view == "loaned":
            self.show_loaned()
        elif view == "reminders":
            self.show_reminders()
        else:
            items = DB.get_items(view, search, category)
            if not items:
                self.content.add_widget(Label(text="暂无物品", font_size=dp(16), color=(0.5,0.5,0.5,1), size_hint_y=None, height=dp(100)))
            for item in items:
                card = ItemCard(item, self.app)
                self.content.add_widget(card)

    def show_stats(self):
        total, pinned, total_searches, cats, top = DB.get_stats()
        self.content.add_widget(Label(text="[b]物品统计[/b]", font_size=dp(18), markup=True, size_hint_y=None, height=dp(30)))
        self.content.add_widget(Label(text=f"总物品: {total}", size_hint_y=None, height=dp(22)))
        self.content.add_widget(Label(text=f"置顶: {pinned}", size_hint_y=None, height=dp(22)))
        self.content.add_widget(Label(text=f"总查找: {total_searches}", size_hint_y=None, height=dp(22)))
        self.content.add_widget(Label(text="[b]分类分布[/b]", font_size=dp(14), markup=True, size_hint_y=None, height=dp(25)))
        for cat, count in cats:
            self.content.add_widget(Label(text=f"{cat}: {count} 个", size_hint_y=None, height=dp(20)))
        self.content.add_widget(Label(text="[b]高频查找[/b]", font_size=dp(14), markup=True, size_hint_y=None, height=dp(25)))
        for name, count in top:
            if count > 0:
                color = "[color=FF0000]" if count >= 5 else ""
                end = "[/color]" if count >= 5 else ""
                self.content.add_widget(Label(text=f"{color}{name}: {count} 次{end}", markup=True, size_hint_y=None, height=dp(20)))

    def show_loaned(self):
        loans = DB.get_loans()
        self.content.add_widget(Label(text="[b]借出记录[/b]", font_size=dp(18), markup=True, size_hint_y=None, height=dp(30)))
        if not loans:
            self.content.add_widget(Label(text="没有借出中的物品", size_hint_y=None, height=dp(50)))
            return
        for lid, name, lent_to, lent_date, expected in loans:
            box = Card()
            box.add_widget(Label(text=f"物品: {name}", bold=True, size_hint_y=None, height=dp(22)))
            box.add_widget(Label(text=f"借给: {lent_to}", size_hint_y=None, height=dp(20)))
            box.add_widget(Label(text=f"借出: {lent_date[:10]}", size_hint_y=None, height=dp(20)))
            if expected:
                box.add_widget(Label(text=f"预计归还: {expected[:10]}", color=(0.9,0.5,0.1,1), size_hint_y=None, height=dp(20)))
            box.add_widget(Button(text="标记已归还", size_hint_y=None, height=dp(35), background_color=(0.2,0.7,0.2,1), on_press=lambda x, id=lid: self.app.mark_returned(id)))
            self.content.add_widget(box)

    def show_reminders(self):
        rems = DB.get_reminders()
        self.content.add_widget(Label(text="[b]提醒列表[/b]", font_size=dp(18), markup=True, size_hint_y=None, height=dp(30)))
        if not rems:
            self.content.add_widget(Label(text="暂无提醒", size_hint_y=None, height=dp(50)))
            return
        for rid, name, rtype, rdate, note in rems:
            box = Card()
            box.add_widget(Label(text=f"物品: {name}", bold=True, size_hint_y=None, height=dp(22)))
            box.add_widget(Label(text=f"类型: {rtype}", size_hint_y=None, height=dp(20)))
            if rdate:
                box.add_widget(Label(text=f"日期: {rdate[:10]}", color=(0.9,0.5,0.1,1), size_hint_y=None, height=dp(20)))
            if note:
                box.add_widget(Label(text=f"备注: {note}", size_hint_y=None, height=dp(20)))
            box.add_widget(Button(text="删除", size_hint_y=None, height=dp(35), background_color=(0.9,0.2,0.2,1), on_press=lambda x, id=rid: self.app.delete_reminder(id)))
            self.content.add_widget(box)


class ItemFinderApp(App):
    def build(self):
        Window.clearcolor = (1, 1, 1, 1)
        init_db()
        self.sm = ScreenManager()
        self.main_screen = MainScreen(self, name="main")
        self.sm.add_widget(self.main_screen)
        return self.sm

    def refresh(self):
        self.main_screen.load_items()

    def toggle_pin(self, item_id):
        DB.toggle_pin(item_id)
        self.refresh()

    def view_item(self, item_id):
        DB.view_item(item_id)
        self.refresh()

    def confirm_delete(self, item_id):
        def do_delete(instance):
            DB.delete_item(item_id)
            popup.dismiss()
            self.refresh()
        content = BoxLayout(orientation='vertical')
        content.add_widget(Label(text="确定删除这个物品吗？"))
        btn_box = BoxLayout(size_hint_y=None, height=dp(40))
        btn_box.add_widget(Button(text="取消", on_press=lambda x: popup.dismiss()))
        btn_box.add_widget(Button(text="删除", background_color=(0.9,0.2,0.2,1), on_press=do_delete))
        content.add_widget(btn_box)
        popup = Popup(title="确认删除", content=content, size_hint=(0.8,0.3))
        popup.open()

    def mark_returned(self, loan_id):
        DB.mark_returned(loan_id)
        self.refresh()

    def delete_reminder(self, rem_id):
        DB.delete_reminder(rem_id)
        self.refresh()

    def show_add(self, instance=None):
        self._show_item_dialog()

    def show_edit(self, item_id):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT * FROM items WHERE id=?", (item_id,))
        item = c.fetchone()
        conn.close()
        if item:
            self._show_item_dialog(item)

    def _show_item_dialog(self, item=None):
        is_edit = item is not None
        item_id = item[0] if item else None
        name_val = item[1] if item else ""
        loc_val = item[2] if item else ""
        desc_val = item[3] if item else ""
        cat_val = item[4] if item else "其他"

        content = BoxLayout(orientation='vertical', spacing=dp(5), padding=dp(10))
        name_input = TextInput(text=name_val, hint_text="物品名称", multiline=False)
        loc_input = TextInput(text=loc_val, hint_text="位置", multiline=False)
        cat_spinner = Spinner(text=cat_val, values=["证件","电子设备","衣物","药品","书籍","季节性物品","其他"])
        desc_input = TextInput(text=desc_val, hint_text="描述", multiline=True)
        photo_input = TextInput(hint_text="照片路径（可选）", multiline=False)

        content.add_widget(name_input)
        content.add_widget(loc_input)
        content.add_widget(cat_spinner)
        content.add_widget(desc_input)
        if not is_edit:
            content.add_widget(photo_input)

        def save(instance):
            name = name_input.text.strip()
            location = loc_input.text.strip()
            if not name or not location:
                return
            if is_edit:
                DB.update_item(item_id, name, location, desc_input.text, cat_spinner.text)
            else:
                photo = photo_input.text.strip() or None
                DB.add_item(name, location, desc_input.text, cat_spinner.text, photo)
            popup.dismiss()
            self.refresh()

        btn_box = BoxLayout(size_hint_y=None, height=dp(40))
        btn_box.add_widget(Button(text="取消", on_press=lambda x: popup.dismiss()))
        btn_box.add_widget(Button(text="保存", background_color=(0.2,0.7,0.2,1), on_press=save))
        content.add_widget(btn_box)

        popup = Popup(title="编辑物品" if is_edit else "新增物品", content=content, size_hint=(0.9,0.7))
        popup.open()

    def show_lend(self, item_id):
        content = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(5))
        to_input = TextInput(hint_text="借给谁", multiline=False)
        date_input = TextInput(hint_text="预计归还日期（可选）", multiline=False)
        content.add_widget(to_input)
        content.add_widget(date_input)

        def save(instance):
            lent_to = to_input.text.strip()
            if not lent_to:
                return
            expected = date_input.text.strip() or None
            DB.add_loan(item_id, lent_to, expected)
            popup.dismiss()
            self.refresh()

        btn_box = BoxLayout(size_hint_y=None, height=dp(40))
        btn_box.add_widget(Button(text="取消", on_press=lambda x: popup.dismiss()))
        btn_box.add_widget(Button(text="保存", background_color=(0.2,0.7,0.2,1), on_press=save))
        content.add_widget(btn_box)

        popup = Popup(title="借出记录", content=content, size_hint=(0.8,0.4))
        popup.open()

    def show_reminder(self, item_id):
        content = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(5))
        type_spinner = Spinner(text="过期提醒", values=["过期提醒","电池更换","维护提醒","其他"])
        date_input = TextInput(text=datetime.now().strftime("%Y-%m-%d"), hint_text="提醒日期")
        note_input = TextInput(hint_text="备注", multiline=True)
        content.add_widget(type_spinner)
        content.add_widget(date_input)
        content.add_widget(note_input)

        def save(instance):
            DB.add_reminder(item_id, type_spinner.text, date_input.text.strip(), note_input.text)
            popup.dismiss()
            self.refresh()

        btn_box = BoxLayout(size_hint_y=None, height=dp(40))
        btn_box.add_widget(Button(text="取消", on_press=lambda x: popup.dismiss()))
        btn_box.add_widget(Button(text="保存", background_color=(0.2,0.7,0.2,1), on_press=save))
        content.add_widget(btn_box)

        popup = Popup(title="添加提醒", content=content, size_hint=(0.8,0.5))
        popup.open()


if __name__ == '__main__':
    ItemFinderApp().run()
