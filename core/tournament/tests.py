# from .unit_tests import  TournamentCreationTestCase #, TournamentFunctionalityTestCase ,RoundCreationTestCase, RoundCreationTestCase
#
# import unittest
#
#
# def suite():
#     loader = unittest.TestLoader()
#     suite = unittest.TestSuite()
#
#     # Add your test cases here
#     suite.addTest(loader.loadTestsFromTestCase(TournamentCreationTestCase))
#     # suite.addTest(loader.loadTestsFromTestCase(TournamentFunctionalityTestCase))
#     # suite.addTest(loader.loadTestsFromTestCase(RoundCreationTestCase))
#     # suite.addTest(loader.loadTestsFromTestCase(RoundCreationTestCase))
#     # Add other test cases as needed
#
#     return suite
#
#
# if __name__ == '__main__':
#     runner = unittest.TextTestRunner(verbosity=2)
#     runner.run(suite())
#
#     import logging
#     from core.tournament.unit_tests.tests.tournament_test_1 import tournament_test_1
#     from .unit_tests import tournament_test_1
#
#     import unittest
#
#
#     class TournamentTestSuite(unittest.TestCase):
#
#         # def Tournament_Simulation_128_Max_andAccepted_PLayers(self):
#         #     logging.INFO('Starting Tournament Simulation test with 128 max and accepted players')
#         #     test1 = tournament_test_1(max_players=128, tourney_name='test128')
#
#         # def Tournament_Simulation_2_Max_andAccepted_PLayers(self):
#         #     logging.INFO('Starting Tournament Simulation test with 2 max and accepted players')
#         #     test1 = tournament_test_1(max_players=2, tourney_name='test2')