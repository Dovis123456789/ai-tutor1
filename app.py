import streamlit as st
import time
import re
import bcrypt
import sqlite3
from datetime import datetime
from ai_tutor import AITutor
from worksheet_utils import create_worksheet_docx

# ========== 数据库初始化 ==========
def init_db():
    conn = sqlite3.connect('ai_tutor_users.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            role TEXT,
            content TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (username) REFERENCES users(username)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def register_user(username, password):
    conn = sqlite3.connect('ai_tutor_users.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, hash_password(password)))
        conn.commit()
        return True, "注册成功！"
    except sqlite3.IntegrityError:
        return False, "用户名已存在"
    finally:
        conn.close()

def login_user(username, password):
    conn = sqlite3.connect('ai_tutor_users.db')
    c = conn.cursor()
    c.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    if row and verify_password(password, row[0]):
        return True
    return False

def save_chat_message(username, role, content):
    conn = sqlite3.connect('ai_tutor_users.db')
    c = conn.cursor()
    c.execute("INSERT INTO chat_history (username, role, content) VALUES (?, ?, ?)",
              (username, role, content))
    conn.commit()
    conn.close()

def load_chat_history(username, limit=100):
    conn = sqlite3.connect('ai_tutor_users.db')
    c = conn.cursor()
    c.execute("""
        SELECT role, content FROM chat_history 
        WHERE username = ? 
        ORDER BY timestamp ASC 
        LIMIT ?
    """, (username, limit))
    rows = c.fetchall()
    conn.close()
    return [{"role": row[0], "content": row[1]} for row in rows]

def clear_chat_history(username):
    conn = sqlite3.connect('ai_tutor_users.db')
    c = conn.cursor()
    c.execute("DELETE FROM chat_history WHERE username = ?", (username,))
    conn.commit()
    conn.close()

st.set_page_config(
    page_title="AI 家教助手",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ========== 主题配置 ==========
if "theme" not in st.session_state:
    st.session_state.theme = "ocean"

def get_theme_css(theme):
    if theme == "ocean":
        return {
            "primary": "#42A5F5",
            "secondary": "#BBDEFB",
            "bg_main": "#E3F2FD",
            "bg_sidebar": "#FFFFFF",
            "user_bubble": "linear-gradient(135deg, #BBDEFB, #90CAF9)",
            "assistant_bubble": "#FFFFFF",
            "text_main": "#0D47A1",
            "text_light": "#5472AE",
            "border": "#64B5F6",
            "scrollbar": "#42A5F5",
            "bg_pattern": "radial-gradient(circle at 10% 20%, rgba(66,165,245,0.05) 2%, transparent 2.5%)",
            "avatar_user": "🧜‍♂️",
            "avatar_assistant": "🐠",
            "deco": "🌊",
            "glow": "none"
        }
    elif theme == "star":
        return {
            "primary": "#9575CD",
            "secondary": "#EDE7F6",
            "bg_main": "#F3E5F5",
            "bg_sidebar": "#FFFFFF",
            "user_bubble": "linear-gradient(135deg, #D1C4E9, #B39DDB)",
            "assistant_bubble": "#FFFFFF",
            "text_main": "#4A148C",
            "text_light": "#7B1FA2",
            "border": "#B39DDB",
            "scrollbar": "#9575CD",
            "bg_pattern": "radial-gradient(circle at 30% 40%, #E1BEE7 1.2px, transparent 1px)",
            "avatar_user": "👩‍🚀",
            "avatar_assistant": "⭐",
            "deco": "⭐",
            "glow": "none"
        }
    elif theme == "forest":
        return {
            "primary": "#4CAF50",
            "secondary": "#8D6E63",
            "bg_main": "#F5F5DC",
            "bg_sidebar": "#FFFFFF",
            "user_bubble": "linear-gradient(135deg, #C8E6C9, #A5D6A7)",
            "assistant_bubble": "#FFFFFF",
            "text_main": "#2E5C2E",
            "text_light": "#6D4C41",
            "border": "#A5D6A7",
            "scrollbar": "#4CAF50",
            "bg_pattern": "repeating-linear-gradient(0deg, rgba(76,175,80,0.03) 0px, rgba(76,175,80,0.03) 2px, transparent 2px, transparent 30px)",
            "avatar_user": "🌿",
            "avatar_assistant": "🍃",
            "deco": "🌳",
            "glow": "none"
        }
    else:  # peach
        return {
            "primary": "#F48FB1",
            "secondary": "#FFF3E0",
            "bg_main": "#FCE4EC",
            "bg_sidebar": "#FFFFFF",
            "user_bubble": "linear-gradient(135deg, #F8BBD0, #F48FB1)",
            "assistant_bubble": "#FFFFFF",
            "text_main": "#AD1457",
            "text_light": "#F8BBD0",
            "border": "#F48FB1",
            "scrollbar": "#F48FB1",
            "bg_pattern": "radial-gradient(circle at 20% 30%, #F8BBD0 1.2px, transparent 1px)",
            "avatar_user": "🍑",
            "avatar_assistant": "☁️",
            "deco": "🌸",
            "glow": "none"
        }

# ========== 全局 CSS + 移动端媒体查询 ==========
def apply_theme(theme):
    cfg = get_theme_css(theme)
    st.markdown(f"""
    <style>
        * {{
            box-sizing: border-box;
        }}
        .stApp {{
            background: {cfg["bg_main"]} {cfg["bg_pattern"]};
            background-attachment: fixed;
        }}
        .stApp header .stButton {{
            display: none !important;
        }}
        /* 标题区布局 */
        .title-container {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin: 0.5rem 1rem;
        }}
        .title-left {{
            flex: 1;
        }}
        .title-center {{
            flex: 3;
            text-align: center;
        }}
        .title-right {{
            flex: 1;
            display: flex;
            justify-content: flex-end;
            gap: 12px;
        }}
        .main-title {{
            font-size: 2rem;
            font-weight: bold;
            background: linear-gradient(120deg, {cfg["primary"]}, {cfg["secondary"]});
            -webkit-background-clip: text;
            background-clip: text;
            color: transparent;
            display: inline-block;
        }}
        .subtitle {{
            text-align: center;
            font-size: 0.85rem;
            color: {cfg["text_light"]};
            margin-top: -0.5rem;
            margin-bottom: 1rem;
        }}
        /* 圆形图标按钮 */
        .icon-button {{
            background: rgba(255,255,245,0.8);
            border: 1px solid {cfg["primary"]};
            border-radius: 50%;
            width: 40px;
            height: 40px;
            font-size: 1.5rem;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: all 0.2s ease;
            color: {cfg["primary"]};
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }}
        .icon-button:hover {{
            transform: scale(1.05);
            background-color: {cfg["primary"]};
            color: white;
            border-color: {cfg["primary"]};
        }}
        .icon-button:active {{
            transform: scale(0.98);
        }}
        /* 自定义 popover 内容（主题选择菜单） */
        .theme-popover {{
            position: absolute;
            background: white;
            border-radius: 20px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            padding: 0.5rem;
            min-width: 140px;
            z-index: 1001;
        }}
        .theme-option {{
            padding: 8px 12px;
            border-radius: 30px;
            cursor: pointer;
            transition: background 0.1s;
            font-size: 0.9rem;
        }}
        .theme-option:hover {{
            background: #f0f0f0;
        }}
        /* 聊天气泡等原有样式略... */
        .user-msg, .assistant-msg {{
            max-width: 80%;
            padding: 10px 18px;
            margin: 10px 0;
            border-radius: 24px;
            word-wrap: break-word;
            white-space: normal;
            border: 2px solid {cfg["border"]};
        }}
        .user-msg {{
            background: {cfg["user_bubble"]};
            border-radius: 24px 24px 8px 24px;
            margin-left: auto;
            color: {cfg["text_main"]};
        }}
        .assistant-msg {{
            background: {cfg["assistant_bubble"]};
            border-radius: 24px 24px 24px 8px;
            box-shadow: 2px 2px 6px rgba(0,0,0,0.05);
            color: {cfg["text_main"]};
        }}
        .stChatInput textarea {{
            border-radius: 40px !important;
            border: 2px dashed {cfg["primary"]} !important;
            background: {cfg["bg_sidebar"]} !important;
            padding: 10px 16px !important;
            font-size: 0.9rem;
        }}
        ::-webkit-scrollbar {{
            width: 6px;
        }}
        ::-webkit-scrollbar-track {{
            background: #F0F0F0;
        }}
        ::-webkit-scrollbar-thumb {{
            background: {cfg["scrollbar"]};
            border-radius: 10px;
        }}
        .floating-assistant {{
            position: fixed;
            bottom: 20px;
            right: 20px;
            font-size: 2.5rem;
            cursor: pointer;
            filter: drop-shadow(0 2px 4px rgba(0,0,0,0.1));
            transition: transform 0.2s;
            z-index: 1000;
        }}
        .floating-assistant:hover {{
            transform: scale(1.05);
        }}
        @media (max-width: 768px) {{
            .main-title {{
                font-size: 1.4rem;
            }}
            .subtitle {{
                font-size: 0.65rem;
            }}
            .icon-button {{
                width: 36px;
                height: 36px;
                font-size: 1.3rem;
            }}
            .user-msg, .assistant-msg {{
                max-width: 90%;
                padding: 8px 14px;
                font-size: 0.85rem;
            }}
            [data-testid="stSidebar"] {{
                width: 70vw !important;
                min-width: 200px !important;
                max-width: 280px !important;
            }}
            .sidebar-mask {{
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0,0,0,0.5);
                z-index: 999;
                display: none;
            }}
            .sidebar-mask.active {{
                display: block;
            }}
            .floating-assistant {{
                font-size: 2rem;
                bottom: 70px;
                right: 15px;
            }}
        }}
    </style>
    <div id="sidebarMask" class="sidebar-mask" onclick="closeSidebar()"></div>
    <script>
        function closeSidebar() {{
            const sidebar = document.querySelector('[data-testid="stSidebar"]');
            const mask = document.getElementById('sidebarMask');
            if (sidebar && sidebar.style.width !== '0px') {{
                const closeBtn = document.querySelector('[data-testid="stSidebarCollapse"]');
                if (closeBtn) closeBtn.click();
            }}
            if (mask) mask.classList.remove('active');
        }}
        const observer = new MutationObserver(function(mutations) {{
            const sidebar = document.querySelector('[data-testid="stSidebar"]');
            const mask = document.getElementById('sidebarMask');
            if (sidebar && mask) {{
                if (sidebar.offsetWidth > 0) {{
                    mask.classList.add('active');
                }} else {{
                    mask.classList.remove('active');
                }}
            }}
        }});
        observer.observe(document.body, {{ attributes: true, childList: true, subtree: true }});
    </script>
    """, unsafe_allow_html=True)

apply_theme(st.session_state.theme)
cfg = get_theme_css(st.session_state.theme)

# ========== 右上角功能区（HTML + JS） ==========
# 注意：由于 Streamlit 的 rerun 机制，主题切换需要使用 st.session_state 并重新运行。
# 我们用 st.popover 包装主题选择，并用自定义 CSS 美化触发按钮。
# 朗读按钮直接调用浏览器语音。

# 为了让右上角按钮与标题同一行，使用 columns 布局
col_left, col_center, col_right = st.columns([1, 3, 1])

with col_center:
    st.markdown(f"""
    <div style="text-align: center;">
        <span class="main-title">{cfg['deco']} AI 家教助手 {cfg['deco']}</span>
    </div>
    """, unsafe_allow_html=True)

with col_right:
    # 主题切换按钮（popover 触发）
    with st.popover("", help="切换主题"):
        st.markdown("### 选择主题")
        theme_opt = st.radio(
            "主题",
            options=["海洋冒险风", "星空梦幻风", "森林物语风", "蜜桃奶冻风"],
            index=["ocean", "star", "forest", "peach"].index(st.session_state.theme),
            label_visibility="collapsed",
            key="theme_radio"
        )
        theme_map = {"海洋冒险风": "ocean", "星空梦幻风": "star", "森林物语风": "forest", "蜜桃奶冻风": "peach"}
        new_theme = theme_map[theme_opt]
        if new_theme != st.session_state.theme:
            st.session_state.theme = new_theme
            st.rerun()
    # 朗读按钮
    if st.button("🔊", key="speak_top_btn", help="朗读AI最新回复"):
        # 获取最后一条 AI 消息
        last_assistant_msg = None
        for msg in reversed(st.session_state.messages):
            if msg["role"] == "assistant":
                last_assistant_msg = msg["content"]
                break
        if last_assistant_msg:
            # 使用浏览器语音合成
            safe_text = last_assistant_msg.replace("'", "\\'").replace("\n", " ")
            st.markdown(f"""
                <script>
                    var msg = '{safe_text}';
                    var utterance = new SpeechSynthesisUtterance(msg);
                    utterance.lang = 'zh-CN';
                    window.speechSynthesis.speak(utterance);
                </script>
            """, unsafe_allow_html=True)
            st.toast("正在朗读", icon="🔊")
        else:
            st.warning("还没有AI老师的回复，先问个问题吧～")

# 副标题独立一行
st.markdown(f'<div class="subtitle">🧸 让学习像玩游戏一样有趣 🎈</div>', unsafe_allow_html=True)

# ========== 初始化 session_state ==========
if "tutor" not in st.session_state:
    st.session_state.tutor = AITutor()
if "worksheet" not in st.session_state:
    st.session_state.worksheet = None
if "show_mistakes" not in st.session_state:
    st.session_state.show_mistakes = False
if "show_report" not in st.session_state:
    st.session_state.show_report = False
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = None
if "guest_count" not in st.session_state:
    st.session_state.guest_count = 0
if "show_login" not in st.session_state:
    st.session_state.show_login = False
if "messages" not in st.session_state:
    st.session_state.messages = []

# ========== 登录弹窗 ==========
if st.__version__ >= "1.33.0":
    @st.dialog("🎈 哎呀，需要登录啦～")
    def login_dialog():
        st.markdown("登录后可以无限使用，还能保存学习记录哦～")
        tab1, tab2 = st.tabs(["🔑 登录", "📝 注册"])
        with tab1:
            with st.form("login_form"):
                username = st.text_input("用户名")
                password = st.text_input("密码", type="password")
                if st.form_submit_button("登录"):
                    if login_user(username, password):
                        st.session_state.logged_in = True
                        st.session_state.username = username
                        st.session_state.guest_count = 0
                        st.session_state.show_login = False
                        st.session_state.messages = load_chat_history(username)
                        st.success("登录成功！")
                        st.rerun()
                    else:
                        st.error("用户名或密码错误")
        with tab2:
            with st.form("register_form"):
                new_user = st.text_input("用户名")
                new_pass = st.text_input("密码", type="password")
                confirm_pass = st.text_input("确认密码", type="password")
                if st.form_submit_button("注册"):
                    if not new_user or not new_pass:
                        st.error("请填写完整")
                    elif new_pass != confirm_pass:
                        st.error("两次密码不一致")
                    else:
                        ok, msg = register_user(new_user, new_pass)
                        if ok:
                            if login_user(new_user, new_pass):
                                st.session_state.logged_in = True
                                st.session_state.username = new_user
                                st.session_state.guest_count = 0
                                st.session_state.show_login = False
                                st.session_state.messages = []
                                st.success("注册并登录成功！")
                                st.rerun()
                            else:
                                st.error("注册成功但自动登录失败，请手动登录")
                        else:
                            st.error(msg)
else:
    def login_dialog():
        with st.expander("🎈 哎呀，需要登录啦～ (请升级 Streamlit 获得更好体验)", expanded=True):
            st.warning("请升级 Streamlit 到最新版本以使用弹窗登录")

# ========== 侧边栏 ==========
with st.sidebar:
    st.markdown(f"""
    <div style="background: {cfg['bg_sidebar']}; border: 2px dashed {cfg['border']}; border-radius: 20px; padding: 0.8rem; margin-bottom: 1rem;">
        <div style="display: flex; align-items: center; gap: 10px;">
            <span style="font-size: 1.8rem;">👨‍🎓</span>
            <div>
                {f"<b style='font-size:0.9rem'>{st.session_state.username}</b><br><span style='font-size:0.7rem; color:{cfg['text_light']}'>已登录</span>" if st.session_state.logged_in else "<b>游客模式</b>"}
                {f"<span style='font-size:0.65rem; background:{cfg['secondary']}; padding:2px 6px; border-radius:20px; margin-top:4px; display:inline-block'>今日免费剩余：{max(0,5-st.session_state.guest_count)} 次</span>" if not st.session_state.logged_in else ""}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    if not st.session_state.logged_in:
        if st.button("🔑 登录", use_container_width=True, key="login_btn"):
            st.session_state.show_login = True
            st.rerun()
    else:
        if st.button("🚪 退出登录", use_container_width=True, key="logout_btn"):
            st.session_state.logged_in = False
            st.session_state.username = None
            st.session_state.messages = []
            st.session_state.show_login = False
            st.session_state.tutor = AITutor()
            st.rerun()
    st.markdown("---")

    st.markdown(f"### 🔧 学习工具")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📖 错题本", use_container_width=True, key="mistakes_btn"):
            st.session_state.show_mistakes = True
            st.session_state.show_report = False
            st.rerun()
    with col2:
        if st.button("📊 周报", use_container_width=True, key="report_btn"):
            st.session_state.show_report = True
            st.session_state.show_mistakes = False
            st.rerun()
    if st.button("💬 返回对话", use_container_width=True, key="back_chat_btn"):
        st.session_state.show_mistakes = False
        st.session_state.show_report = False
        st.rerun()
    if st.button("🗑️ 清空对话", use_container_width=True, key="clear_chat_btn"):
        if st.session_state.logged_in:
            clear_chat_history(st.session_state.username)
        st.session_state.messages = []
        st.session_state.tutor.clear_memory()
        st.session_state.worksheet = None
        st.rerun()
    st.markdown("---")

    with st.expander("🎤 语音 & 批改", expanded=False):
        # 注意：朗读按钮已移到右上角，此处不再显示
        with st.expander("📝 作业批改", expanded=False):
            homework_text = st.text_area("作业内容", height=120, placeholder="请粘贴学生作业...")
            if st.button("🚀 开始批改", use_container_width=True, key="grade_btn"):
                if homework_text.strip():
                    with st.spinner("批改中..."):
                        grade_result = st.session_state.tutor.grade_homework(
                            subject="通用",
                            grade_level="通用",
                            homework_content=homework_text
                        )
                        if grade_result and "mistakes" in grade_result:
                            for mistake in grade_result["mistakes"]:
                                st.session_state.tutor.record_mistake(
                                    session_id=st.session_state.tutor.session_id,
                                    subject="通用",
                                    grade_level="通用",
                                    question=mistake.get("question", ""),
                                    wrong_answer=mistake.get("wrong_answer", ""),
                                    correct_answer=mistake.get("correct_answer", ""),
                                    knowledge_point=mistake.get("knowledge_point", ""),
                                    error_type=mistake.get("error_type", "未分类")
                                )
                        st.session_state.grade_result = grade_result
                    st.success("批改完成，查看主界面")
                else:
                    st.warning("请输入作业内容")
    st.markdown("---")
    if st.button("⚙️ 设置", use_container_width=True):
        st.info("设置功能开发中")

# ========== 主内容区 ==========
if st.session_state.show_login:
    login_dialog()
    st.stop()

if st.session_state.show_mistakes:
    st.subheader("📚 我的错题本")
    mistakes = st.session_state.tutor.get_mistakes(st.session_state.tutor.session_id, reviewed=0)
    if not mistakes:
        st.info("暂无错题，继续加油～")
    else:
        for m in mistakes:
            with st.expander(f"❌ {m[4][:60]}..."):
                st.write(f"**题目**：{m[4]}")
                st.write(f"**你的答案**：{m[5]}")
                st.write(f"**正确答案**：{m[6]}")
                st.write(f"**知识点**：{m[7]}")
                st.write(f"**错误类型**：{m[8] if m[8] else '未分类'}")
                st.write(f"**时间**：{m[9]}")
                if st.button(f"✅ 标记为已复习", key=f"review_{m[0]}"):
                    st.session_state.tutor.mark_reviewed(m[0])
                    st.success("已标记！")
                    st.rerun()
elif st.session_state.show_report:
    st.subheader("📊 本周学习报告")
    with st.spinner("生成报告中..."):
        report = st.session_state.tutor.get_weekly_report(st.session_state.tutor.session_id)
    st.markdown(report)
else:
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(f'<div class="user-msg">{msg["content"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="assistant-msg">{msg["content"]}</div>', unsafe_allow_html=True)

    if st.session_state.worksheet:
        ws = st.session_state.worksheet
        st.markdown("---")
        st.subheader(f"📄 {ws.get('title', '练习题')}")
        for i, q in enumerate(ws.get("questions", []), 1):
            cleaned_q = re.sub(r'^\d+\.\s*', '', q)
            st.write(f"{i}. {cleaned_q}")
        col1, col2 = st.columns(2)
        with col1:
            docx_no_ans = create_worksheet_docx(ws.get("title", "练习题"), ws.get("questions", []), include_answers=False)
            st.download_button("📥 下载作业（无答案）", data=docx_no_ans, file_name=f"{ws.get('title', '作业')}_无答案.docx", use_container_width=True)
        with col2:
            docx_with_ans = create_worksheet_docx(ws.get("title", "练习题"), ws.get("questions", []), ws.get("answers", []), include_answers=True)
            st.download_button("📥 下载作业（含答案）", data=docx_with_ans, file_name=f"{ws.get('title', '作业')}_含答案.docx", use_container_width=True)

    if "grade_result" in st.session_state:
        st.markdown("---")
        col1, col2 = st.columns([6,1])
        with col1:
            st.subheader("📋 批改结果")
        with col2:
            if st.button("🗑️ 清除"):
                del st.session_state.grade_result
                st.rerun()
        gr = st.session_state.grade_result
        st.markdown(f"**得分**：{gr.get('score', 0)} / {gr.get('total_score', 100)}")
        if gr.get("comment"):
            st.markdown(f"**评语**：{gr['comment']}")
        if gr.get("mistakes"):
            st.markdown("**错题详情**：")
            for i, m in enumerate(gr["mistakes"], 1):
                st.markdown(f"{i}. {m.get('question', '')}  → 正确答案：{m.get('correct_answer', '')}")

# ========== 悬浮助手 ==========
st.markdown(f"""
<div class="floating-assistant" id="floatingHelper">
    {cfg['avatar_assistant']}
</div>
<script>
    const helper = document.getElementById('floatingHelper');
    let rotation = 0;
    setInterval(() => {{
        if (helper) {{
            rotation = (rotation + 0.02) % (Math.PI * 2);
            const translate = Math.sin(rotation) * 4;
            helper.style.transform = `translateY(${{translate}}px) scale(1.02)`;
        }}
    }}, 500);
</script>
""", unsafe_allow_html=True)

# ========== 辅助函数 ==========
def format_text_for_display(text):
    text = re.sub(r'([。！？；])(?!\n)', r'\1\n', text)
    text = re.sub(r'(第[一二三四五六七八九十]+步[：:])(?!\n)', r'\1\n', text)
    text = re.sub(r'(\d+\.)(?!\n)', r'\1\n', text)
    text = re.sub(r'(小练习|练习时间|小测试)', r'\n\1\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text

def extract_grade_from_prompt(prompt):
    grade_map = {
        "小学一年级": "小学一年级", "小学二年级": "小学二年级",
        "小学三年级": "小学三年级", "小学四年级": "小学四年级",
        "小学五年级": "小学五年级", "小学六年级": "小学六年级",
        "初中一年级": "初中一年级", "初中二年级": "初中二年级", "初中三年级": "初中三年级",
        "高中一年级": "高中一年级", "高中二年级": "高中二年级", "高中三年级": "高中三年级",
        "小学": "小学", "初中": "初中", "高中": "高中"
    }
    for key, value in grade_map.items():
        if key in prompt:
            return value
    return None

# ========== 接收用户输入 ==========
if prompt := st.chat_input("✏️ 输入你的问题，比如：鸡兔同笼怎么解？"):
    if not st.session_state.logged_in and st.session_state.guest_count >= 5:
        st.warning("您已达到免费使用次数上限，请登录后继续使用。")
        st.stop()
    
    if not st.session_state.logged_in:
        st.session_state.guest_count += 1
    
    with st.chat_message("user", avatar="🧑‍🎓"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    if st.session_state.logged_in:
        save_chat_message(st.session_state.username, "user", prompt)

    if "作业" in prompt:
        pattern = r'(?:生成|出)(\d+|两|二|一|三|四|五|六|七|八|九|十)?道?[的]?(.+?)(?:作业|题目|问题)'
        match = re.search(pattern, prompt)
        if match:
            num_str = match.group(1)
            if num_str:
                if num_str in ["两", "二"]:
                    num = 2
                elif num_str.isdigit():
                    num = int(num_str)
                else:
                    chinese_map = {"一":1, "二":2, "三":3, "四":4, "五":5, "六":6, "七":7, "八":8, "九":9, "十":10}
                    num = chinese_map.get(num_str, 5)
            else:
                num = 5
            topic = match.group(2).strip()
            if topic:
                extracted_grade = extract_grade_from_prompt(prompt)
                target_grade = extracted_grade if extracted_grade else None
                with st.spinner(f"正在生成 {topic} 的作业..."):
                    ws = st.session_state.tutor.generate_worksheet(topic, "中等", num, grade=target_grade)
                    if ws and ws.get("questions"):
                        st.session_state.worksheet = ws
                        with st.chat_message("assistant", avatar="👩‍🏫"):
                            st.markdown(f"✅ 已生成 **{topic}** 的作业（共 {len(ws['questions'])} 道题）：")
                            for i, q in enumerate(ws["questions"], 1):
                                cleaned = re.sub(r'^\d+\.\s*', '', q)
                                st.markdown(f"{i}. {cleaned}")
                            st.markdown("---")
                            col1, col2 = st.columns(2)
                            with col1:
                                docx_no_ans = create_worksheet_docx(ws.get("title", topic), ws.get("questions", []), include_answers=False)
                                st.download_button("📥 下载作业（无答案）", data=docx_no_ans, file_name=f"{topic}_作业_无答案.docx", use_container_width=True)
                            with col2:
                                docx_with_ans = create_worksheet_docx(ws.get("title", topic), ws.get("questions", []), ws.get("answers", []), include_answers=True)
                                st.download_button("📥 下载作业（含答案）", data=docx_with_ans, file_name=f"{topic}_作业_含答案.docx", use_container_width=True)
                        assistant_content = f"✅ 已生成 {topic} 的作业（共 {len(ws['questions'])} 道题），请在上方查看并下载。"
                        st.session_state.messages.append({"role": "assistant", "content": assistant_content})
                        if st.session_state.logged_in:
                            save_chat_message(st.session_state.username, "assistant", assistant_content)
                    else:
                        error_msg = "❌ 生成失败，请稍后重试。"
                        with st.chat_message("assistant", avatar="👩‍🏫"):
                            st.markdown(error_msg)
                        st.session_state.messages.append({"role": "assistant", "content": error_msg})
                        if st.session_state.logged_in:
                            save_chat_message(st.session_state.username, "assistant", error_msg)
            else:
                error_msg = "请告诉我具体的知识点，例如：生成2道鸡兔同笼作业。"
                with st.chat_message("assistant", avatar="👩‍🏫"):
                    st.markdown(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
                if st.session_state.logged_in:
                    save_chat_message(st.session_state.username, "assistant", error_msg)
        else:
            error_msg = "请使用类似“生成2道鸡兔同笼作业”的格式来生成作业。"
            with st.chat_message("assistant", avatar="👩‍🏫"):
                st.markdown(error_msg)
            st.session_state.messages.append({"role": "assistant", "content": error_msg})
            if st.session_state.logged_in:
                save_chat_message(st.session_state.username, "assistant", error_msg)
    else:
        with st.chat_message("assistant", avatar="👩‍🏫"):
            with st.spinner("🤔 老师正在思考中..."):
                raw_response = st.session_state.tutor.chat(prompt)
            formatted_response = format_text_for_display(raw_response)
            st.markdown(formatted_response)
        st.session_state.messages.append({"role": "assistant", "content": formatted_response})
        if st.session_state.logged_in:
            save_chat_message(st.session_state.username, "assistant", formatted_response)
