# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
import os
from django import setup
# Configure Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "CoreRoot.settings")
setup()

from tests.test1 import Test1

# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    test1 = Test1()
    test1.test7()