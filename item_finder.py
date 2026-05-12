#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
物品位置管理工具 - 专治丢三落四
功能：记录物品位置、搜索、置顶、统计、借出管理、提醒
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import os
import json
from datetime import datetime, timedelta
from PIL import Image, ImageTk
import shutil

# 配置
APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "items.db")
PHOTO_DIR = os.path.join(APP_DIR, "photos")
THUMB_SIZE = (120, 120)

def init_db():
    """初始化数据库"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 物品表
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
    
    # 借出记录表
    c.execute('''CREATE TABLE IF NOT EXISTS loans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER,
        lent_to TEXT NOT NULL,
        lent_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expected_return TIMESTAMP,
        returned INTEGER DEFAULT 0,
        FOREIGN KEY (item_id) REFERENCES items(id)
    )''')
    
    # 提醒表
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

class ItemManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("📦 物品位置管理器 - 再也不怕找不到")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)
        
        # 确保照片目录存在
        os.makedirs(PHOTO_DIR, exist_ok=True)
        
        # 当前视图状态
        self.current_view = "all"  # all, pinned, recent, stats
        self.search_text = ""
        self.selected_category = "全部"
        
        # 图片缓存
        self.photo_cache = {}
        
        self.setup_ui()
        self.load_items()
    
    def setup_ui(self):
        """设置界面"""
        # 顶部搜索栏
        top_frame = tk.Frame(self.root, padx=10, pady=10)
        top_frame.pack(fill=tk.X)
        
        tk.Label(top_frame, text="🔍", font=("微软雅黑", 12)).pack(side=tk.LEFT)
        self.search_entry = tk.Entry(top_frame, font=("微软雅黑", 11), width=40)
        self.search_entry.pack(side=tk.LEFT, padx=5)
        self.search_entry.bind('<KeyRelease>', self.on_search)
        
        tk.Button(top_frame, text="搜索", command=self.load_items, 
                 bg="#4CAF50", fg="white", font=("微软雅黑", 10)).pack(side=tk.LEFT, padx=5)
        tk.Button(top_frame, text="➕ 新增物品", command=self.add_item_dialog,
                 bg="#2196F3", fg="white", font=("微软雅黑", 10)).pack(side=tk.RIGHT)
        
        # 分类筛选
        category_frame = tk.Frame(self.root, padx=10)
        category_frame.pack(fill=tk.X)
        
        tk.Label(category_frame, text="分类筛选:", font=("微软雅黑", 10)).pack(side=tk.LEFT)
        self.category_var = tk.StringVar(value="全部")
        categories = ["全部", "证件", "电子设备", "衣物", "药品", "书籍", "季节性物品", "其他"]
        category_menu = ttk.Combobox(category_frame, textvariable=self.category_var, 
                                     values=categories, width=15, state="readonly")
        category_menu.pack(side=tk.LEFT, padx=5)
        category_menu.bind('<<ComboboxSelected>>', self.on_category_change)
        
        # 视图切换按钮
        btn_frame = tk.Frame(self.root, padx=10, pady=5)
        btn_frame.pack(fill=tk.X)
        
        tk.Button(btn_frame, text="📋 全部", command=lambda: self.switch_view("all"),
                 font=("微软雅黑", 9)).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="⭐ 置顶", command=lambda: self.switch_view("pinned"),
                 font=("微软雅黑", 9)).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="👁 最近查看", command=lambda: self.switch_view("recent"),
                 font=("微软雅黑", 9)).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="📊 统计", command=lambda: self.switch_view("stats"),
                 font=("微软雅黑", 9)).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="📤 借出中", command=lambda: self.switch_view("loaned"),
                 font=("微软雅黑", 9)).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="⏰ 提醒", command=lambda: self.switch_view("reminders"),
                 font=("微软雅黑", 9)).pack(side=tk.LEFT, padx=2)
        
        # 主内容区 - 使用Canvas实现滚动
        self.canvas = tk.Canvas(self.root)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw", width=880)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 绑定鼠标滚轮
        self.canvas.bind_all("<MouseWheel>", self.on_mousewheel)
        
        # 状态栏
        self.status_bar = tk.Label(self.root, text="就绪", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def on_mousewheel(self, event):
        """鼠标滚轮滚动"""
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    
    def on_search(self, event):
        """搜索输入事件"""
        self.search_text = self.search_entry.get()
        self.load_items()
    
    def on_category_change(self, event):
        """分类切换事件"""
        self.selected_category = self.category_var.get()
        self.load_items()
    
    def switch_view(self, view_type):
        """切换视图"""
        self.current_view = view_type
        self.load_items()
    
    def load_items(self):
        """加载物品列表"""
        # 清空当前显示
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        if self.current_view == "stats":
            self.show_stats(c)
        elif self.current_view == "loaned":
            self.show_loaned_items(c)
        elif self.current_view == "reminders":
            self.show_reminders(c)
        else:
            self.show_item_list(c)
        
        conn.close()
    
    def show_item_list(self, c):
        """显示物品列表"""
        # 构建查询
        query = "SELECT * FROM items WHERE 1=1"
        params = []
        
        if self.current_view == "pinned":
            query += " AND is_pinned = 1"
        elif self.current_view == "recent":
            query += " AND last_viewed IS NOT NULL ORDER BY last_viewed DESC LIMIT 20"
        else:
            query += " ORDER BY is_pinned DESC, search_count DESC, name"
        
        if self.search_text:
            query += " AND (name LIKE ? OR location LIKE ? OR description LIKE ?)"
            params.extend([f'%{self.search_text}%'] * 3)
        
        if self.selected_category != "全部":
            query += " AND category = ?"
            params.append(self.selected_category)
        
        c.execute(query, params)
        items = c.fetchall()
        
        if not items:
            tk.Label(self.scrollable_frame, text="暂无物品，点击右上角添加吧！", 
                    font=("微软雅黑", 12), fg="gray", pady=50).pack()
            self.status_bar.config(text="共 0 个物品")
            return
        
        self.status_bar.config(text=f"共 {len(items)} 个物品")
        
        for item in items:
            self.create_item_card(item)
    
    def create_item_card(self, item):
        """创建物品卡片"""
        item_id, name, location, description, category, photo_path, is_pinned, search_count, last_viewed, created_at = item
        
        card = tk.Frame(self.scrollable_frame, relief=tk.RIDGE, borderwidth=1, padx=10, pady=10)
        card.pack(fill=tk.X, pady=5)
        
        # 左侧照片
        left_frame = tk.Frame(card)
        left_frame.pack(side=tk.LEFT, padx=5)
        
        if photo_path and os.path.exists(photo_path):
            try:
                img = Image.open(photo_path)
                img.thumbnail(THUMB_SIZE)
                photo = ImageTk.PhotoImage(img)
                self.photo_cache[item_id] = photo  # 保持引用
                tk.Label(left_frame, image=photo).pack()
            except:
                tk.Label(left_frame, text="📷", font=("微软雅黑", 24), width=8, height=4, bg="#f0f0f0").pack()
        else:
            tk.Label(left_frame, text="📷", font=("微软雅黑", 24), width=8, height=4, bg="#f0f0f0").pack()
        
        # 右侧信息
        right_frame = tk.Frame(card)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
        
        # 标题行
        title_frame = tk.Frame(right_frame)
        title_frame.pack(fill=tk.X)
        
        pin_icon = "⭐ " if is_pinned else ""
        title = tk.Label(title_frame, text=f"{pin_icon}{name}", font=("微软雅黑", 14, "bold"))
        title.pack(side=tk.LEFT)
        
        # 标签
        cat_label = tk.Label(title_frame, text=f"🏷 {category}", 
                            font=("微软雅黑", 9), fg="blue")
        cat_label.pack(side=tk.LEFT, padx=10)
        
        # 位置
        loc_label = tk.Label(right_frame, text=f"📍 位置：{location}", 
                            font=("微软雅黑", 11), fg="green")
        loc_label.pack(anchor=tk.W, pady=2)
        
        # 描述
        if description:
            desc_label = tk.Label(right_frame, text=f"📝 {description}", 
                                 font=("微软雅黑", 10), wraplength=500, justify=tk.LEFT)
            desc_label.pack(anchor=tk.W, pady=2)
        
        # 统计信息
        stats_text = f"🔍 查找 {search_count} 次"
        if last_viewed:
            stats_text += f"  |  最近查看：{last_viewed[:10]}"
        
        # 高频查找提醒
        if search_count >= 5:
            stats_text += "  ⚠️ 经常找不到！"
        
        stats_label = tk.Label(right_frame, text=stats_text, font=("微软雅黑", 9), fg="gray")
        stats_label.pack(anchor=tk.W, pady=2)
        
        # 按钮区
        btn_frame = tk.Frame(right_frame)
        btn_frame.pack(anchor=tk.W, pady=5)
        
        pin_text = "取消置顶" if is_pinned else "置顶"
        tk.Button(btn_frame, text=pin_text, command=lambda i=item_id: self.toggle_pin(i),
                 font=("微软雅黑", 9)).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="查看", command=lambda i=item_id: self.view_item(i),
                 font=("微软雅黑", 9), bg="#4CAF50", fg="white").pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="编辑", command=lambda i=item_id: self.edit_item(i),
                 font=("微软雅黑", 9)).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="借出", command=lambda i=item_id: self.lend_item(i),
                 font=("微软雅黑", 9)).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="提醒", command=lambda i=item_id: self.add_reminder(i),
                 font=("微软雅黑", 9)).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="删除", command=lambda i=item_id: self.delete_item(i),
                 font=("微软雅黑", 9), fg="red").pack(side=tk.LEFT, padx=2)
    
    def show_stats(self, c):
        """显示统计信息"""
        tk.Label(self.scrollable_frame, text="📊 物品统计", 
                font=("微软雅黑", 16, "bold"), pady=10).pack()
        
        # 总体统计
        c.execute("SELECT COUNT(*) FROM items")
        total = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM items WHERE is_pinned = 1")
        pinned = c.fetchone()[0]
        
        c.execute("SELECT SUM(search_count) FROM items")
        total_searches = c.fetchone()[0] or 0
        
        stats_frame = tk.Frame(self.scrollable_frame)
        stats_frame.pack(pady=10)
        
        tk.Label(stats_frame, text=f"总物品数：{total}", font=("微软雅黑", 12)).pack(anchor=tk.W)
        tk.Label(stats_frame, text=f"置顶物品：{pinned}", font=("微软雅黑", 12)).pack(anchor=tk.W)
        tk.Label(stats_frame, text=f"总查找次数：{total_searches}", font=("微软雅黑", 12)).pack(anchor=tk.W)
        
        # 分类统计
        tk.Label(self.scrollable_frame, text="分类分布", 
                font=("微软雅黑", 14, "bold"), pady=10).pack()
        
        c.execute("SELECT category, COUNT(*) FROM items GROUP BY category ORDER BY COUNT(*) DESC")
        for cat, count in c.fetchall():
            tk.Label(self.scrollable_frame, text=f"{cat}: {count} 个", 
                    font=("微软雅黑", 11)).pack(anchor=tk.W, padx=20)
        
        # 最常查找的物品
        tk.Label(self.scrollable_frame, text="🏆 查找次数最多的物品（你可能经常找不到它们）", 
                font=("微软雅黑", 14, "bold"), pady=10).pack()
        
        c.execute("SELECT name, search_count FROM items ORDER BY search_count DESC LIMIT 10")
        for name, count in c.fetchall():
            if count > 0:
                tk.Label(self.scrollable_frame, text=f"{name}: {count} 次", 
                        font=("微软雅黑", 11), fg="red" if count >= 5 else "black").pack(anchor=tk.W, padx=20)
        
        self.status_bar.config(text="统计视图")
    
    def show_loaned_items(self, c):
        """显示借出中的物品"""
        tk.Label(self.scrollable_frame, text="📤 借出记录", 
                font=("微软雅黑", 16, "bold"), pady=10).pack()
        
        c.execute('''SELECT l.id, i.name, l.lent_to, l.lent_date, l.expected_return 
                     FROM loans l JOIN items i ON l.item_id = i.id 
                     WHERE l.returned = 0 ORDER BY l.lent_date DESC''')
        loans = c.fetchall()
        
        if not loans:
            tk.Label(self.scrollable_frame, text="没有借出中的物品", 
                    font=("微软雅黑", 12), fg="gray").pack()
            return
        
        for loan_id, item_name, lent_to, lent_date, expected_return in loans:
            frame = tk.Frame(self.scrollable_frame, relief=tk.RIDGE, borderwidth=1, padx=10, pady=10)
            frame.pack(fill=tk.X, pady=5)
            
            tk.Label(frame, text=f"物品：{item_name}", font=("微软雅黑", 12, "bold")).pack(anchor=tk.W)
            tk.Label(frame, text=f"借给：{lent_to}", font=("微软雅黑", 11)).pack(anchor=tk.W)
            tk.Label(frame, text=f"借出时间：{lent_date[:10]}", font=("微软雅黑", 10)).pack(anchor=tk.W)
            if expected_return:
                tk.Label(frame, text=f"预计归还：{expected_return[:10]}", font=("微软雅黑", 10), fg="orange").pack(anchor=tk.W)
            
            tk.Button(frame, text="标记已归还", command=lambda lid=loan_id: self.mark_returned(lid),
                     font=("微软雅黑", 9), bg="#4CAF50", fg="white").pack(anchor=tk.W, pady=5)
        
        self.status_bar.config(text=f"借出中：{len(loans)} 件")
    
    def show_reminders(self, c):
        """显示提醒"""
        tk.Label(self.scrollable_frame, text="⏰ 提醒列表", 
                font=("微软雅黑", 16, "bold"), pady=10).pack()
        
        c.execute('''SELECT r.id, i.name, r.reminder_type, r.reminder_date, r.note 
                     FROM reminders r JOIN items i ON r.item_id = i.id 
                     WHERE r.reminder_date >= date('now') OR r.reminder_date IS NULL
                     ORDER BY r.reminder_date''')
        reminders = c.fetchall()
        
        if not reminders:
            tk.Label(self.scrollable_frame, text="暂无提醒", 
                    font=("微软雅黑", 12), fg="gray").pack()
            return
        
        for rem_id, item_name, rem_type, rem_date, note in reminders:
            frame = tk.Frame(self.scrollable_frame, relief=tk.RIDGE, borderwidth=1, padx=10, pady=10)
            frame.pack(fill=tk.X, pady=5)
            
            tk.Label(frame, text=f"物品：{item_name}", font=("微软雅黑", 12, "bold")).pack(anchor=tk.W)
            tk.Label(frame, text=f"类型：{rem_type}", font=("微软雅黑", 11)).pack(anchor=tk.W)
            if rem_date:
                tk.Label(frame, text=f"提醒日期：{rem_date[:10]}", font=("微软雅黑", 10), fg="orange").pack(anchor=tk.W)
            if note:
                tk.Label(frame, text=f"备注：{note}", font=("微软雅黑", 10)).pack(anchor=tk.W)
            
            tk.Button(frame, text="删除提醒", command=lambda rid=rem_id: self.delete_reminder(rid),
                     font=("微软雅黑", 9), fg="red").pack(anchor=tk.W, pady=5)
        
        self.status_bar.config(text=f"提醒数：{len(reminders)}")
    
    def view_item(self, item_id):
        """查看物品（增加搜索次数）"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE items SET search_count = search_count + 1, last_viewed = CURRENT_TIMESTAMP WHERE id = ?", (item_id,))
        conn.commit()
        conn.close()
        self.load_items()
    
    def toggle_pin(self, item_id):
        """切换置顶状态"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE items SET is_pinned = 1 - is_pinned WHERE id = ?", (item_id,))
        conn.commit()
        conn.close()
        self.load_items()
    
    def add_item_dialog(self):
        """添加物品对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("新增物品")
        dialog.geometry("500x450")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 表单
        tk.Label(dialog, text="物品名称：", font=("微软雅黑", 11)).pack(anchor=tk.W, padx=20, pady=(20,0))
        name_entry = tk.Entry(dialog, font=("微软雅黑", 11), width=40)
        name_entry.pack(anchor=tk.W, padx=20)
        
        tk.Label(dialog, text="位置：", font=("微软雅黑", 11)).pack(anchor=tk.W, padx=20, pady=(10,0))
        location_entry = tk.Entry(dialog, font=("微软雅黑", 11), width=40)
        location_entry.pack(anchor=tk.W, padx=20)
        
        tk.Label(dialog, text="分类：", font=("微软雅黑", 11)).pack(anchor=tk.W, padx=20, pady=(10,0))
        category_var = tk.StringVar(value="其他")
        categories = ["证件", "电子设备", "衣物", "药品", "书籍", "季节性物品", "其他"]
        ttk.Combobox(dialog, textvariable=category_var, values=categories, 
                    width=15, state="readonly").pack(anchor=tk.W, padx=20)
        
        tk.Label(dialog, text="描述：", font=("微软雅黑", 11)).pack(anchor=tk.W, padx=20, pady=(10,0))
        desc_entry = tk.Text(dialog, font=("微软雅黑", 10), width=40, height=3)
        desc_entry.pack(anchor=tk.W, padx=20)
        
        # 照片选择
        photo_path_var = tk.StringVar()
        tk.Label(dialog, text="照片：", font=("微软雅黑", 11)).pack(anchor=tk.W, padx=20, pady=(10,0))
        
        photo_frame = tk.Frame(dialog)
        photo_frame.pack(anchor=tk.W, padx=20)
        
        tk.Entry(photo_frame, textvariable=photo_path_var, font=("微软雅黑", 10), width=30).pack(side=tk.LEFT)
        tk.Button(photo_frame, text="选择照片", 
                 command=lambda: photo_path_var.set(filedialog.askopenfilename(
                     filetypes=[("图片", "*.jpg *.jpeg *.png *.gif")]) or "")).pack(side=tk.LEFT, padx=5)
        
        def save():
            name = name_entry.get().strip()
            location = location_entry.get().strip()
            if not name or not location:
                messagebox.showwarning("提示", "名称和位置不能为空！")
                return
            
            # 复制照片到应用目录
            photo_path = photo_path_var.get()
            if photo_path and os.path.exists(photo_path):
                ext = os.path.splitext(photo_path)[1]
                new_name = f"item_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
                new_path = os.path.join(PHOTO_DIR, new_name)
                shutil.copy2(photo_path, new_path)
                photo_path = new_path
            else:
                photo_path = None
            
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('''INSERT INTO items (name, location, description, category, photo_path)
                        VALUES (?, ?, ?, ?, ?)''',
                     (name, location, desc_entry.get("1.0", tk.END).strip(), 
                      category_var.get(), photo_path))
            conn.commit()
            conn.close()
            
            dialog.destroy()
            self.load_items()
            messagebox.showinfo("成功", "物品已添加！")
        
        tk.Button(dialog, text="保存", command=save, bg="#4CAF50", fg="white",
                 font=("微软雅黑", 11), width=15).pack(pady=20)
    
    def edit_item(self, item_id):
        """编辑物品"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT * FROM items WHERE id = ?", (item_id,))
        item = c.fetchone()
        conn.close()
        
        if not item:
            return
        
        item_id, name, location, description, category, photo_path, is_pinned, search_count, last_viewed, created_at = item
        
        dialog = tk.Toplevel(self.root)
        dialog.title(f"编辑：{name}")
        dialog.geometry("500x450")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 表单（预填充）
        tk.Label(dialog, text="物品名称：", font=("微软雅黑", 11)).pack(anchor=tk.W, padx=20, pady=(20,0))
        name_entry = tk.Entry(dialog, font=("微软雅黑", 11), width=40)
        name_entry.insert(0, name)
        name_entry.pack(anchor=tk.W, padx=20)
        
        tk.Label(dialog, text="位置：", font=("微软雅黑", 11)).pack(anchor=tk.W, padx=20, pady=(10,0))
        location_entry = tk.Entry(dialog, font=("微软雅黑", 11), width=40)
        location_entry.insert(0, location)
        location_entry.pack(anchor=tk.W, padx=20)
        
        tk.Label(dialog, text="分类：", font=("微软雅黑", 11)).pack(anchor=tk.W, padx=20, pady=(10,0))
        category_var = tk.StringVar(value=category)
        categories = ["证件", "电子设备", "衣物", "药品", "书籍", "季节性物品", "其他"]
        ttk.Combobox(dialog, textvariable=category_var, values=categories, 
                    width=15, state="readonly").pack(anchor=tk.W, padx=20)
        
        tk.Label(dialog, text="描述：", font=("微软雅黑", 11)).pack(anchor=tk.W, padx=20, pady=(10,0))
        desc_entry = tk.Text(dialog, font=("微软雅黑", 10), width=40, height=3)
        desc_entry.insert("1.0", description or "")
        desc_entry.pack(anchor=tk.W, padx=20)
        
        def save():
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('''UPDATE items SET name=?, location=?, description=?, category=?
                        WHERE id=?''',
                     (name_entry.get().strip(), location_entry.get().strip(),
                      desc_entry.get("1.0", tk.END).strip(), category_var.get(), item_id))
            conn.commit()
            conn.close()
            
            dialog.destroy()
            self.load_items()
            messagebox.showinfo("成功", "物品已更新！")
        
        tk.Button(dialog, text="保存", command=save, bg="#4CAF50", fg="white",
                 font=("微软雅黑", 11), width=15).pack(pady=20)
    
    def delete_item(self, item_id):
        """删除物品"""
        if not messagebox.askyesno("确认", "确定要删除这个物品吗？"):
            return
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT photo_path FROM items WHERE id = ?", (item_id,))
        result = c.fetchone()
        
        # 删除照片文件
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
        
        self.load_items()
        messagebox.showinfo("成功", "物品已删除！")
    
    def lend_item(self, item_id):
        """借出物品对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("借出记录")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        tk.Label(dialog, text="借给谁：", font=("微软雅黑", 11)).pack(anchor=tk.W, padx=20, pady=(20,0))
        lent_to_entry = tk.Entry(dialog, font=("微软雅黑", 11), width=30)
        lent_to_entry.pack(anchor=tk.W, padx=20)
        
        tk.Label(dialog, text="预计归还日期：", font=("微软雅黑", 11)).pack(anchor=tk.W, padx=20, pady=(10,0))
        return_entry = tk.Entry(dialog, font=("微软雅黑", 11), width=30)
        return_entry.insert(0, "(可选) 格式：2026-05-20")
        return_entry.pack(anchor=tk.W, padx=20)
        
        def save():
            lent_to = lent_to_entry.get().strip()
            if not lent_to:
                messagebox.showwarning("提示", "借给谁不能为空！")
                return
            
            expected_return = return_entry.get().strip()
            if "可选" in expected_return:
                expected_return = None
            
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('''INSERT INTO loans (item_id, lent_to, expected_return)
                        VALUES (?, ?, ?)''', (item_id, lent_to, expected_return))
            conn.commit()
            conn.close()
            
            dialog.destroy()
            messagebox.showinfo("成功", "借出记录已添加！")
        
        tk.Button(dialog, text="保存", command=save, bg="#4CAF50", fg="white",
                 font=("微软雅黑", 11), width=15).pack(pady=20)
    
    def mark_returned(self, loan_id):
        """标记已归还"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE loans SET returned = 1 WHERE id = ?", (loan_id,))
        conn.commit()
        conn.close()
        self.load_items()
        messagebox.showinfo("成功", "已标记为归还！")
    
    def add_reminder(self, item_id):
        """添加提醒"""
        dialog = tk.Toplevel(self.root)
        dialog.title("添加提醒")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        tk.Label(dialog, text="提醒类型：", font=("微软雅黑", 11)).pack(anchor=tk.W, padx=20, pady=(20,0))
        type_var = tk.StringVar(value="过期提醒")
        types = ["过期提醒", "电池更换", "维护提醒", "其他"]
        ttk.Combobox(dialog, textvariable=type_var, values=types, 
                    width=15, state="readonly").pack(anchor=tk.W, padx=20)
        
        tk.Label(dialog, text="提醒日期：", font=("微软雅黑", 11)).pack(anchor=tk.W, padx=20, pady=(10,0))
        date_entry = tk.Entry(dialog, font=("微软雅黑", 11), width=30)
        date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
        date_entry.pack(anchor=tk.W, padx=20)
        
        tk.Label(dialog, text="备注：", font=("微软雅黑", 11)).pack(anchor=tk.W, padx=20, pady=(10,0))
        note_entry = tk.Text(dialog, font=("微软雅黑", 10), width=30, height=3)
        note_entry.pack(anchor=tk.W, padx=20)
        
        def save():
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('''INSERT INTO reminders (item_id, reminder_type, reminder_date, note)
                        VALUES (?, ?, ?, ?)''',
                     (item_id, type_var.get(), date_entry.get().strip(),
                      note_entry.get("1.0", tk.END).strip()))
            conn.commit()
            conn.close()
            
            dialog.destroy()
            messagebox.showinfo("成功", "提醒已添加！")
        
        tk.Button(dialog, text="保存", command=save, bg="#4CAF50", fg="white",
                 font=("微软雅黑", 11), width=15).pack(pady=20)
    
    def delete_reminder(self, rem_id):
        """删除提醒"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM reminders WHERE id = ?", (rem_id,))
        conn.commit()
        conn.close()
        self.load_items()


def main():
    init_db()
    
    root = tk.Tk()
    
    # 设置 DPI 感知（Windows）
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass
    
    app = ItemManagerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
