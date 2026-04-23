import dashscope
import json
import re
import time
import sqlite3
from datetime import datetime, timedelta
from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.messages import HumanMessage, AIMessage

dashscope.api_key = "sk-9f6558ca077a481fa54d52e15c863146"

class AITutor:
    def __init__(self, session_id=None):
        self.session_id = session_id if session_id else f"session_{int(time.time())}"
        # 通用老师，不再设置年级和科目
        self.student_level = None
        self.subject = None

        # 持久化聊天历史
        self.message_history = SQLChatMessageHistory(
            session_id=self.session_id,
            connection_string="sqlite:///ai_tutor_memory.db"
        )

        self.llm = ChatTongyi(
            model="qwen-plus",
            dashscope_api_key=dashscope.api_key
        )

        # 初始化错题本数据库表
        self._init_mistakes_table()

    def _init_mistakes_table(self):
        conn = sqlite3.connect('ai_tutor_memory.db')
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mistakes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                subject TEXT,
                grade_level TEXT,
                question TEXT,
                wrong_answer TEXT,
                correct_answer TEXT,
                knowledge_point TEXT,
                error_type TEXT,
                timestamp DATETIME,
                reviewed INTEGER DEFAULT 0
            )
        ''')
        conn.commit()
        conn.close()

    def get_system_prompt(self):
        # 通用老师提示词
        return f"""你是一位耐心、亲切的AI家教老师，可以帮助学生学习各个学科的知识，包括数学、语文、英语、物理、化学、生物、历史、地理、政治等。请根据学生的问题提供准确、清晰的解答，语气活泼有鼓励性。

【输出格式要求】非常重要，必须遵守！
1. 每个段落之间要有一个空行。
2. 当使用序号（如“第一步：”、“第二步：”或“1.”、“2.”）时，每个序号的内容必须单独占一行，写完一个序号后必须换行再写下一条。
3. 不要将多个序号的内容写在同一行或连续堆叠。

【教学要求】
- 不要直接给答案，要引导学生自己思考
- 每讲完一个知识点，出一道小练习
- 语气活泼、有鼓励性
- 适当使用 emoji
"""

    def calculate(self, expression):
        try:
            return str(eval(expression))
        except:
            return "计算错误"

    def define_tools(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "calculate",
                    "description": "计算数学表达式，返回计算结果",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "expression": {
                                "type": "string",
                                "description": "数学表达式，如 '35*2' 或 '94-70'"
                            }
                        },
                        "required": ["expression"]
                    }
                }
            }
        ]

    def call_llm(self, messages):
        response = dashscope.Generation.call(
            model='qwen-plus',
            messages=messages,
            tools=self.define_tools(),
            tool_choice='auto',
            result_format='message'
        )
        return response.output.choices[0].message

    def format_response(self, text):
        text = re.sub(r'(?<!\n)(第[一二三四五六七八九十]+步[：:])', r'\n\1', text)
        text = re.sub(r'(?<!\n)(\d+\.)', r'\n\1', text)
        text = re.sub(r'(?<!\n)(第一步|第二步|第三步|第四步|第五步)', r'\n\1', text)
        text = text.strip()
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text

    def _get_role(self, msg):
        if isinstance(msg, HumanMessage):
            return "user"
        elif isinstance(msg, AIMessage):
            return "assistant"
        return "system"

    def chat(self, user_input):
        self.message_history.add_user_message(user_input)
        history_messages = self.message_history.messages

        full_messages = [
            {"role": "system", "content": self.get_system_prompt()},
            *[{"role": self._get_role(msg), "content": msg.content} for msg in history_messages]
        ]

        message = self.call_llm(full_messages)

        if "tool_calls" in message and message["tool_calls"]:
            tool_call = message["tool_calls"][0]
            function_name = tool_call["function"]["name"]
            arguments = json.loads(tool_call["function"]["arguments"])

            if function_name == "calculate":
                result = self.calculate(arguments["expression"])
                tool_result_msg = f"【计算结果】{arguments['expression']} = {result}"
                self.message_history.add_ai_message(tool_result_msg)

                new_history = self.message_history.messages
                explain_messages = [
                    {"role": "system", "content": self.get_system_prompt()},
                    *[{"role": self._get_role(msg), "content": msg.content} for msg in new_history],
                    {"role": "user", "content": f"请用生动的方式讲解 {arguments['expression']} = {result} 这个计算过程，然后出一道类似的小练习。"}
                ]
                explain_response = self.call_llm(explain_messages)
                assistant_msg = explain_response.get("content", "")
                assistant_msg = self.format_response(assistant_msg)
                self.message_history.add_ai_message(assistant_msg)
                return assistant_msg
        else:
            assistant_msg = message.get("content", "")
            assistant_msg = self.format_response(assistant_msg)
            self.message_history.add_ai_message(assistant_msg)
            return assistant_msg

    def generate_worksheet(self, topic, difficulty="中等", num_questions=5, grade=None):
        # 不再依赖 self.student_level，如果 grade 为 None 则生成通用标题
        title_prefix = f"【{grade}】" if grade else ""
        prompt = f"""请生成 {difficulty} 难度的 {topic} 练习题，共 {num_questions} 道。
要求：
1. 题目内容要适合学习该知识点的学生，难度适中。
2. 输出必须严格按照以下 JSON 格式，不要有其他任何解释文字：
{{
    "title": "{title_prefix}{topic}练习题",
    "questions": ["题目1", "题目2", ...],
    "answers": ["答案1", "答案2", ...]
}}
"""
        response = dashscope.Generation.call(
            model='qwen-plus',
            messages=[{"role": "user", "content": prompt}],
            result_format='message'
        )
        content = response.output.choices[0].message.content
        try:
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = json.loads(content)
            data["title"] = f"{title_prefix}{topic}练习题"
            return data
        except Exception:
            return {
                "title": f"{title_prefix}{topic}练习题",
                "questions": [f"请计算：{topic}"],
                "answers": ["略"]
            }

    def grade_homework(self, subject, grade_level, homework_content):
        # 如果传入的是默认值，AI 会根据内容自动判断
        prompt = f"""你是AI老师。请批改以下学生作业。

作业内容：
{homework_content}

要求：
1. 输出必须为以下 JSON 格式，不要有其他任何文字：
{{
    "score": 85,
    "total_score": 100,
    "mistakes": [
        {{
            "question": "题目原文",
            "wrong_answer": "学生错误答案",
            "correct_answer": "正确答案",
            "knowledge_point": "知识点",
            "error_type": "错误类型，如：概念不清、计算失误、粗心大意、审题错误等"
        }}
    ],
    "comment": "评语"
}}
"""
        response = dashscope.Generation.call(
            model='qwen-plus',
            messages=[{"role": "user", "content": prompt}],
            result_format='message'
        )
        content = response.output.choices[0].message.content
        try:
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                result = json.loads(content)
            if "mistakes" not in result:
                result["mistakes"] = []
            return result
        except Exception:
            return {"score": 0, "total_score": 100, "mistakes": [], "comment": "解析失败，请重试"}

    def record_mistake(self, session_id, subject, grade_level, question, wrong_answer, correct_answer, knowledge_point, error_type):
        conn = sqlite3.connect('ai_tutor_memory.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO mistakes (session_id, subject, grade_level, question, wrong_answer, correct_answer, knowledge_point, error_type, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (session_id, subject, grade_level, question, wrong_answer, correct_answer, knowledge_point, error_type, datetime.now()))
        conn.commit()
        conn.close()

    def get_mistakes(self, session_id, reviewed=None):
        conn = sqlite3.connect('ai_tutor_memory.db')
        cursor = conn.cursor()
        if reviewed is None:
            cursor.execute('SELECT * FROM mistakes WHERE session_id = ? ORDER BY timestamp DESC', (session_id,))
        else:
            cursor.execute('SELECT * FROM mistakes WHERE session_id = ? AND reviewed = ? ORDER BY timestamp DESC', (session_id, reviewed))
        rows = cursor.fetchall()
        conn.close()
        return rows

    def mark_reviewed(self, mistake_id):
        conn = sqlite3.connect('ai_tutor_memory.db')
        cursor = conn.cursor()
        cursor.execute('UPDATE mistakes SET reviewed = 1 WHERE id = ?', (mistake_id,))
        conn.commit()
        conn.close()

    def get_weekly_report(self, session_id):
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        conn = sqlite3.connect('ai_tutor_memory.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM mistakes 
            WHERE session_id = ? AND timestamp >= ? AND timestamp <= ?
        ''', (session_id, start_date, end_date))
        total_mistakes = cursor.fetchone()[0]
        cursor.execute('''
            SELECT knowledge_point, COUNT(*) FROM mistakes 
            WHERE session_id = ? AND timestamp >= ? AND timestamp <= ?
            GROUP BY knowledge_point ORDER BY COUNT(*) DESC
        ''', (session_id, start_date, end_date))
        knowledge_stats = cursor.fetchall()
        cursor.execute('''
            SELECT error_type, COUNT(*) FROM mistakes 
            WHERE session_id = ? AND timestamp >= ? AND timestamp <= ?
            GROUP BY error_type
        ''', (session_id, start_date, end_date))
        error_type_stats = cursor.fetchall()
        conn.close()

        report_text = f"📊 本周学习报告（{start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}）\n\n"
        report_text += f"📝 本周共产生 **{total_mistakes}** 道错题。\n\n"
        if knowledge_stats:
            report_text += "🎯 薄弱知识点 TOP3：\n"
            for i, (kp, cnt) in enumerate(knowledge_stats[:3], 1):
                report_text += f"{i}. {kp}：{cnt} 次\n"
            report_text += "\n"
        if error_type_stats:
            report_text += "💡 错误类型分布：\n"
            for et, cnt in error_type_stats:
                report_text += f"- {et}：{cnt} 次\n"
            report_text += "\n"
        report_text += "✨ 继续加油，坚持练习，你会越来越棒！"
        return report_text

    def clear_memory(self):
        self.message_history.clear()
        conn = sqlite3.connect('ai_tutor_memory.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM mistakes WHERE session_id = ?', (self.session_id,))
        conn.commit()
        conn.close()

    def run(self):
        print("=" * 40)
        print("AI家教：通用老师")
        print("输入 quit 退出")
        print("=" * 40)
        while True:
            user_input = input("\n学生: ")
            if user_input == "quit":
                break
            response = self.chat(user_input)
            print(f"老师：{response}")

if __name__ == "__main__":
    tutor = AITutor()
    tutor.run()
