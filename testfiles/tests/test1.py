import json

# Importing various serializers and models from different Django apps
from core.event.models.sport import Sport
from core.game.models import Game
from core.match.models import Match

# Instantiating Sport model
sport_model = Sport()

# Importing cron jobs for scheduled tasks
from core.event.crons.sportUpdate import SportCron
sport_cron = SportCron()

from core.event.crons.eventUpdate import EventCron
from core.event.crons.teamUpdate import TeamCron

event_cron = EventCron()
team_cron = TeamCron()

# Importing datetime to manipulate date and time

# Class containing various utility functions
from core.tournament.unit_tests.tests.Support import Support



support = Support()


class Test1:

    def test1(self):
        print("Starting Event Creation Testing 1")
        Support.test_get_nfl_events('testfiles/nfl-copy1.json')
        # Needs to add checks
        print("Stopped Event Creation Testing 1")

    def test2(self):
        print("Starting SportCronTesting 2")
        sport_cron.get_sports()
        print(sport_cron.get_active_sports())
        # Needs to add checks
        print("Stopped SportCronTesting 2")

    def test3(self):
        print("Starting EventCronTesting 3")
        events = event_cron.get_sport_events("americanfootball_nfl.json")
        pretty = json.dumps(events)
        print(pretty)
        # Needs to add checks
        print("Stopped EventCronTesting 3")

    def test4(self):
        print("Starting EventCronTesting 4")
        events = event_cron.update_all_events()
        print(events)
        # Needs to add checks
        print("Stopped EventCronTesting 4")

    def test5(self):
        print("Starting Event Creation Testing 5")
        sport_cron.get_sports()
        sports = sport_cron.get_active_sports()
        # print(sports)
        # event_cron.get_sport_events("soccer_switzerland_superleague")
        # print(sports)
        for sport in sports:
            Support.test_get_nfl_events(f'testfiles/originals/{sport}.json')
        # Needs to add checks
        print("Stopped Event Creation Testing 5")

    def test5_5(self):
        print("Starting sport Creation Testing 5.5")

        folder_path = 'testfiles/originals'
        output_file = 'testfiles/sports_list.txt'
        support.process_files_in_folder(folder_path, output_file)
        sports = Support.read_list_from_file(output_file)
        print(sports)
        # sport_cron.get_sports()
        # sports = sport_cron.get_active_sports()
        # # print(sports)
        # # event_cron.get_sport_events("soccer_switzerland_superleague")
        # # print(sports)
        for sport in sports:
            support.test_get_nfl_events(f'testfiles/originals/{sport}')
        # Needs to add checks
        print("Stopped sport Creation Testing 5.5")

    def test6(self):
        print("Starting Game Creation and Update Testing 6")
        owner, player_2 = Support.get_test_players()
        game = Game.objects.create_game(owner, player_2)
        data1 = {
            "event_id": "85ccca87e453d00340982559fd50c443",
            "player_choice": "Penn State Nittany Lions"
        }
        data2 = {
            "event_id": "85ccca87e453d00340982559fd50c443",
            "player_choice": "Ole Miss Rebels"
        }
        Game.objects.update_by_id(game.id, owner, data1)
        Game.objects.update_by_id(game.id, player_2, data2)
        game1 = Game.objects.get_object_by_id(game.id)
        print(game1.event)
        print(game1.owner_choice)
        print(game1.player_2_choice)
        # Needs to add checks

        print("Stopped Game Creation and Update Testing 6")

    def test7(self):
        print("Starting Game Creation and Signal Update Testing 7")
        support.flush_database()
        folder_path = 'testfiles/originals'
        output_file = 'testfiles/sports_list.txt'
        support.process_files_in_folder(folder_path, output_file)
        sports = support.read_list_from_file(output_file)
        support.test_get_nfl_events(f'testfiles/nfl-copy1-1.json')
        owner, player_2 = support.get_test_players()

        game = Game.objects.create_game(owner, player_2)

        data1 = {
            "event_id": "484bc5582bb44ab79a1e942cf8762eda",
            "player_choice": "Miami Dolphins"
        }
        data2 = {
            "event_id": "484bc5582bb44ab79a1e942cf8762eda",
            "player_choice": "Tennessee Titans"
        }

        Game.objects.update_by_id(game.id, owner, data1)
        Game.objects.update_by_id(game.id, player_2, data2)
        support.test_get_nfl_events(f'testfiles/nfl-copy2-1.json')
        game1 = Game.objects.get_object_by_id(game.id)
        if game1.event.winner == "Miami Dolphins":
            print(f"Event winner:{game1.event.winner} - pass")
        else:
            print(f"Event winner:{game1.event.winner} - fail")
        if game1.owner_choice == "Miami Dolphins":
            print(f"Owner Choice:{game1.owner_choice} - pass")
        else:
            print(f"Owner Choice:{game1.owner_choice} - fail")
        if game1.player_2_choice == "Tennessee Titans":
            print(f"Player_2 Choice:{game1.player_2_choice} - pass")
        else:
            print(f"Player_2 Choice:{game1.play_2_choice} - fail")
        if game1.winner == "Miami Dolphins":
            print(f"Game winner:{game1.winner} - pass")
        else:
            print(f"Game winner:{game1.winner} - fail")
        print("Stopped Game Creation and Signal Update Testing 7")

    def test8(self, amount):
        print(f"Starting Test  8- testing {amount} games being made and updated")
        support.flush_database()
        print("Test 8 - first update - Start")
        folder_path = 'testfiles/originals'
        output_file = 'testfiles/sports_list.txt'
        support.process_files_in_folder(folder_path, output_file)
        sports = support.read_list_from_file(output_file)
        support.test_get_nfl_events(f'testfiles/nfl-copy1-1.json')
        print("Test 8 - first update - Finish")
        print("Test 8 Starting Game creating for loop")
        for x in range(1, amount):
            # print(x)
            owner, player_2 = support.get_test_players()

            game = Game.objects.create_game(owner, player_2)

            data1 = {
                "event_id": "484bc5582bb44ab79a1e942cf8762eda",
                "player_choice": "Miami Dolphins"
            }
            data2 = {
                "event_id": "484bc5582bb44ab79a1e942cf8762eda",
                "player_choice": "Tennessee Titans"
            }

            Game.objects.update_by_id(game.id, owner, data1)
            Game.objects.update_by_id(game.id, player_2, data2)
        print("Test 8 - Second update - Start")
        support.test_get_nfl_events(f'testfiles/nfl-copy2-1.json')
        print("Test 8 - Second update - Finish")
        print("Finish Test  8- testing 1000000 games being made and updated")

    def test9(self):

        print("Starting Match Creation and Update Testing 9")
        support.flush_database()
        support.update_golden_game(f'testfiles/nfl-copy1-1.json', "ea43090cd4cc2eb2fb98ba3847aba986")
        support.update_golden_game(f'testfiles/nfl-copy2-1.json', "ea43090cd4cc2eb2fb98ba3847aba986")

        folder_path = 'testfiles/originals'
        output_file = 'testfiles/sports_list.txt'
        support.process_files_in_folder(folder_path, output_file)
        sports = support.read_list_from_file(output_file)

        support.test_get_nfl_events(f'testfiles/nfl-copy1-1.json')
        owner, player_2 = support.get_test_players()
        match = Match.objects.create_match(owner)
        # print(match)
        match1 = Match.objects.accept_match(match,player_2)

        if match != match1:
            print("Test 9 failed for two different matches")
            exit()

        data1 = {
            "event_id": "484bc5582bb44ab79a1e942cf8762eda",
            "player_choice": "Miami Dolphins"
        }
        data2 = {
            "event_id": "484bc5582bb44ab79a1e942cf8762eda",
            "player_choice": "Tennessee Titans"
        }
        data1_gg = {
            "event_id": "ea43090cd4cc2eb2fb98ba3847aba986",
            "player_choice": "New York Giants"
        }
        data2_gg = {
            "event_id": "ea43090cd4cc2eb2fb98ba3847aba986",
            "player_choice": "Green Bay Packers"
        }
        Game.objects.update_by_id(match1.player_1_game_1.id, owner, data1)
        Game.objects.update_by_id(match1.player_1_game_1.id, player_2, data2)
        Game.objects.update_by_id(match1.player_1_game_2.id, owner, data1)
        Game.objects.update_by_id(match1.player_1_game_2.id, player_2, data2)
        Game.objects.update_by_id(match1.player_1_game_3.id, owner, data1)
        Game.objects.update_by_id(match1.player_1_game_3.id, player_2, data2)
        Game.objects.update_by_id(match1.player_1_game_4.id, owner, data1)
        Game.objects.update_by_id(match1.player_1_game_4.id, player_2, data2)
        Game.objects.update_by_id(match1.player_1_game_5.id, owner, data1)
        Game.objects.update_by_id(match1.player_1_game_5.id, player_2, data2)

        Game.objects.update_by_id(match1.player_2_game_1.id, player_2, data2)
        Game.objects.update_by_id(match1.player_2_game_1.id, owner, data1)
        Game.objects.update_by_id(match1.player_2_game_2.id, player_2, data2)
        Game.objects.update_by_id(match1.player_2_game_2.id, owner, data1)
        Game.objects.update_by_id(match1.player_2_game_3.id, player_2, data2)
        Game.objects.update_by_id(match1.player_2_game_3.id, owner, data1)
        Game.objects.update_by_id(match1.player_2_game_4.id, player_2, data2)
        Game.objects.update_by_id(match1.player_2_game_4.id, owner, data1)
        Game.objects.update_by_id(match1.player_2_game_5.id, player_2, data2)
        Game.objects.update_by_id(match1.player_2_game_5.id, owner, data1)

        Game.objects.update_by_id(match1.golden_game.id, player_2, data2_gg)
        Game.objects.update_by_id(match1.golden_game.id, owner, data1_gg)

        support.test_get_nfl_events(f'testfiles/nfl-copy2-1.json')
        match2 = Match.objects.get_object_by_id(match1.id)
        # print(match2)
        games = [match2.player_1_game_1,
                 match2.player_1_game_2,
                 match2.player_1_game_3,
                 match2.player_1_game_4,
                 match2.player_1_game_5,
                 match2.player_2_game_1,
                 match2.player_2_game_2,
                 match2.player_2_game_3,
                 match2.player_2_game_4,
                 match2.player_2_game_5,
                 match2.golden_game]

        for game in games:
            if game != match2.golden_game:
                if game.owner == match2.player_1:
                    if game.event.winner == "Miami Dolphins":
                        print(f"Event winner:{game.event.winner} - pass")
                    else:
                        print(f"Event winner:{game.event.winner} - fail")
                        exit()
                    if game.owner_choice == "Miami Dolphins":
                        print(f"Owner Choice:{game.owner_choice} - pass")
                    else:
                        print(f"Owner Choice:{game.owner_choice} - fail")
                        exit()
                    if game.player_2_choice == "Tennessee Titans":
                        print(f"Player_2 Choice:{game.player_2_choice} - pass")
                    else:
                        print(f"Player_2 Choice:{game.player_2_choice} - fail")
                        exit()
                    if game.winner == "Miami Dolphins":
                        print(f"Game winner:{game.winner} - pass")
                    else:
                        print(f"Game winner:{game.winner} - fail")
                        exit()
                if game.owner == match2.player_2:
                    if game.event.winner == "Miami Dolphins":
                        print(f"Event winner:{game.event.winner} - pass")
                    else:
                        print(f"Event winner:{game.event.winner} - fail")
                        exit()
                    if game.owner_choice == "Tennessee Titans":
                        print(f"Owner Choice:{game.owner_choice} - pass")
                    else:
                        print(f"Owner Choice:{game.owner_choice} - fail")
                        exit()
                    if game.player_2_choice == "Miami Dolphins":
                        print(f"Player_2 Choice:{game.player_2_choice} - pass")
                    else:
                        print(f"Player_2 Choice:{game.player_2_choice} - fail")
                        exit()
                    if game.winner == "Miami Dolphins":
                        print(f"Game winner:{game.winner} - pass")
                    else:
                        print(f"Game winner:{game.winner} - fail")
                        exit()
            elif game != match2.golden_game:
                print("*Golden Game Check*")
                if game.event.winner == "New York Giants":
                    print(f"Event winner:{game.event.winner} - pass")
                else:
                    print(f"Event winner:{game.event.winner} - fail")
                    exit()
                if game.owner_choice == "New York Giants":
                    print(f"Owner Choice:{game.owner_choice} - pass")
                else:
                    print(f"Owner Choice:{game.owner_choice} - fail")
                    exit()
                if game.player_2_choice == "Green Bay Packers":
                    print(f"Player_2 Choice:{game.player_2_choice} - pass")
                else:
                    print(f"Player_2 Choice:{game.player_2_choice} - fail")
                    exit()
                if game.winner == "New York Giants":
                    print(f"Game winner:{game.winner} - pass")
                else:
                    print(f"Game winner:{game.winner} - fail")
                    exit()

        print("Stopped Match Creation and Update Testing 9")

    def test10(self):

        print("Starting Match Creation and Update Testing 10")
        support.flush_database()
        print("Test10 - started to modify the golden game")
        support.update_golden_game(f'testfiles/nfl-copy1-1.json', "ea43090cd4cc2eb2fb98ba3847aba986")
        support.update_golden_game(f'testfiles/nfl-copy2-1.json', "ea43090cd4cc2eb2fb98ba3847aba986")
        print("Test10 - started to  update all the nfl events")
        folder_path = 'testfiles/originals'
        output_file = 'testfiles/sports_list.txt'
        support.process_files_in_folder(folder_path, output_file)
        sports = support.read_list_from_file(output_file)
        support.test_get_nfl_events(f'testfiles/nfl-copy1-1.json')
        print("Test10 - started Match Making And Accepting")
        owner, player_2 = support.get_test_players()
        match = Match.objects.create_match(owner)
        # print(match)
        match1 = Match.objects.accept_match(match, player_2)

        if match != match1:
            print("Test 9 failed for two different matches")
            exit()

        data1 = {
            "event_id": "484bc5582bb44ab79a1e942cf8762eda",
            "player_choice": "Miami Dolphins"
        }
        data2 = {
            "event_id": "484bc5582bb44ab79a1e942cf8762eda",
            "player_choice": "Tennessee Titans"
        }
        data1_gg = {
            "event_id": "ea43090cd4cc2eb2fb98ba3847aba986",
            "player_choice": "New York Giants"
        }
        data2_gg = {
            "event_id": "ea43090cd4cc2eb2fb98ba3847aba986",
            "player_choice": "Green Bay Packers"
        }
        Game.objects.update_by_id(match1.player_1_game_1.id, owner, data1)
        Game.objects.update_by_id(match1.player_1_game_1.id, player_2, data2)
        Game.objects.update_by_id(match1.player_1_game_2.id, owner, data1)
        Game.objects.update_by_id(match1.player_1_game_2.id, player_2, data2)
        Game.objects.update_by_id(match1.player_1_game_3.id, owner, data1)
        Game.objects.update_by_id(match1.player_1_game_3.id, player_2, data2)
        Game.objects.update_by_id(match1.player_1_game_4.id, owner, data1)
        Game.objects.update_by_id(match1.player_1_game_4.id, player_2, data2)
        Game.objects.update_by_id(match1.player_1_game_5.id, owner, data1)
        Game.objects.update_by_id(match1.player_1_game_5.id, player_2, data2)

        Game.objects.update_by_id(match1.player_2_game_1.id, player_2, data2)
        Game.objects.update_by_id(match1.player_2_game_1.id, owner, data1)
        Game.objects.update_by_id(match1.player_2_game_2.id, player_2, data2)
        Game.objects.update_by_id(match1.player_2_game_2.id, owner, data1)
        Game.objects.update_by_id(match1.player_2_game_3.id, player_2, data2)
        Game.objects.update_by_id(match1.player_2_game_3.id, owner, data1)
        Game.objects.update_by_id(match1.player_2_game_4.id, player_2, data2)
        Game.objects.update_by_id(match1.player_2_game_4.id, owner, data1)
        Game.objects.update_by_id(match1.player_2_game_5.id, player_2, data2)
        Game.objects.update_by_id(match1.player_2_game_5.id, owner, data1)

        Game.objects.update_by_id(match1.golden_game.id, player_2, data2_gg)
        Game.objects.update_by_id(match1.golden_game.id, owner, data1_gg)

        support.test_get_nfl_events(f'testfiles/nfl-copy2-1.json')
        match2 = Match.objects.get_object_by_id(match1.id)
        # print(match2)
        games = [match2.player_1_game_1,
                 match2.player_1_game_2,
                 match2.player_1_game_3,
                 match2.player_1_game_4,
                 match2.player_1_game_5,
                 match2.player_2_game_1,
                 match2.player_2_game_2,
                 match2.player_2_game_3,
                 match2.player_2_game_4,
                 match2.player_2_game_5,
                 match2.golden_game]

        for game in games:
            if game != match2.golden_game:
                if game.owner == match2.player_1:
                    if game.event.winner == "Miami Dolphins":
                        # print(f"Event winner:{game.event.winner} - pass")
                        pass
                    else:
                        print(f"Event winner:{game.event.winner} - fail")
                        exit()
                    if game.owner_choice == "Miami Dolphins":
                        # print(f"Owner Choice:{game.owner_choice} - pass")
                        pass
                    else:
                        print(f"Owner Choice:{game.owner_choice} - fail")
                        exit()
                    if game.player_2_choice == "Tennessee Titans":
                        # print(f"Player_2 Choice:{game.player_2_choice} - pass")
                        pass
                    else:
                        print(f"Player_2 Choice:{game.player_2_choice} - fail")
                        exit()
                    if game.winner == "Miami Dolphins":
                        # print(f"Game winner:{game.winner} - pass")
                        pass
                    else:
                        print(f"Game winner:{game.winner} - fail")
                        exit()
                if game.owner == match2.player_2:
                    if game.event.winner == "Miami Dolphins":
                        # print(f"Event winner:{game.event.winner} - pass")
                        pass
                    else:
                        print(f"Event winner:{game.event.winner} - fail")
                        exit()
                    if game.owner_choice == "Tennessee Titans":
                        # print(f"Owner Choice:{game.owner_choice} - pass")
                        pass
                    else:
                        print(f"Owner Choice:{game.owner_choice} - fail")
                        exit()
                    if game.player_2_choice == "Miami Dolphins":
                        # print(f"Player_2 Choice:{game.player_2_choice} - pass")
                        pass
                    else:
                        print(f"Player_2 Choice:{game.player_2_choice} - fail")
                        exit()
                    if game.winner == "Miami Dolphins":
                        # print(f"Game winner:{game.winner} - pass")
                        pass
                    else:
                        print(f"Game winner:{game.winner} - fail")
                        exit()
            elif game != match2.golden_game:
                print("*Golden Game Check*")
                if game.event.winner == "New York Giants":
                    # print(f"Event winner:{game.event.winner} - pass")
                    pass
                else:
                    print(f"Event winner:{game.event.winner} - fail")
                    exit()
                if game.owner_choice == "New York Giants":
                    # print(f"Owner Choice:{game.owner_choice} - pass")
                    pass
                else:
                    print(f"Owner Choice:{game.owner_choice} - fail")
                    exit()
                if game.player_2_choice == "Green Bay Packers":
                    # print(f"Player_2 Choice:{game.player_2_choice} - pass")
                    pass
                else:
                    print(f"Player_2 Choice:{game.player_2_choice} - fail")
                    exit()
                if game.winner == "New York Giants":
                    # print(f"Game winner:{game.winner} - pass")
                    pass
                else:

                    print(f"Game winner:{game.winner} - fail")
                    exit()
        match = Match.objects.get_object_by_id(match.id)

        if match.winner != owner:
            print(f"Winner {match.winner}- Failed")
            exit()
        if match.match_state != "completed":
            print(f"Stated =  {match.match_state}- Failed")
            exit()

        print("Stopped Match Creation and Update Testing 10")

    def test10_1(self):

        print("Starting Match Creation and Update Testing 10.1")
        support.flush_database()
        support.update_golden_game(f'testfiles/nfl-copy1-1.json', "ea43090cd4cc2eb2fb98ba3847aba986")
        support.update_golden_game(f'testfiles/nfl-copy2-1.json', "ea43090cd4cc2eb2fb98ba3847aba986")

        folder_path = 'testfiles/originals'
        output_file = 'testfiles/sports_list.txt'
        support.process_files_in_folder(folder_path, output_file)
        sports = support.read_list_from_file(output_file)
        support.test_get_nfl_events(f'testfiles/nfl-copy1-1.json')
        owner, player_2 = support.get_test_players()


        print("Finished Event Update Testing 10.1")


    def testFlushAndGetSportsAndEvents(self):
        support.datadump()
        support.flush_database()
        owner, player_2 = support.get_test_players()
        sport_cron.get_sports()
        event_cron.update_all_events()
        support.datadump()

    def testTeams(self,team_name,title,group):

        team_cron.check_team(team_name, title, group)

    def testCreateMatches(self,num):
        for x in range(1,num+1):
            owner, player_2 = support.get_test_players()
            match = Match.objects.create_match(owner)
            # print(match)
            # match1 = Match.objects.accept_match(match, player_2)

    def testCreateAndAcceptMatches(self,num):
        for x in range(1,num+1):
            owner, player_2 = support.get_test_players()
            match = Match.objects.create_match(owner)
            # print(match)
            match1 = Match.objects.accept_match(match, player_2)

