#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
物品位置管理工具 - Android 版 (Flet)
功能与桌面版 item_finder.py 完全一致
"""

import flet as ft
import sqlite3
import os
import shutil
from datetime import datetime, timedelta

# ============ 配置 ============
APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "items.db")
PHOTO_DIR = os.path.join(APP_DIR, "photos")

# ============ 数据库操作（复用桌面版逻辑） ============
def init_db():
    """初始化数据库"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        location TEXT NOT NULL,
        description TEXT,
        category TEXT DEFAULT '其他',
        photo_path TEXT,
        is_pinned INTEGER DEFAULT 0,
        search_count INTEGER DEFAULT 0,
        last_viewed TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS loans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER,
        lent_to TEXT NOT NULL,
        lent_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expected_return TIMESTAMP,
        returned INTEGER DEFAULT 0,
        FOREIGN KEY (item_id) REFERENCES items(id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS reminders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER,
        reminder_type TEXT,
        reminder_date TIMESTAMP,
        note TEXT,
        FOREIGN KEY (item_id) REFERENCES items(id)
    )''')
    conn.commit()
    conn.close()

class DB:
    """数据库操作类"""
    @staticmethod
    def get_conn():
        return sqlite3.connect(DB_PATH)

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
        c.execute('''INSERT INTO items (name, location, description, category, photo_path)
                     VALUES (?, ?, ?, ?, ?)''',
                  (name, location, description, category, photo_path))
        conn.commit()
        item_id = c.lastrowid
        conn.close()
        return item_id

    @staticmethod
    def update_item(item_id, name, location, description, category):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''UPDATE items SET name=?, location=?, description=?, category=?
                     WHERE id=?''',
                  (name, location, description, category, item_id))
        conn.commit()
        conn.close()

    @staticmethod
    def delete_item(item_id):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT photo_path FROM items WHERE id = ?", (item_id,))
        result = c.fetchone()
        if result and result[0] and os.path.exists(result[0]):
            try:
                os.remove(result[0])
            except:
                pass
        c.execute("DELETE FROM items WHERE id = ?", (item_id,))
        c.execute("DELETE FROM loans WHERE item_id = ?", (item_id,))
        c.execute("DELETE FROM reminders WHERE item_id = ?", (item_id,))
        conn.commit()
        conn.close()

    @staticmethod
    def view_item(item_id):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE items SET search_count = search_count + 1, last_viewed = CURRENT_TIMESTAMP WHERE id = ?", (item_id,))
        conn.commit()
        conn.close()

    @staticmethod
    def toggle_pin(item_id):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE items SET is_pinned = 1 - is_pinned WHERE id = ?", (item_id,))
        conn.commit()
        conn.close()

    @staticmethod
    def get_stats():
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM items")
        total = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM items WHERE is_pinned = 1")
        pinned = c.fetchone()[0]
        c.execute("SELECT SUM(search_count) FROM items")
        total_searches = c.fetchone()[0] or 0
        c.execute("SELECT category, COUNT(*) FROM items GROUP BY category ORDER BY COUNT(*) DESC")
        categories = c.fetchall()
        c.execute("SELECT name, search_count FROM items ORDER BY search_count DESC LIMIT 10")
        top_searched = c.fetchall()
        conn.close()
        return total, pinned, total_searches, categories, top_searched

    @staticmethod
    def get_loans():
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''SELECT l.id, i.name, l.lent_to, l.lent_date, l.expected_return
                     FROM loans l JOIN items i ON l.item_id = i.id
                     WHERE l.returned = 0 ORDER BY l.lent_date DESC''')
        rows = c.fetchall()
        conn.close()
        return rows

    @staticmethod
    def add_loan(item_id, lent_to, expected_return):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''INSERT INTO loans (item_id, lent_to, expected_return)
                     VALUES (?, ?, ?)''', (item_id, lent_to, expected_return or None))
        conn.commit()
        conn.close()

    @staticmethod
    def mark_returned(loan_id):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE loans SET returned = 1 WHERE id = ?", (loan_id,))
        conn.commit()
        conn.close()

    @staticmethod
    def get_reminders():
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''SELECT r.id, i.name, r.reminder_type, r.reminder_date, r.note
                     FROM reminders r JOIN items i ON r.item_id = i.id
                     WHERE r.reminder_date >= date('now') OR r.reminder_date IS NULL
                     ORDER BY r.reminder_date''')
        rows = c.fetchall()
        conn.close()
        return rows

    @staticmethod
    def add_reminder(item_id, reminder_type, reminder_date, note):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''INSERT INTO reminders (item_id, reminder_type, reminder_date, note)
                     VALUES (?, ?, ?, ?)''',
                  (item_id, reminder_type, reminder_date, note))
        conn.commit()
        conn.close()

    @staticmethod
    def delete_reminder(rem_id):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM reminders WHERE id = ?", (rem_id,))
        conn.commit()
        conn.close()


# ============ Flet 应用 ============
class ItemFinderApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "物品位置管理器"
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.padding = 0
        self.page.scroll = ft.ScrollMode.AUTO

        # 确保目录存在
        os.makedirs(PHOTO_DIR, exist_ok=True)
        init_db()

        # 状态
        self.current_view = "all"
        self.search_text = ""
        self.selected_category = "全部"

        # 分类列表
        self.categories = ["全部", "证件", "电子设备", "衣物", "药品", "书籍", "季节性物品", "其他"]

        self.build_ui()
        self.load_items()

    def build_ui(self):
        """构建主界面"""
        # 搜索栏
        self.search_field = ft.TextField(
            hint_text="搜索物品名称、位置、描述...",
            prefix_icon=ft.icons.SEARCH,
            on_change=self.on_search,
            expand=True,
        )

        # 分类下拉
        self.category_dropdown = ft.Dropdown(
            options=[ft.dropdown.Option(c) for c in self.categories],
            value="全部",
            width=120,
            on_change=self.on_category_change,
        )

        # 顶部栏
        top_bar = ft.Row(
            [
                self.search_field,
                self.category_dropdown,
                ft.IconButton(
                    icon=ft.icons.ADD_CIRCLE,
                    icon_color=ft.colors.BLUE,
                    icon_size=32,
                    on_click=self.show_add_dialog,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        # 内容列表
        self.content_list = ft.ListView(expand=True, spacing=10, padding=10)

        # 底部导航
        self.nav_bar = ft.NavigationBar(
            selected_index=0,
            on_change=self.on_nav_change,
            destinations=[
                ft.NavigationBarDestination(icon=ft.icons.LIST, label="全部"),
                ft.NavigationBarDestination(icon=ft.icons.STAR, label="置顶"),
                ft.NavigationBarDestination(icon=ft.icons.ACCESS_TIME, label="最近"),
                ft.NavigationBarDestination(icon=ft.icons.BAR_CHART, label="统计"),
                ft.NavigationBarDestination(icon=ft.icons.SEND, label="借出"),
                ft.NavigationBarDestination(icon=ft.icons.ALARM, label="提醒"),
            ],
        )

        self.page.add(
            ft.Column(
                [
                    ft.Container(content=top_bar, padding=10),
                    ft.Divider(height=1),
                    ft.Container(content=self.content_list, expand=True),
                    self.nav_bar,
                ],
                expand=True,
            )
        )

    def on_search(self, e):
        self.search_text = e.control.value
        self.load_items()

    def on_category_change(self, e):
        self.selected_category = e.control.value
        self.load_items()

    def on_nav_change(self, e):
        views = ["all", "pinned", "recent", "stats", "loaned", "reminders"]
        self.current_view = views[e.control.selected_index]
        self.load_items()

    def load_items(self):
        self.content_list.controls.clear()

        if self.current_view == "stats":
            self.show_stats()
        elif self.current_view == "loaned":
            self.show_loaned()
        elif self.current_view == "reminders":
            self.show_reminders()
        else:
            self.show_item_list()

        self.page.update()

    def show_item_list(self):
        items = DB.get_items(self.current_view, self.search_text, self.selected_category)
        if not items:
            self.content_list.controls.append(
                ft.Container(
                    content=ft.Text("暂无物品，点击右上角 + 添加吧！", color=ft.colors.GREY, size=16),
                    alignment=ft.alignment.center,
                    padding=50,
                )
            )
            return

        for item in items:
            card = self.create_item_card(item)
            self.content_list.controls.append(card)

    def create_item_card(self, item):
        item_id, name, location, description, category, photo_path, is_pinned, search_count, last_viewed, created_at = item

        # 照片显示
        photo_widget = ft.Icon(ft.icons.PHOTO, size=60, color=ft.colors.GREY_400)
        if photo_path and os.path.exists(photo_path):
            photo_widget = ft.Image(src=photo_path, width=80, height=80, fit=ft.ImageFit.COVER, border_radius=8)

        # 置顶图标
        pin_icon = ft.Icon(ft.icons.STAR, color=ft.colors.AMBER, size=20) if is_pinned else ft.Container(width=20)

        # 高频提醒
        warning = ft.Text("⚠️ 经常找不到！", color=ft.colors.RED, size=12) if search_count >= 5 else ft.Container()

        # 统计文本
        stats_text = f"查找 {search_count} 次"
        if last_viewed:
            stats_text += f"  |  最近：{last_viewed[:10]}"

        card = ft.Card(
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                photo_widget,
                                ft.Column(
                                    [
                                        ft.Row([pin_icon, ft.Text(name, size=16, weight=ft.FontWeight.BOLD)]),
                                        ft.Text(f"🏷 {category}", size=12, color=ft.colors.BLUE),
                                        ft.Text(f"📍 {location}", size=14, color=ft.colors.GREEN),
                                        ft.Text(description or "", size=12, color=ft.colors.GREY_700) if description else ft.Container(),
                                        ft.Text(stats_text, size=11, color=ft.colors.GREY),
                                        warning,
                                        ft.Row(
                                            [
                                                ft.TextButton("置顶" if not is_pinned else "取消置顶", on_click=lambda e, i=item_id: self.toggle_pin(i)),
                                                ft.TextButton("查看", on_click=lambda e, i=item_id: self.view_item(i)),
                                                ft.TextButton("编辑", on_click=lambda e, i=item_id: self.show_edit_dialog(i)),
                                                ft.TextButton("借出", on_click=lambda e, i=item_id: self.show_lend_dialog(i)),
                                                ft.TextButton("提醒", on_click=lambda e, i=item_id: self.show_reminder_dialog(i)),
                                                ft.TextButton("删除", on_click=lambda e, i=item_id: self.delete_item(i)),
                                            ],
                                            wrap=True,
                                        ),
                                    ],
                                    expand=True,
                                    spacing=2,
                                ),
                            ],
                            spacing=10,
                        ),
                    ],
                ),
                padding=15,
            ),
        )
        return card

    def show_stats(self):
        total, pinned, total_searches, categories, top_searched = DB.get_stats()

        self.content_list.controls.append(ft.Text("📊 物品统计", size=20, weight=ft.FontWeight.BOLD))
        self.content_list.controls.append(ft.Text(f"总物品数：{total}"))
        self.content_list.controls.append(ft.Text(f"置顶物品：{pinned}"))
        self.content_list.controls.append(ft.Text(f"总查找次数：{total_searches}"))
        self.content_list.controls.append(ft.Divider())

        self.content_list.controls.append(ft.Text("分类分布", size=16, weight=ft.FontWeight.BOLD))
        for cat, count in categories:
            self.content_list.controls.append(ft.Text(f"{cat}: {count} 个"))

        self.content_list.controls.append(ft.Divider())
        self.content_list.controls.append(ft.Text("🏆 查找次数最多的物品", size=16, weight=ft.FontWeight.BOLD))
        for name, count in top_searched:
            if count > 0:
                color = ft.colors.RED if count >= 5 else ft.colors.BLACK
                self.content_list.controls.append(ft.Text(f"{name}: {count} 次", color=color))

    def show_loaned(self):
        loans = DB.get_loans()
        self.content_list.controls.append(ft.Text("📤 借出记录", size=20, weight=ft.FontWeight.BOLD))

        if not loans:
            self.content_list.controls.append(ft.Text("没有借出中的物品", color=ft.colors.GREY))
            return

        for loan_id, item_name, lent_to, lent_date, expected_return in loans:
            card = ft.Card(
                content=ft.Container(
                    content=ft.Column(
                        [
                            ft.Text(f"物品：{item_name}", weight=ft.FontWeight.BOLD),
                            ft.Text(f"借给：{lent_to}"),
                            ft.Text(f"借出时间：{lent_date[:10]}"),
                            ft.Text(f"预计归还：{expected_return[:10] if expected_return else '未设置'}", color=ft.colors.ORANGE),
                            ft.ElevatedButton("标记已归还", on_click=lambda e, lid=loan_id: self.mark_returned(lid)),
                        ],
                    ),
                    padding=15,
                ),
            )
            self.content_list.controls.append(card)

    def show_reminders(self):
        reminders = DB.get_reminders()
        self.content_list.controls.append(ft.Text("⏰ 提醒列表", size=20, weight=ft.FontWeight.BOLD))

        if not reminders:
            self.content_list.controls.append(ft.Text("暂无提醒", color=ft.colors.GREY))
            return

        for rem_id, item_name, rem_type, rem_date, note in reminders:
            card = ft.Card(
                content=ft.Container(
                    content=ft.Column(
                        [
                            ft.Text(f"物品：{item_name}", weight=ft.FontWeight.BOLD),
                            ft.Text(f"类型：{rem_type}"),
                            ft.Text(f"提醒日期：{rem_date[:10] if rem_date else '未设置'}", color=ft.colors.ORANGE),
                            ft.Text(f"备注：{note}" if note else ""),
                            ft.TextButton("删除提醒", on_click=lambda e, rid=rem_id: self.delete_reminder(rid)),
                        ],
                    ),
                    padding=15,
                ),
            )
            self.content_list.controls.append(card)

    # ============ 操作 ============
    def view_item(self, item_id):
        DB.view_item(item_id)
        self.load_items()

    def toggle_pin(self, item_id):
        DB.toggle_pin(item_id)
        self.load_items()

    def delete_item(self, item_id):
        def confirm_delete(e):
            DB.delete_item(item_id)
            dialog.open = False
            self.page.update()
            self.load_items()

        dialog = ft.AlertDialog(
            title=ft.Text("确认删除"),
            content=ft.Text("确定要删除这个物品吗？"),
            actions=[
                ft.TextButton("取消", on_click=lambda e: setattr(dialog, 'open', False) or self.page.update()),
                ft.ElevatedButton("删除", color=ft.colors.RED, on_click=confirm_delete),
            ],
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def mark_returned(self, loan_id):
        DB.mark_returned(loan_id)
        self.load_items()

    def delete_reminder(self, rem_id):
        DB.delete_reminder(rem_id)
        self.load_items()

    # ============ 对话框 ============
    def show_add_dialog(self, e):
        name_field = ft.TextField(label="物品名称", autofocus=True)
        location_field = ft.TextField(label="位置")
        category_dropdown = ft.Dropdown(
            label="分类",
            options=[ft.dropdown.Option(c) for c in self.categories[1:]],
            value="其他",
        )
        desc_field = ft.TextField(label="描述", multiline=True, min_lines=2)
        photo_path = ft.TextField(label="照片路径（可选）", hint_text="手机端请填写路径或留空")

        def save(e):
            name = name_field.value.strip()
            location = location_field.value.strip()
            if not name or not location:
                self.page.snack_bar = ft.SnackBar(ft.Text("名称和位置不能为空！"))
                self.page.snack_bar.open = True
                self.page.update()
                return
            DB.add_item(name, location, desc_field.value, category_dropdown.value, photo_path.value or None)
            dialog.open = False
            self.page.update()
            self.load_items()

        dialog = ft.AlertDialog(
            title=ft.Text("新增物品"),
            content=ft.Column([name_field, location_field, category_dropdown, desc_field, photo_path], tight=True, spacing=10),
            actions=[
                ft.TextButton("取消", on_click=lambda e: setattr(dialog, 'open', False) or self.page.update()),
                ft.ElevatedButton("保存", on_click=save),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def show_edit_dialog(self, item_id):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT * FROM items WHERE id = ?", (item_id,))
        item = c.fetchone()
        conn.close()
        if not item:
            return

        _, name, location, description, category, photo_path, is_pinned, search_count, last_viewed, created_at = item

        name_field = ft.TextField(label="物品名称", value=name)
        location_field = ft.TextField(label="位置", value=location)
        category_dropdown = ft.Dropdown(
            label="分类",
            options=[ft.dropdown.Option(c) for c in self.categories[1:]],
            value=category,
        )
        desc_field = ft.TextField(label="描述", value=description or "", multiline=True, min_lines=2)

        def save(e):
            DB.update_item(item_id, name_field.value.strip(), location_field.value.strip(),
                           desc_field.value, category_dropdown.value)
            dialog.open = False
            self.page.update()
            self.load_items()

        dialog = ft.AlertDialog(
            title=ft.Text(f"编辑：{name}"),
            content=ft.Column([name_field, location_field, category_dropdown, desc_field], tight=True, spacing=10),
            actions=[
                ft.TextButton("取消", on_click=lambda e: setattr(dialog, 'open', False) or self.page.update()),
                ft.ElevatedButton("保存", on_click=save),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def show_lend_dialog(self, item_id):
        lent_to_field = ft.TextField(label="借给谁", autofocus=True)
        return_field = ft.TextField(label="预计归还日期", hint_text="格式：2026-05-20（可选）")

        def save(e):
            lent_to = lent_to_field.value.strip()
            if not lent_to:
                self.page.snack_bar = ft.SnackBar(ft.Text("借给谁不能为空！"))
                self.page.snack_bar.open = True
                self.page.update()
                return
            expected = return_field.value.strip()
            if "可选" in expected:
                expected = None
            DB.add_loan(item_id, lent_to, expected)
            dialog.open = False
            self.page.update()
            self.load_items()

        dialog = ft.AlertDialog(
            title=ft.Text("借出记录"),
            content=ft.Column([lent_to_field, return_field], tight=True, spacing=10),
            actions=[
                ft.TextButton("取消", on_click=lambda e: setattr(dialog, 'open', False) or self.page.update()),
                ft.ElevatedButton("保存", on_click=save),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def show_reminder_dialog(self, item_id):
        type_dropdown = ft.Dropdown(
            label="提醒类型",
            options=[ft.dropdown.Option(t) for t in ["过期提醒", "电池更换", "维护提醒", "其他"]],
            value="过期提醒",
        )
        date_field = ft.TextField(label="提醒日期", value=datetime.now().strftime("%Y-%m-%d"))
        note_field = ft.TextField(label="备注", multiline=True, min_lines=2)

        def save(e):
            DB.add_reminder(item_id, type_dropdown.value, date_field.value.strip(), note_field.value)
            dialog.open = False
            self.page.update()
            self.load_items()

        dialog = ft.AlertDialog(
            title=ft.Text("添加提醒"),
            content=ft.Column([type_dropdown, date_field, note_field], tight=True, spacing=10),
            actions=[
                ft.TextButton("取消", on_click=lambda e: setattr(dialog, 'open', False) or self.page.update()),
                ft.ElevatedButton("保存", on_click=save),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()


def main(page: ft.Page):
    ItemFinderApp(page)


if __name__ == "__main__":
    ft.app(target=main)
