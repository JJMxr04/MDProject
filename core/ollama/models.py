# from django.db import models
#
# # Create your models here.
# # import ollama
# from langchain_community.llms import Ollama
# from langchain_core.messages import HumanMessage, AIMessage
# from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
#
#
# llm = Ollama(model="llama3")
#
# chat_history = []
#
# prompt_template = ChatPromptTemplate.from_messages(
#     [
#         (
#             "system",
#             "You are an AI named Mike, you answer questions with simple answers and no funny stuff.",
#         ),
#         MessagesPlaceholder(variable_name="chat_history"),
#         ("human", "{input}"),
#     ]
# )
#
# chain = prompt_template | llm
#
#
#
# class OllamaBot:
#
#
#
#
#     # def chat(self, response):
#     #     stream = ollama.chat(
#     #         model='llama3',
#     #         messages=[{'role': 'user', 'content': response}],
#     #         stream=self.streamBool,
#     #     )
#     #     return stream
#     #
#     # def printStream(self,stream):
#     #     for chunk in stream:
#     #         print(chunk['message']['content'], end='', flush=True)
#     #
#     # def terminalPrintChat(self,reponse):
#     #     stream = self.chat(response=reponse)
#     #     self.printStream(stream=stream)
#     #
#     #
#     # def Chat1(self,res):
#     #     stream = ollama.chat(
#     #         model='llama3',
#     #         messages=[{'role': 'user', 'content': res}],
#     #         stream=True,
#     #     )
#     #     for chunk in stream:
#     #         print(chunk['message']['content'], end='', flush=True)





# from langchain_community.llms import Ollama
# from langchain_core.messages import HumanMessage, AIMessage
# from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
#
#
# llm = Ollama(model="llama3")
#
# chat_history = []
#
# prompt_template = ChatPromptTemplate.from_messages(
#     [
#         (
#             "system",
#             "You are an AI named Mike, you answer questions with simple answers and no funny stuff.",
#         ),
#         MessagesPlaceholder(variable_name="chat_history"),
#         ("human", "{input}"),
#     ]
# )
#
# chain = prompt_template | llm
#
#
# def start_app():
#     while True:
#         question = input("You: ")
#         if question == "done":
#             return
#
#         # response = llm.invoke(question)
#         response = chain.invoke({"input": question, "chat_history": chat_history})
#         chat_history.append(HumanMessage(content=question))
#         chat_history.append(AIMessage(content=response))
#
#         print("AI:" + response)
#
#
# if __name__ == "__main__":
#     start_app()
