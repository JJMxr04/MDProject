from .unit_tests import  TournamentCreationTestCase #, TournamentFunctionalityTestCase ,RoundCreationTestCase, RoundCreationTestCase

import unittest


def suite():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add your test cases here
    suite.addTest(loader.loadTestsFromTestCase(TournamentCreationTestCase))
    # suite.addTest(loader.loadTestsFromTestCase(TournamentFunctionalityTestCase))
    # suite.addTest(loader.loadTestsFromTestCase(RoundCreationTestCase))
    # suite.addTest(loader.loadTestsFromTestCase(RoundCreationTestCase))
    # Add other test cases as needed

    return suite


if __name__ == '__main__':
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite())