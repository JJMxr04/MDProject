# # This is a sample Python script.
#
# # Press Shift+F10 to execute it or replace it with your code.
# # Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
# import os
# from django import setup
# # Configure Django settings
# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "CoreRoot.settings")
# setup()
# # from tests.tourneyTestHelpFuncs import TourneyTestHelp
# from core.event.models.team import Team
# # from tests.test1 import Test1
# # from tests.test2 import eventTest
# from core.tournament.unit_tests.tests.Tourney_Simulator_1 import TourneyTest
# # test1 = Test1()
# # eventTest = eventTest()
# team1 = Team()
# # from tests.Support import Support
# # support = Support()
#
# from core.ollama.models import Ollama
# ollama = Ollama()
# from core.event.models.sport import Sport
# from core.event.serializers.sport import SportSerializer
#
#
#
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
#
# # if __name__ == '__main__':
# #     # test = TourneyTest(max_players=128,tourney_name='test1').run_test()
# #     # ollama.terminalPrintChat("what is the last sports event you have seen? or entered as a database entry?")
# #     # ollama.Chat1("What was the most recent sport event?")
# #     # ollama.Chat1("write the code to train you on data, what i mean by thi is i want to give you some data sets on events though json so that you are up to daTE ON EVENTS. tHEN I want to ask you to write them like blogs eventually")
# #     # ollama.Chat1("What was the last wuestion im asked?")
# #
# #
# #     pass
#
