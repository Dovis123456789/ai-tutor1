import dashscope
import json

dashscope.api_key = "sk-9f6558ca077a481fa54d52e15c863146"

class AITutor:
    def __init__(self):
        self.messages = []
        self.student_level = "小学五年级"
        self.subject = "数学"

    def get_system_prompt(self):
        return f"""你是{self.student_level}的{self.subject}家教老师。

要求：
1. 不要直接给答案，要引导学生自己思考
2. 每讲完一个知识点，出一道小练习
3. 语气要活泼、有鼓励性
4. 适当使用 emoji 增加趣味性

重要规则：
- 当学生问数学计算题时，不要自己计算，必须调用 calculate 工具
- 用工具算出结果后，再向学生展示计算过程

"""
    def calculate(self, expression):
        """计算数学表达式"""
        try:
            return str(eval(expression))
        except:
            return "计算错误"

    def define_tools(self):
        """定义可用工具"""
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
    
    def chat(self, user_input):
        self.messages.append({"role": "user", "content": user_input})

        full_messages = [
            {"role": "system", "content": self.get_system_prompt()},
            *self.messages
        ]
        
        response = dashscope.Generation.call(
            model='qwen-plus',
            messages=full_messages,
            tools=self.define_tools(),
            tool_choice='auto',
            result_format='message'
        )
        message = response.output.choices[0].message

        if "tool_calls" in message and message["tool_calls"]:
            tool_call = message["tool_calls"][0]
            function_name = tool_call["function"]["name"]
            arguments = json.loads(tool_call["function"]["arguments"])

            if function_name == "calculate":
                result = self.calculate(arguments["expression"])
                # 把计算结果作为助手回复
                assistant_msg = f"计算结果：{result}"
                self.messages.append({"role": "assistant", "content": assistant_msg})
                return assistant_msg
        else:
            assistant_msg = message.get("content", "")
            self.messages.append({"role": "assistant", "content": assistant_msg})
            return assistant_msg

    
    def run(self):
        print("=" * 40)
        print(f"AI家教：{self.student_level} {self.subject}老师")
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