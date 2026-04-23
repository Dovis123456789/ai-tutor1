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

# ========== 聊天历史持久化 ==========
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

# ========== 页面配置 ==========
st.set_page_config(
    page_title="AI 家教助手",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========== CSS 样式 ==========
st.markdown("""
<style>
html, body, [class*="css"] { font-family: 'Inter', 'Comic Neue', 'Quicksand', system-ui, sans-serif; }
.stApp { background: linear-gradient(135deg, #e8f5e9 0%, #e0f2f1 100%); }
.main-title { font-size: 1.8rem; font-weight: 700; text-align: center; margin: 0.5rem 0 0.2rem; background: linear-gradient(120deg, #2e7d32, #81c784); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.subtitle { font-size: 0.8rem; text-align: center; margin: 0 0 0.8rem 0; color: #5a8a5a; }
.stChatMessage { padding: 0.1rem 0 !important; margin: 0 !important; }
[data-testid="stChatMessage"][data-testid="user"] { background-color: #c8e6c9 !important; border-radius: 20px 20px 8px 20px !important; padding: 6px 12px !important; font-size: 0.85rem !important; line-height: 1.35 !important; max-width: 85% !important; margin-left: auto !important; margin-bottom: 4px !important; }
[data-testid="stChatMessage"][data-testid="assistant"] { background-color: #fff9c4 !important; border-radius: 20px 20px 20px 8px !important; padding: 6px 12px !important; font-size: 0.85rem !important; line-height: 1.35 !important; max-width: 85% !important; margin-bottom: 4px !important; }
[data-testid="stSidebar"] { background: rgba(255, 255, 245, 0.95); border-right: 3px solid #81c784; border-radius: 0 30px 30px 0; }
.stButton button { background-color: #66bb6a; color: white; border-radius: 50px; border: none; font-size: 0.85rem; padding: 0.3rem 0.8rem; }
.stButton button:hover { background-color: #4caf50; }
.stChatInput textarea { border-radius: 30px !important; border: 2px solid #a5d6a7 !important; background-color: #ffffff !important; font-size: 0.9rem; padding: 8px 14px; }
@media (max-width: 768px) { .main-title { font-size: 1.5rem; } .subtitle { font-size: 0.7rem; } [data-testid="stChatMessage"][data-testid="user"], [data-testid="stChatMessage"][data-testid="assistant"] { padding: 5px 10px !important; font-size: 0.75rem !important; margin-bottom: 3px !important; } }
</style>
""", unsafe_allow_html=True)

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

# ========== 弹窗登录/注册 ==========
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
    # 降级方案
    def login_dialog():
        with st.expander("🎈 哎呀，需要登录啦～ (请升级 Streamlit 获得更好体验)", expanded=True):
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

# ========== 侧边栏 ==========
grade_list = [
    "小学一年级", "小学二年级", "小学三年级", "小学四年级", "小学五年级", "小学六年级",
    "初中一年级", "初中二年级", "初中三年级",
    "高中一年级", "高中二年级", "高中三年级"
]
subject_map = {
    "小学": ["语文", "数学", "英语"],
    "初中": ["语文", "数学", "英语", "物理", "化学", "生物", "历史", "地理", "政治"],
    "高中": ["语文", "数学", "英语", "物理", "化学", "生物", "历史", "地理", "政治"]
}
def get_subjects_by_grade(grade):
    if grade.startswith("小学"):
        return subject_map["小学"]
    elif grade.startswith("初中"):
        return subject_map["初中"]
    else:
        return subject_map["高中"]

with st.sidebar:
    st.markdown("### 🤖 智能老师")
    st.markdown("---")
    if st.session_state.logged_in:
        st.write(f"👤 欢迎，{st.session_state.username}")
        if st.button("🚪 退出登录", use_container_width=True):
            # 关键修改：退出登录时不清空 guest_count，只清空登录状态和消息
            st.session_state.logged_in = False
            st.session_state.username = None
            st.session_state.messages = []
            st.session_state.show_login = False
            st.session_state.tutor = AITutor()
            st.rerun()
    else:
        st.write("👤 游客模式")
        remaining = max(0, 5 - st.session_state.guest_count)
        st.caption(f"今日免费剩余：{remaining} 次")
        if st.button("🔑 登录", use_container_width=True):
            st.session_state.show_login = True
            st.rerun()
    st.markdown("---")
    selected_grade = st.selectbox("📖 年级", grade_list)
    subjects = get_subjects_by_grade(selected_grade)
    selected_subject = st.selectbox("✏️ 科目", subjects)
    st.session_state.tutor.student_level = selected_grade
    st.session_state.tutor.subject = selected_subject

    if st.button("🧹 清空对话", use_container_width=True):
        if st.session_state.logged_in:
            clear_chat_history(st.session_state.username)
        st.session_state.messages = []
        st.session_state.tutor.clear_memory()
        st.session_state.worksheet = None
        st.rerun()

    st.markdown("---")
    st.subheader("📚 学习工具")
    if st.button("📖 错题本", use_container_width=True):
        st.session_state.show_mistakes = True
        st.session_state.show_report = False
        st.rerun()
    if st.button("📊 本周学习报告", use_container_width=True):
        st.session_state.show_report = True
        st.session_state.show_mistakes = False
        st.rerun()
    if st.button("💬 返回对话", use_container_width=True):
        st.session_state.show_mistakes = False
        st.session_state.show_report = False
        st.rerun()

    st.markdown("---")
    if st.button("🔊 朗读最新回复", use_container_width=True):
        last_assistant_msg = None
        for msg in reversed(st.session_state.messages):
            if msg["role"] == "assistant":
                last_assistant_msg = msg["content"]
                break
        if last_assistant_msg:
            safe_text = last_assistant_msg.replace("'", "\\'").replace("\n", " ")
            st.markdown(f"""
                <script>
                    var msg = '{safe_text}';
                    var utterance = new SpeechSynthesisUtterance(msg);
                    utterance.lang = 'zh-CN';
                    window.speechSynthesis.speak(utterance);
                </script>
            """, unsafe_allow_html=True)
            st.success("正在朗读（浏览器语音）")
        else:
            st.warning("还没有AI老师的回复，先问个问题吧～")

    st.markdown("---")
    st.subheader("📝 作业批改")
    with st.expander("上传作业（文本）"):
        homework_text = st.text_area("作业内容", height=200, placeholder="请粘贴学生作业...")
        if st.button("🚀 开始批改", use_container_width=True):
            if homework_text.strip():
                with st.spinner("批改中，请稍候..."):
                    grade_result = st.session_state.tutor.grade_homework(
                        subject=selected_subject,
                        grade_level=selected_grade,
                        homework_content=homework_text
                    )
                    if grade_result and "mistakes" in grade_result:
                        for mistake in grade_result["mistakes"]:
                            st.session_state.tutor.record_mistake(
                                session_id=st.session_state.tutor.session_id,
                                subject=selected_subject,
                                grade_level=selected_grade,
                                question=mistake.get("question", ""),
                                wrong_answer=mistake.get("wrong_answer", ""),
                                correct_answer=mistake.get("correct_answer", ""),
                                knowledge_point=mistake.get("knowledge_point", ""),
                                error_type=mistake.get("error_type", "未分类")
                            )
                    st.session_state.grade_result = grade_result
                st.success("批改完成，请查看主界面结果。")
            else:
                st.warning("请输入作业内容")

    st.markdown("---")
    st.markdown('<div class="info-card">💡 小贴士<br>• 一步步引导思考<br>• 支持复杂计算</div>', unsafe_allow_html=True)

# ========== 主区域 ==========
st.markdown('<div class="main-title">🤖 AI 家教助手</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">🧸 让学习像看动画片一样有趣 🎈</div>', unsafe_allow_html=True)

# 主动显示登录弹窗
if st.session_state.show_login:
    login_dialog()
    st.stop()

# ========== 其他界面 ==========
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
                    st.success("已标记，继续加油！")
                    st.rerun()
elif st.session_state.show_report:
    st.subheader("📊 本周学习报告")
    with st.spinner("生成报告中..."):
        report = st.session_state.tutor.get_weekly_report(st.session_state.tutor.session_id)
    st.markdown(report)
else:
    # 显示聊天历史
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            with st.chat_message("user", avatar="🧑‍🎓"):
                st.markdown(msg["content"])
        else:
            with st.chat_message("assistant", avatar="👩‍🏫"):
                st.markdown(msg["content"])

    # 作业预览与下载
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
            st.download_button("📥 下载作业（无答案）", data=docx_no_ans, file_name=f"{ws.get('title', '作业')}_无答案.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
        with col2:
            docx_with_ans = create_worksheet_docx(ws.get("title", "练习题"), ws.get("questions", []), ws.get("answers", []), include_answers=True)
            st.download_button("📥 下载作业（含答案）", data=docx_with_ans, file_name=f"{ws.get('title', '作业')}_含答案.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)

    # 作业批改结果显示
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
                st.markdown(f"{i}. {m.get('question', '')}  → 正确答案：{m.get('correct_answer', '')}  (错误类型：{m.get('error_type', '')})")

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
    # 游客检查：未登录且已达到5次，提示并停止
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
                target_grade = extracted_grade if extracted_grade else st.session_state.tutor.student_level
                with st.spinner(f"正在生成 {target_grade} {topic} 的作业..."):
                    ws = st.session_state.tutor.generate_worksheet(topic, "中等", num, grade=target_grade)
                    if ws and ws.get("questions"):
                        st.session_state.worksheet = ws
                        with st.chat_message("assistant", avatar="👩‍🏫"):
                            st.markdown(f"✅ 已生成 **{target_grade} {topic}** 的作业（共 {len(ws['questions'])} 道题）：")
                            for i, q in enumerate(ws["questions"], 1):
                                cleaned = re.sub(r'^\d+\.\s*', '', q)
                                st.markdown(f"{i}. {cleaned}")
                            st.markdown("---")
                            col1, col2 = st.columns(2)
                            with col1:
                                docx_no_ans = create_worksheet_docx(ws.get("title", topic), ws.get("questions", []), include_answers=False)
                                st.download_button("📥 下载作业（无答案）", data=docx_no_ans, file_name=f"{topic}_作业_无答案.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
                            with col2:
                                docx_with_ans = create_worksheet_docx(ws.get("title", topic), ws.get("questions", []), ws.get("answers", []), include_answers=True)
                                st.download_button("📥 下载作业（含答案）", data=docx_with_ans, file_name=f"{topic}_作业_含答案.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
                        assistant_content = f"✅ 已生成 {target_grade} {topic} 的作业（共 {len(ws['questions'])} 道题），请在上方查看并下载。"
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
