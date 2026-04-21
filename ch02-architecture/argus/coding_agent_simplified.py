class CodingAgent:
    def __init__(self):
        self.tools = [  #A
        ReadFile, EditFile, Bash,
        Search, Glob, Grep]
        self.memory = ConversationHistory()  #B

    def run(self, user_task: str):
        self.memory.add_user_message(user_task)
        while True:
            context = (  #C
            self.memory.get_context_window())
            response = self.llm.generate(context)  #D
            if response.is_final_answer():
                return response.text
            tool_result = (  #E
            self.execute_tool(response.tool))
            self.memory.add_tool_result(  #F
            tool_result)
