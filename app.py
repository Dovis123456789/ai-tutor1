import streamlit as st
import time
import json
import os
from ai_tutor import AITutor # 引入你刚才写的家教类
HISTORY_FILE = "chat_history.json"

def save_history(messages):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False)

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

st.title("🤖 我的AI家教")
saved_messages = load_history()

# 初始化聊天历史和家教实例
if "tutor" not in st.session_state:
    st.session_state.tutor = AITutor()
if "messages" not in st.session_state:
    st.session_state.messages = saved_messages

# 侧边栏设置
with st.sidebar:
    st.header("设置")
    grade = st.selectbox("年级", ["小学五年级", "小学六年级", "初中一年级"])
    subject = st.selectbox("科目", ["数学", "语文", "英语"])
    
    # 更新家教实例的年级和科目
    st.session_state.tutor.student_level = grade
    st.session_state.tutor.subject = subject
    
    if st.button("清空对话"):
        st.session_state.messages = []
        st.session_state.tutor = AITutor()
        save_history([])
        st.rerun()


# 显示历史消息
for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

# 打字机效果函数
def stream_response(response):
    for word in response.split():
        yield word + " "
        time.sleep(0.03)

# 接受用户输入
if prompt := st.chat_input("输入你的问题..."):
    st.chat_message("user").write(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        with st.spinner("老师正在思考中..."):
            response = st.session_state.tutor.chat(prompt)
        st.write_stream(stream_response(response)) 
    st.session_state.messages.append({"role": "assistant", "content": response})
    save_history(st.session_state.messages)