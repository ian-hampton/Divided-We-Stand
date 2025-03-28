# STANDARD IMPORTS
import ast
import csv
from datetime import datetime
import json
import os
import random
import shutil
from typing import Union, Tuple, List

# MY IMPORTS
from app import map
from app import interpreter
from app import public_actions
from app import private_actions
from app import checks
from app import events
from app.region import Region
from app.improvement import Improvement
from app.unit import Unit
from app.wardata import WarData
from app.notifications import Notifications
from app.alliance import Alliance
from app.alliance import AllianceTable


#TURN PROCESSING PROCEDURE
################################################################################

def resolve_stage1_processing(game_id, starting_region_list, player_color_list):
    '''
    Resolves turn processing for a game in stage one.

    Parameters:
    - game_id: The full game_id of the active game.
    - starting_region_list: A list of player starting region ids gathered from turn resolution HTML form. 
    - player_color_list: A list of player colors gathered from turn resolution HTML form. 
    '''

    # get game files
    with open(f'gamedata/{game_id}/regdata.json', 'r') as json_file:
        regdata_dict = json.load(json_file)


    # create hex color list
    hexadecimal_player_color_list = []
    for player_color in player_color_list:
        new_player_color = player_colors_hex[player_color]
        hexadecimal_player_color_list.append(new_player_color)
    

    # Place Starting Capitals For Players
    random_assignment_list = []
    for index, region_id in enumerate(starting_region_list):
        player_id = index + 1
        if region_id in regdata_dict:
            starting_region = Region(region_id, game_id)
            starting_region_improvement = Improvement(region_id, game_id)
            starting_region.set_owner_id(player_id)
            starting_region_improvement.set_improvement("Capital")
        else:
            random_assignment_list.append(player_id)
    
    # place starting capitals for players who want random start
    for random_assignment_player_id in random_assignment_list:
        while True:
            # randomly select a region
            conflict_detected = False
            region_id_list = list(regdata_dict.keys()) 
            random_region_id = random.sample(region_id_list, 1)[0]
            random_region = Region(random_region_id, game_id)
            # if region not allowed restart loop
            if not random_region.is_start:
                continue
            # check if there is a player within three regions
            regions_in_radius = random_region.get_regions_in_radius(3)
            for candidate_region_id in regions_in_radius:
                candidate_region = Region(candidate_region_id, game_id)
                # if player found restart loop
                if candidate_region.owner_id != 0:
                    conflict_detected = True
                    break
            # if no player found place player
            if conflict_detected == False:
                random_region.set_owner_id(random_assignment_player_id)
                random_region_improvement = Improvement(random_region_id, game_id)
                random_region_improvement.set_improvement("Capital")
                break
    
    # read and update playerdata
    playerdata_list = read_file(f'gamedata/{game_id}/playerdata.csv', 1)
    for index, player in enumerate(playerdata_list):
        player[2] = hexadecimal_player_color_list[index]
    early_player_data_header = ["Player","Nation Name","Color","Government","Foreign Policy","Military Capacity","Trade Fee","Stability Data","VC Set A","VC Set B","Dollars","Political Power","Technology","Coal","Oil","Green Energy","Basic Materials","Common Metals","Advanced Metals","Uranium","Rare Earth Elements","Alliance Data","Missile Data","Diplomatic Relations","Upkeep Manager","Miscellaneous Information","Income Details","Completed Research","Improvement Count"]
    with open(f'gamedata/{game_id}/playerdata.csv', 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(early_player_data_header)
        writer.writerows(playerdata_list)
    
    # update active_games.json
    with open('active_games.json', 'r') as json_file:
        active_games_dict = json.load(json_file)
    active_games_dict[game_id]["Statistics"]["Current Turn"] = "Nation Setup in Progress"
    with open('active_games.json', 'w') as json_file:
        json.dump(active_games_dict, json_file, indent=4)
    
    # generate and update maps
    current_turn_num = get_current_turn_num(int(game_id[-1]))
    map_name = get_map_name(int(game_id[-1]))
    main_map = map.MainMap(game_id, map_name, current_turn_num)
    resource_map = map.ResourceMap(game_id, map_name)
    control_map = map.ControlMap(game_id, map_name)
    resource_map.create()
    main_map.place_random()
    main_map.update()
    resource_map.update()
    control_map.update()

def resolve_stage2_processing(game_id, player_nation_name_list, player_government_list, player_foreign_policy_list, player_victory_condition_set_list):
    '''
    Resolves turn processing for a game in stage two.

    Parameters:
    - game_id: The full game_id of the active game.
    - player_nation_name_list: A list of player nation names gathered from turn resolution HTML form. 
    - player_government_list: A list of player government choices gathered from turn resolution HTML form. 
    - player_foreign_policy_list: A list of player fp choices gathered from turn resolution HTML form. 
    - player_victory_condition_set_list: A list of player vc set choices gathered from turn resolution HTML form. 
    '''
    playerdata_filepath = f'gamedata/{game_id}/playerdata.csv'
    playerdata_list = read_file(playerdata_filepath, 1)
    player_count = len(playerdata_list)
    research_data_dict = get_scenario_dict(game_id, "Technologies")
    five_point_research_list = []
    for key in research_data_dict:
        tech = research_data_dict[key]
        if tech["Cost"] == 5:
            five_point_research_list.append(key)
    with open(f'gamedata/{game_id}/gamedata.json', 'r') as json_file:
        gamedata_dict = json.load(json_file)
    
    # read and update playerdata
    for index, player in enumerate(playerdata_list):
        if player[0] != "":
            # update basic nation info
            player[1] = player_nation_name_list[index].title()
            player[3] = player_government_list[index]
            player[4] = player_foreign_policy_list[index]
            # confirm victory condition set
            if player_victory_condition_set_list[index] == "Set A":
                del player[9]
            else:
                del player[8]
            # apply income rates
            if player[3] == 'Republic':
                rate_list = republic_rates
            elif player[3] == 'Technocracy':
                rate_list = technocracy_rates
            elif player[3] == 'Oligarchy':
                rate_list = oligarchy_rates
            elif player[3] == 'Totalitarian':
                rate_list = totalitarian_rates
            elif player[3] == 'Remnant':
                rate_list = remnant_rates
            elif player[3] == 'Protectorate':
                rate_list = protectorate_rates
            elif player[3] == 'Military Junta':
                rate_list = military_junta_rates
            elif player[3] == 'Crime Syndicate':
                rate_list = crime_syndicate_rates
            j = 9
            for rate in rate_list:
                resource_data = ast.literal_eval(playerdata_list[index][j])
                resource_data[3] = rate
                playerdata_list[index][j] = str(resource_data)
                j += 1
            # give starting research
            if player[3] == "Technocracy":
                starting_list = random.sample(five_point_research_list, 3)
                player[26] = str(starting_list)

    # add vc playerdata
    # to do - move this into regular playerdata once playerdata rework happens
    for playerdata in playerdata_list:
        gamedata_dict["victoryConditions"][playerdata[1]] = [False, False, False]
    
    # create records
    file_names = ['largest_nation', 'strongest_economy', 'largest_military', 'most_research']
    starting_records_data = [['Turn', 0]]
    for playerdata in playerdata_list:
        starting_records_data.append([playerdata[1], 0])
    for file_name in file_names:
        with open(f'gamedata/{game_id}/{file_name}.csv', 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerows(starting_records_data)

    # update playerdata.csv
    with open(playerdata_filepath, 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(player_data_header)
        writer.writerows(playerdata_list)

    # create trucedata.csv
    with open(f'gamedata/{game_id}/trucedata.csv', 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(trucedata_header)

    # update misc info in playerdata
    for i in range(player_count):
        player_id = i + 1
        checks.update_misc_info(game_id, player_id)
    # update improvement count in playerdata
    for i in range(player_count):
        player_id = i + 1
        checks.update_improvement_count(game_id, player_id)
    # update income in playerdata
    checks.update_income(game_id)
    
    # gain starting resources
    playerdata_list = read_file(playerdata_filepath, 1)
    for player in playerdata_list:
        dollars_data = ast.literal_eval(player[9])
        political_power_data = ast.literal_eval(player[10])
        technology_data = ast.literal_eval(player[11])
        dollars_data[0] = '10.00'
        political_power_data[0] = '0.00'
        technology_data[0] = '0.00'
        player[9] = str(dollars_data)
        player[10] = str(political_power_data)
        player[11] = str(technology_data)

    # update playerdata.csv
    with open(playerdata_filepath, 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(player_data_header)
        writer.writerows(playerdata_list)
    
    # update game_settings
    with open('active_games.json', 'r') as json_file:
        active_games_dict = json.load(json_file)
    active_games_dict[game_id]["Statistics"]["Current Turn"] = "1"
    current_date = datetime.today().date()
    current_date_string = current_date.strftime("%m/%d/%Y")
    active_games_dict[game_id]["Statistics"]["Game Started"] = current_date_string
    active_games_dict[game_id]["Statistics"]["Days Ellapsed"] = 0
    steal_tracking_dict = {}
    for playerdata in playerdata_list:
        if playerdata[3] == 'Crime Syndicate':
            inner_dict = {
                'Nation Name': None,
                'Streak': 0,
            }
            steal_tracking_dict[playerdata[1]] = inner_dict
    active_games_dict[game_id]["Steal Action Record"] = steal_tracking_dict
    transactions_dict = {}
    for playerdata in playerdata_list:
        transactions_dict[playerdata[1]] = 0
    active_games_dict[game_id]["Transactions Record"] = transactions_dict
    with open('active_games.json', 'w') as json_file:
        json.dump(active_games_dict, json_file, indent=4)
    
    # save gamedata
    with open(f'gamedata/{game_id}/gamedata.json', 'w') as json_file:
        json.dump(gamedata_dict, json_file, indent=4)

    # update visuals
    current_turn_num = 1
    map_name = active_games_dict[game_id]["Information"]["Map"]
    main_map = map.MainMap(game_id, map_name, current_turn_num)
    main_map.update()

def resolve_turn_processing(full_game_id, public_actions_list, private_actions_list):
    '''
    Resolves turn processing for a game in stage three (an active and fully setup game).

    Parameters:
    - full_game_id: The full game_id of the active game.
    - public_actions_list: A list of player public actions gathered from turn resolution HTML form. 
    - private_actions_list: A list of player private actions gathered from turn resolution HTML form. 
    '''
    playerdata_filepath = f'gamedata/{full_game_id}/playerdata.csv'
    playerdata_list = read_file(playerdata_filepath, 1)
    player_count = len(playerdata_list)
    current_turn_num = get_current_turn_num(int(full_game_id[-1]))
    map_name = get_map_name(int(full_game_id[-1]))
    
    #create logs
    player_action_logs = []
    for i in range(player_count):
        player_action_logs.append([])
    notifications = Notifications(full_game_id)
    notifications.clear()

    #filter
    library = get_library(full_game_id)
    for player_actions_list in public_actions_list:
        for i, action in enumerate(player_actions_list):
            player_actions_list[i] = interpreter.check_action(action, library, full_game_id)
    for player_actions_list in private_actions_list:
        for i, action in enumerate(player_actions_list):
            player_actions_list[i] = interpreter.check_action(action, library, full_game_id)


    #Declare Action Dictionaries
    public_actions_dict = {
        'Surrender': [],
        'White Peace': [],
        'Purchase': [],
        'Research': [],
        'Remove': [],
        'Build': [],
        'Make': [],
        'Buy': [],
        'Sell': [],
        'Alliance Create': [],
        'Alliance Join': [],
        'Alliance Leave': [],
        'Republic': [],
        'Event': []
    }
    private_actions_dict = {
        'Steal': [],
        'Withdraw': [],
        'Disband': [],
        'Deploy': [],
        'War': [],
        'Launch': [],
        'Move': []
    }


    #Oppertunity to Resolve Active Events
    public_actions_dict, private_actions_dict = events.resolve_active_events("Before Actions", public_actions_dict, private_actions_dict, full_game_id)

    
    #Sort Player Entered Public Actions
    if public_actions_list != []:
        for i, player_public_actions_list in enumerate(public_actions_list):
            for public_action in player_public_actions_list:
                action_type = identify(public_action)
                action = [i + 1, public_action]
                if action_type in public_actions_dict:
                    public_actions_dict[action_type].append(action)
    #process actions
    public_actions.resolve_trades(full_game_id)
    print("Resolving public actions...")
    if public_actions_list != []:
        update_control_map = False
        if len(public_actions_dict['Surrender'] + public_actions_dict['White Peace']) > 0:
            peace_action_list = public_actions_dict['Surrender'] + public_actions_dict['White Peace']
            player_action_logs = public_actions.resolve_peace_actions(peace_action_list, full_game_id, current_turn_num, player_action_logs)
            update_control_map = True
        if len(public_actions_dict['Research']) > 0:
            player_action_logs = public_actions.resolve_research_actions(public_actions_dict['Research'], full_game_id, player_action_logs)
        if len(public_actions_dict['Alliance Leave']) > 0:
            player_action_logs = public_actions.resolve_alliance_leaves(public_actions_dict['Alliance Leave'], full_game_id, player_action_logs)
        if len(public_actions_dict['Alliance Create']) > 0:
            player_action_logs = public_actions.resolve_alliance_creations(public_actions_dict['Alliance Create'], full_game_id, player_action_logs)
        if len(public_actions_dict['Alliance Join']) > 0:
            player_action_logs = public_actions.resolve_alliance_joins(public_actions_dict['Alliance Join'], full_game_id, player_action_logs)
        if len(public_actions_dict['Purchase']) > 0:
            player_action_logs = public_actions.resolve_region_purchases(public_actions_dict['Purchase'], full_game_id, player_action_logs)
            update_control_map = True
        if len(public_actions_dict['Remove']) > 0:
            player_action_logs = public_actions.resolve_improvement_removals(public_actions_dict['Remove'], full_game_id, player_action_logs)
        if len(public_actions_dict['Build']) > 0:
            player_action_logs = public_actions.resolve_improvement_builds(public_actions_dict['Build'], full_game_id, player_action_logs)
        if len(public_actions_dict['Republic']) > 0:
            government_actions_list = public_actions_dict['Republic']
            player_action_logs = public_actions.resolve_government_abilities(government_actions_list, full_game_id, player_action_logs)
        if len(public_actions_dict['Make']) > 0:
            player_action_logs = public_actions.resolve_missile_builds(public_actions_dict['Make'], full_game_id, player_action_logs)
        if len(public_actions_dict['Event']) > 0:
            player_action_logs = public_actions.resolve_event_actions(public_actions_dict['Event'], full_game_id, current_turn_num, player_action_logs)


    #Post Public Action Checks
    #check for missing war justifications
    checks.prompt_for_missing_war_justifications(full_game_id)
    #update improvement count in playerdata
    for i in range(player_count):
        player_id = i + 1
        checks.update_improvement_count(full_game_id, player_id)
    #update military capacity
    checks.update_military_capacity(full_game_id)


    #Sort Player Entered Private Actions
    if private_actions_list != []:
        for i, player_private_actions_list in enumerate(private_actions_list):
            for private_action in player_private_actions_list:
                action_type = identify(private_action)
                action = [i + 1, private_action]
                if action_type in private_actions_dict:
                    private_actions_dict[action_type].append(action)
    #process actions
    player_resource_market_incomes = False
    player_action_logs, player_resource_market_incomes = public_actions.resolve_market_actions(public_actions_dict['Buy'], public_actions_dict['Sell'], private_actions_dict['Steal'], full_game_id, current_turn_num, player_count, player_action_logs)    
    print("Resolving private actions...")
    if private_actions_list != []:
        if len(private_actions_dict['Disband']) > 0:
            player_action_logs = private_actions.resolve_unit_disbands(private_actions_dict['Disband'], full_game_id, player_action_logs)
        if len(private_actions_dict['Deploy']) > 0:
            player_action_logs = private_actions.resolve_unit_deployments(private_actions_dict['Deploy'], full_game_id, player_action_logs)
        if len(private_actions_dict['War']) > 0:
            player_action_logs = private_actions.resolve_war_declarations(private_actions_dict['War'], full_game_id, current_turn_num, player_action_logs)
        if len(private_actions_dict['Launch']) > 0:
            player_action_logs = private_actions.resolve_missile_launches(private_actions_dict['Launch'], full_game_id, player_action_logs)
        if len(private_actions_dict['Move']) > 0:
            player_action_logs = private_actions.resolve_unit_movements(private_actions_dict['Move'], full_game_id, player_action_logs)
            update_control_map = True


    #Save Logs
    # clear all files in log directory
    directory = f'gamedata/{full_game_id}/logs'
    os.makedirs(directory, exist_ok=True)
    # player logs
    for index, action_log in enumerate(player_action_logs):
        filename = os.path.join(directory, f'Player #{index + 1}.txt')
        with open(filename, 'w') as file:
            for string in action_log:
                file.write(string + '\n')
    # war logs
    from app.wardata import WarData
    wardata = WarData(full_game_id)
    wardata.export_all_logs()


    #End of Turn Checks and Updates
    print("Resolving end of turn updates...")
    checks.total_occupation_forced_surrender(full_game_id)
    checks.war_score_forced_surrender(full_game_id)
    run_end_of_turn_checks(full_game_id, current_turn_num, player_count)
    wardata.add_warscore_from_occupations()
    wardata.update_totals()
    for i in range(player_count):
        player_id = i + 1
        checks.gain_income(full_game_id, player_id)
        
    
    #Oppertunity to Resolve Active Events
    public_actions_dict, private_actions_dict = events.resolve_active_events("After Actions", public_actions_dict, private_actions_dict, full_game_id)


    #Prepwork for the Next Turn
    #resolve improvements with countdowns
    checks.countdown(full_game_id, map_name)
    checks.resolve_resource_shortages(full_game_id)

    for i in range(player_count):
        player_id = i + 1
        checks.update_improvement_count(full_game_id, player_id)
        checks.gain_resource_market_income(full_game_id, player_id, player_resource_market_incomes)
    #update income in playerdata
    checks.update_income(full_game_id)
    

    #Check If Someone Has Won the Game
    player_has_won = check_for_winner(full_game_id, player_count, current_turn_num)


    #Resolve Bonus Phase
    if not player_has_won:
        if current_turn_num % 4 == 0:
            checks.bonus_phase_heals(player_id, full_game_id)
            notifications.append('All units and defensive improvements have regained 2 health.', 1)
        #event procedure
        if current_turn_num % 8 == 0:
            print("Triggering an event...")
            events.trigger_event(full_game_id, current_turn_num)


    #Update Game_Settings
    update_turn_num(int(full_game_id[-1]))
    with open('active_games.json', 'r') as json_file:
        active_games_dict = json.load(json_file)
    start_date = active_games_dict[full_game_id]["Statistics"]["Game Started"]
    current_date = datetime.today().date()
    current_date_string = current_date.strftime("%m/%d/%Y")
    current_date_obj = datetime.strptime(current_date_string, "%m/%d/%Y")
    start_date_obj = datetime.strptime(start_date, "%m/%d/%Y")
    date_difference = current_date_obj - start_date_obj
    active_games_dict[full_game_id]["Statistics"]["Days Ellapsed"] = date_difference.days
    with open('active_games.json', 'w') as json_file:
        json.dump(active_games_dict, json_file, indent=4)


    #Update Visuals
    current_turn_num = get_current_turn_num(int(full_game_id[-1]))
    #resgraphs.update_all(full_game_id)
    main_map = map.MainMap(full_game_id, map_name, current_turn_num)
    main_map.update()
    if update_control_map:
        control_map = map.ControlMap(full_game_id, map_name)
        control_map.update()


#TURN PROCESSING FUNCTIONS
################################################################################

def create_new_game(game_id, form_data_dict, profile_ids_list):
    '''
    Backend code for creating the files for a new game. Returns nothing.

    Parameters:
    - full_game_id: A valid game_id to be used for the new game.
    - form_data_dict: Dictionary of data gathered from the turn resolution HTML form.
    - profile_ids_list: A list of all the profile ids of players participating in the game.
    '''

    # open game record files
    with open('active_games.json', 'r') as json_file:
        active_games_dict = json.load(json_file)
    with open('game_records.json', 'r') as json_file:
        game_records_dict = json.load(json_file)

    # datetime stuff
    current_date = datetime.today().date()
    current_date_string = current_date.strftime("%m/%d/%Y")
    game_version = "Development"

    # generate game id
    # to be added

    # erase old game files
    erase_game(game_id)
    
    # update active_games
    active_games_dict[game_id]["Game Name"] = form_data_dict["Game Name"]
    active_games_dict[game_id]["Statistics"]["Player Count"] = form_data_dict["Player Count"]
    active_games_dict[game_id]["Information"]["Victory Conditions"] = form_data_dict["Victory Conditions"]
    active_games_dict[game_id]["Information"]["Map"] = form_data_dict["Map"]
    active_games_dict[game_id]["Information"]["Accelerated Schedule"] = form_data_dict["Accelerated Schedule"]
    active_games_dict[game_id]["Information"]["Turn Length"] = form_data_dict["Turn Length"]
    active_games_dict[game_id]["Information"]["Fog of War"] = form_data_dict["Fog of War"]
    active_games_dict[game_id]["Information"]["Deadlines on Weekends"] = form_data_dict["Deadlines on Weekends"]
    active_games_dict[game_id]["Information"]["Scenario"] = form_data_dict["Scenario"]
    active_games_dict[game_id]["Statistics"]["Current Turn"] = "Starting Region Selection in Progress"
    active_games_dict[game_id]["Game #"] = len(game_records_dict) + 1
    active_games_dict[game_id]["Information"]["Version"] = game_version
    active_games_dict[game_id]["Statistics"]["Days Ellapsed"] = 0
    active_games_dict[game_id]["Statistics"]["Game Started"] = current_date_string
    active_games_dict[game_id]["Statistics"]["Region Disputes"] = 0
    active_games_dict[game_id]["Inactive Events"] = []
    active_games_dict[game_id]["Active Events"] = {}
    active_games_dict[game_id]["Current Event"] = {}
    active_games_dict[game_id]["Game Active"] = True
    with open('active_games.json', 'w') as json_file:
        json.dump(active_games_dict, json_file, indent=4)
    
    # update game_records
    new_game_entry = {}
    new_game_entry["Game ID"] = "temp"
    new_game_entry["Game #"] = len(game_records_dict) + 1
    new_game_entry["Information"] = {}
    new_game_entry ["Statistics"] = {}
    new_game_entry["Statistics"]["Player Count"] = int(form_data_dict["Player Count"])
    new_game_entry["Information"]["Victory Conditions"] = form_data_dict["Victory Conditions"]
    new_game_entry["Information"]["Map"] = form_data_dict["Map"]
    new_game_entry["Information"]["Accelerated Schedule"] = form_data_dict["Accelerated Schedule"]
    new_game_entry["Information"]["Turn Duration"] = form_data_dict["Turn Length"]
    new_game_entry["Information"]["Fog of War"] = form_data_dict["Fog of War"]
    new_game_entry["Information"]["Version"] = game_version
    new_game_entry["Information"]["Scenario"] = form_data_dict["Scenario"]
    new_game_entry["Statistics"]["Game End Turn"] = 0
    new_game_entry["Statistics"]["Days Ellapsed"] = 0
    new_game_entry["Statistics"]["Game Started"] = current_date_string
    new_game_entry["Statistics"]["Game Ended"] = 'Present'
    game_records_dict[form_data_dict["Game Name"]] = new_game_entry
    with open('game_records.json', 'w') as json_file:
        json.dump(game_records_dict, json_file, indent=4)

    # get scenario data
    improvement_data_dict = get_scenario_dict(game_id, "Improvements")

    # copy starting map images
    files_destination = f'gamedata/{game_id}'
    map_str = map.get_map_str(new_game_entry["Information"]["Map"])
    starting_map_images = ['resourcemap', 'controlmap']
    for map_filename in starting_map_images:
        shutil.copy(f"app/static/images/map_images/{map_str}/blank.png", f"{files_destination}/images")
        shutil.move(f"{files_destination}/images/blank.png", f"gamedata/{game_id}/images/{map_filename}.png")
    
    # create regdata.json
    shutil.copy(f"maps/{map_str}/regdata.json", files_destination)
    if form_data_dict["Scenario"] == 'Standard':
        with open(f'gamedata/{game_id}/regdata.json', 'r') as json_file:
            regdata_dict = json.load(json_file)
        for region_id in regdata_dict:
            regdata_dict[region_id]["regionData"]["infection"] = 0
            regdata_dict[region_id]["regionData"]["quarantine"] = False
        with open(f'gamedata/{game_id}/regdata.json', 'w') as json_file:
            json.dump(regdata_dict, json_file, indent=4)

    # create gamedata.json
    gamedata_filepath = f'gamedata/{game_id}/gamedata.json'
    gamedata_dict = {}
    gamedata_dict["alliances"] = {}
    gamedata_dict["notifications"] = {}
    gamedata_dict["victoryConditions"] = {}
    with open(gamedata_filepath, 'w') as json_file:
        json.dump(gamedata_dict, json_file, indent=4)

    # create rmdata file
    rmdata_filepath = f'{files_destination}/rmdata.csv'
    with open(rmdata_filepath, 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(rm_header)
    
    # create wardata.json
    wardata_dict = {}
    with open(f'gamedata/{game_id}/wardata.json', 'w') as json_file:
        json.dump(wardata_dict, json_file, indent=4)

    # create playerdata file
    playerdata_filepath = f"{files_destination}/playerdata.csv"
    player_data_header = ["Player","Nation Name","Color","Government","Foreign Policy","Military Capacity","Trade Fee","Stability Data","VC Set A","VC Set B","Dollars","Political Power","Technology","Coal","Oil","Green Energy","Basic Materials","Common Metals","Advanced Metals","Uranium","Rare Earth Elements","Alliance Data","Missile Data","Diplomatic Relations","Upkeep Manager","Miscellaneous Information","Income Details","Completed Research","Improvement Count","Status","Global ID"]
    player_data_temp_a = ["TBD","#ffffff","TBD","TBD","0/0","1:1","TBD"]
    victory_conditions_list = []
    player_data_temp_b = [['0.00',100,'0.00',100],['0.00',50,'0.00',100],['0.00',50,'0.00',100],['0.00',50,'0.00',100],['0.00',50,'0.00',100],['0.00',50,'0.00',100],['0.00',50,'0.00',100],['0.00',50,'0.00',100],['0.00',50,'0.00',100],['0.00',50,'0.00',100],['0.00',50,'0.00',100],[False, False, False, False],[0,0],['Neutral','Neutral','Neutral','Neutral','Neutral','Neutral','Neutral','Neutral','Neutral','Neutral'],['0.00','0.00','0.00','0.00'],['Capital Resource: None.','Owned Regions: 0','Occupied Regions: 0','Undeveloped Regions: 0','You cannot issue Economic Sanctions.','You cannot issue Military Sanctions.'],"[]","[]",[0] * len(improvement_data_dict), 'Independent Nation']
    with open(playerdata_filepath, 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(player_data_header)
        for i in range(int(form_data_dict["Player Count"])):
            victory_conditions_list = []
            random_easy_list = random.sample(easy_list, len(easy_list))
            random_normal_list = random.sample(normal_list, len(normal_list))
            random_hard_list = random.sample(hard_list, len(hard_list))
            set_a = []
            set_a.append(random_easy_list.pop())
            set_a.append(random_normal_list.pop())
            set_a.append(random_hard_list.pop())
            set_b = []
            set_b.append(random_easy_list.pop())
            set_b.append(random_normal_list.pop())
            set_b.append(random_hard_list.pop())
            victory_conditions_list.append(set_a)
            victory_conditions_list.append(set_b)
            player_number = f"Player #{i+1}"
            player_data_line = player_data_temp_a + victory_conditions_list + player_data_temp_b
            player_data_line.append(profile_ids_list[i])
            player_data_line.insert(0, player_number)
            writer.writerow(player_data_line)
    relations_data_all = []
    for i in range(int(form_data_dict["Player Count"])):
        relations_row = []
        player_number = "Player #" + str(i+1)
        relations_row.append(player_number)
        for i in range(int(form_data_dict["Player Count"])):
            relations_row.append('Neutral')
        while len(relations_row) < 11:
            relations_row.append('-')
        relations_data_all.append(relations_row)
    for index, entry in enumerate(relations_data_all):
        entry[index + 1] = '-'
    playerdata_list = read_file(playerdata_filepath, 1)
    for index, entry in enumerate(playerdata_list):
        entry[23] = relations_data_all[index]
    with open(playerdata_filepath, 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(player_data_header)
        writer.writerows(playerdata_list)

def erase_game(full_game_id):
    '''
    Erases all the game files of a given game. Returns nothing.
    Note: This does not erase anything from the game_records.json file.

    Parameters:
    - full_game_id: A valid game_id to be erased.
    '''
    shutil.rmtree(f'gamedata/{full_game_id}')
    os.makedirs(f'gamedata/{full_game_id}/images')
    os.makedirs(f'gamedata/{full_game_id}/logs')

def get_data_for_nation_sheet(game_id: str, player_id: int, current_turn_num: int) -> dict:
    '''
    Gathers all the needed data for a player's nation sheet data and spits it as a dict.

    Params:
        game_id: The full game_id of the active game.
        player_id: The integer id of the active player.
        current_turn_num: An integer number representing the game's current turn number.

    Returns:
        dict: player_information_dict.
    '''
    
    # get game data
    playerdata_filepath = f'gamedata/{game_id}/playerdata.csv'
    playerdata_list = read_file(playerdata_filepath, 1)
    nation_name_list = []
    for player in playerdata_list:
        nation_name_list.append(player[1])
    wardata = WarData(game_id)
    alliance_table = AllianceTable(game_id)
    misc_data_dict = get_scenario_dict(game_id, "Misc")

    # get information on player
    playerdata = playerdata_list[player_id - 1]
    player_research_list = ast.literal_eval(playerdata[26])

    # build player info dict
    player_information_dict = {
        'Victory Conditions Data': {},
        'Resource Data': {},
        'Alliance Data': {},
        'Missile Data': {},
        'Relations Data': {},
        'Upkeep Manager': {},
        'Misc Info': {},
    }
    player_information_dict['Nation Name'] = playerdata[1]
    player_information_dict['Color'] = playerdata[2]
    player_information_dict['Government'] = playerdata[3]
    player_information_dict['Foreign Policy'] = playerdata[4]
    player_information_dict['Military Capacity'] = playerdata[5]
    player_information_dict['Trade Fee'] = playerdata[6]
    player_information_dict['Status'] = playerdata[28]
    
    # get victory condition data
    victory_conditions_list = ast.literal_eval(playerdata[8])
    player_information_dict['Victory Conditions Data']['Conditions List'] = victory_conditions_list
    vc_results = checks.check_victory_conditions(game_id, player_id, current_turn_num)
    vc_colors = []
    for entry in vc_results:
        if entry:
            vc_colors.append('#00ff00')
        else:
            vc_colors.append('#ff0000')
    player_information_dict['Victory Conditions Data']['Color List'] = vc_colors

    # resource data
    player_information_dict['Resource Data']['Class List'] = ['dollars', 'political', 'technology', 'coal', 'oil', 'green', 'basic', 'common', 'advanced', 'uranium', 'rare']
    player_information_dict['Resource Data']['Name List'] = RESOURCE_LIST
    stored_list = []
    income_list = []
    rate_list = []
    for j in range(9, 20):
        data = ast.literal_eval(playerdata[j])
        stored_list.append(f'{data[0]}/{data[1]}')
        income_list.append(data[2])
        rate_list.append(f'{data[3]}%')
    player_information_dict['Resource Data']['Stored List'] = stored_list
    player_information_dict['Resource Data']['Income List'] = income_list
    player_information_dict['Resource Data']['Rate List'] = rate_list

    # alliance data
    alliance_count, alliance_capacity = get_alliance_count(game_id, playerdata)
    player_information_dict['Alliance Data']['Name List'] = list(misc_data_dict["allianceTypes"].keys())
    alliance_colors = []
    alliance_data = [False, False, False, False]
    if 'Defensive Agreements' in player_research_list:
        alliance_data[0] = True
    if 'Peace Accords' in player_research_list:
        alliance_data[1] = True
    if 'Research Exchange' in player_research_list:
        alliance_data[2] = True
    if 'Trade Routes' in player_research_list:
        alliance_data[3] = True
    for entry in alliance_data:
        if entry:
            alliance_colors.append('#00ff00')
        else:
            alliance_colors.append('#ff0000')
    player_information_dict['Alliance Data']['Header'] = f'Alliances ({alliance_count}/{alliance_capacity})'
    player_information_dict['Alliance Data']['Color List'] = alliance_colors

    # missile data
    missile_data = ast.literal_eval(playerdata[21])
    player_information_dict['Missile Data']['Standard'] = f'{missile_data[0]}x Standard Missiles'
    player_information_dict['Missile Data']['Nuclear'] = f'{missile_data[1]}x Nuclear Missiles'

    # relations data
    relation_colors = ['#000000'] * 10
    relations_status_list = ['-'] * 10
    for index, nation_name in enumerate(nation_name_list):
        player_id_2 = nation_name_list.index(nation_name) + 1
        if nation_name == player_information_dict['Nation Name']:
            continue
        elif wardata.are_at_war(player_id, player_id_2):
            relation_colors[index] = '#ff0000'
            relations_status_list[index] = "At War"
        elif alliance_table.are_allied(player_information_dict['Nation Name'], nation_name):
            relation_colors[index] = '#3c78d8'
            relations_status_list[index] = "Allied"
        else:
            relation_colors[index] = '#00ff00'
            relations_status_list[index] = 'Neutral'
    while len(nation_name_list) < 10:
        nation_name_list.append('-')
    player_information_dict['Relations Data']['Name List'] = nation_name_list
    player_information_dict['Relations Data']['Color List'] = relation_colors
    player_information_dict['Relations Data']['Status List'] = relations_status_list

    # upkeep manager data
    upkeep_data = ast.literal_eval(playerdata[23])
    player_information_dict['Upkeep Manager']['Coal'] = upkeep_data[0]
    player_information_dict['Upkeep Manager']['Oil'] = upkeep_data[1]
    player_information_dict['Upkeep Manager']['Green Energy'] = upkeep_data[2]
    player_information_dict['Upkeep Manager']['Total'] = upkeep_data[3]

    # misc info data
    misc_info = ast.literal_eval(playerdata[24])
    player_information_dict['Misc Info']['Capital Resource'] = misc_info[0]
    player_information_dict['Misc Info']['Owned Regions'] = misc_info[1]
    player_information_dict['Misc Info']['Occupied Regions'] = misc_info[2]
    player_information_dict['Misc Info']['Undeveloped Regions'] = misc_info[3]

    # income details
    income_details = ast.literal_eval(playerdata[25])
    for i in range(len(income_details)):
        income_details[i] = income_details[i].replace('&Tab;', '&nbsp;&nbsp;&nbsp;&nbsp;')
    income_str = "<br>".join(income_details)
    player_information_dict['Income Details'] = income_str

    # research details
    research_details = player_research_list
    research_str = "<br>".join(research_details)
    player_information_dict['Research Details'] = research_str

    return player_information_dict

def check_for_winner(full_game_id, player_count, current_turn_num):
    '''
    Spaghetti code that checks if a player has won the game and ends the game if so.
    '''
    playerdata_filepath = f'gamedata/{full_game_id}/playerdata.csv'
    player_has_won = False
    for i in range(player_count):
        player_id = i + 1
        victory_list = checks.check_victory_conditions(full_game_id, player_id, current_turn_num)
        if victory_list == [True, True, True]:
            player_has_won = True
            break
    if player_has_won:
        game_name = get_game_name(full_game_id)
        current_date = datetime.today().date()
        current_date_string = current_date.strftime("%m/%d/%Y")
        with open('active_games.json', 'r') as json_file:
            active_games_dict = json.load(json_file)
        active_games_dict[full_game_id]["Game Active"] = False
        with open('active_games.json', 'w') as json_file:
            json.dump(active_games_dict, json_file, indent=4)
        with open('game_records.json', 'r') as json_file:
            game_records_dict = json.load(json_file)
        player_data_dict = {}
        playerdata_list = read_file(playerdata_filepath, 1)
        for index, playerdata in enumerate(playerdata_list):
            player_data_entry_dict = {
                "Nation Name": "",
                "Color": "",
                "Government": "",
                "Foreign Policy": "",
                "Score": 0,
                "Victory": 0
            }
            player_id = index + 1
            player_global_id = playerdata[29]
            player_data_entry_dict["Nation Name"] = playerdata[1]
            player_data_entry_dict["Color"] = playerdata[2]
            player_data_entry_dict["Government"] = playerdata[3]
            player_data_entry_dict["Foreign Policy"] = playerdata[4]
            victory_list = checks.check_victory_conditions(full_game_id, player_id, current_turn_num)
            player_score = 0
            for entry in victory_list:
                if entry:
                    player_score += 1
            player_data_entry_dict["Score"] = player_score
            if player_data_entry_dict["Score"] == 3:
                player_data_entry_dict["Victory"] = 1
            player_data_dict[player_global_id] = player_data_entry_dict
        game_records_dict[game_name]["Player Data"] = player_data_dict
        game_records_dict[game_name]["Statistics"]["Game End Turn"] = current_turn_num
        game_records_dict[game_name]["Statistics"]["Game Ended"] = current_date_string
        game_records_dict[game_name]["Statistics"]["Game Started"] = active_games_dict[full_game_id]["Statistics"]["Game Started"]
        start_date = game_records_dict[game_name]["Statistics"]["Game Started"]
        current_date_obj = datetime.strptime(current_date_string, "%m/%d/%Y")
        start_date_obj = datetime.strptime(start_date, "%m/%d/%Y")
        date_difference = current_date_obj - start_date_obj
        game_records_dict[game_name]["Statistics"]["Days Ellapsed"] = date_difference.days
        with open('game_records.json', 'w') as json_file:
            json.dump(game_records_dict, json_file, indent=4)

        return player_has_won

def get_game_name(full_game_id):
    with open('active_games.json', 'r') as json_file:
        active_games_dict = json.load(json_file)
    game_name = active_games_dict[full_game_id]["Game Name"]
    return game_name

def get_map_name(game_id):
    '''Retrieves map name string given a game id.'''
    full_game_id = f'game{game_id}'
    with open('active_games.json', 'r') as json_file:
        active_games_dict = json.load(json_file)
    map_name = active_games_dict[full_game_id]["Information"]["Map"]
    return map_name

def get_current_turn_num(game_id):
    '''Gets current turn number given game id.'''
    full_game_id = f'game{game_id}'
    with open('active_games.json', 'r') as json_file:
        active_games_dict = json.load(json_file)
    try:
        current_turn_num = int(active_games_dict[full_game_id]["Statistics"]["Current Turn"])
    except:
        current_turn_num = active_games_dict[full_game_id]["Statistics"]["Current Turn"]
    return current_turn_num

def update_turn_num(game_id):
    '''Updates the turn number given game id.'''
    full_game_id = f'game{game_id}'
    with open('active_games.json', 'r') as json_file:
        active_games_dict = json.load(json_file)
    current_turn_num = int(active_games_dict[full_game_id]["Statistics"]["Current Turn"])
    current_turn_num += 1
    active_games_dict[full_game_id]["Statistics"]["Current Turn"] = str(current_turn_num)
    with open('active_games.json', 'w') as json_file:
        json.dump(active_games_dict, json_file, indent=4)

def identify(action):
    ACTIONS_LIST = ['Surrender', 'White Peace', 'Purchase', 'Research', 'Remove', 'Build', 'Alliance Create', 'Alliance Join', 'Alliance Leave', 'Republic', 'Steal', 'Buy', 'Sell', 'Make', 'Withdraw', 'Disband', 'Deploy', 'War', 'Launch', 'Move', 'Event']
    for action_type in ACTIONS_LIST:
        if action_type.lower() == action[:len(action_type)].lower():
            return action_type
    return None

def get_library(game_id):
    '''
    Returns a dictionary containing all game terms. Use this to check validity of actions.
    '''
    
    # get game data
    playerdata_filepath = f'gamedata/{game_id}/playerdata.csv'
    playerdata_list = read_file(playerdata_filepath, 1)
    alliance_table = AllianceTable(game_id)
    alliance_name_list = []
    for alliance in alliance_table:
        alliance_name_list.append(alliance.name)

    #get scenario files
    agenda_data_dict = get_scenario_dict(game_id, "Agendas")
    improvement_data_dict = get_scenario_dict(game_id, "Improvements")
    research_data_dict = get_scenario_dict(game_id, "Technologies")
    unit_data_dict = get_scenario_dict(game_id, "Units")
    misc_data_dict = get_scenario_dict(game_id, "Misc")

    #create library of game terms
    library = {
        'Nation Name List': [playerdata[1] for playerdata in playerdata_list],
        'Research Name List': list(agenda_data_dict.keys()) + list(research_data_dict.keys()),
        'Improvement List': list(improvement_data_dict.keys()),
        'Alliance Type List': list(misc_data_dict["allianceTypes"].keys()),
        'Alliance Name List': alliance_name_list,
        'Resource Name List': RESOURCE_LIST,
        'Missile Type List': list(misc_data_dict["missiles"].keys()),
        'Unit Name List': list(unit_data_dict.keys()),
        'Unit Abbreviation List': [unit['Abbreviation'] for unit in unit_data_dict.values()],
        'War Justification Name List': ['Animosity', 'Border Skirmish', 'Conquest', 'Annexation', 'Independence', 'Subjugation']
    }

    return library

def run_end_of_turn_checks(game_id, current_turn_num, player_count):
    
    checks.prune_alliances(game_id)
    for i in range(player_count):
        player_id = i + 1
        #update playerdata improvement counts
        checks.update_improvement_count(game_id, player_id)
    checks.update_military_capacity(game_id)
    for i in range(player_count):
        player_id = i + 1
        #check refinery ratios
        checks.ratio_check(game_id, player_id)
        #check military capacity
        checks.remove_excess_units(game_id, player_id)
        #refresh improvement count
        checks.update_improvement_count(game_id, player_id)
        #update stockpile limits in playerdata
        checks.update_stockpile_limits(game_id, player_id)
    #update income in playerdata
    checks.update_income(game_id)
    #update misc info and trade tax in playerdata
    for i in range(player_count):
        player_id = i + 1
        checks.update_misc_info(game_id, player_id)
        checks.update_trade_tax(game_id, player_id)
    #update records
    checks.update_records(game_id, current_turn_num)
    #update income in playerdata now that records have been updated (important for political power bonuses)
    checks.update_income(game_id)


#GENERAL PURPOSE GLOBAL FUNCTIONS
################################################################################

def read_file(filepath, skip_value):

    '''
    Reads a csv file given a filepath and returns it as a list of lists.

    Parameters:
    - filepath: The full filepath to the desired file relative to core.py.
    - skip_value: A positive integer value representing how many of the first rows to skip. Usually 0-2.
    '''
    output = []
    with open(filepath, 'r') as file:
        reader = csv.reader(file)
        for i in range(0, skip_value):
            next(reader, None)
        for row in reader:
            if row != []:
                output.append(row)
    return output

def read_rmdata(rmdata_filepath, current_turn_num, refine, keep_header):
    '''
    Reads rmdata.csv and generates a list of all currently relevant transactions.

    Parameters:
    - rmdata_filepath: The full relative filepath to rmdata.csv.
    - current_turn_num: An integer number representing the game's current turn number.
    - refine: A count representing how many turns back you want of resource market data. Define as a positive integer or False if you want all records.
    - keep_header: A boolean value. Enter as True if you don't care about the header rows being in your data.
    '''

    #Get list of all transactions
    rmdata_list = []
    if keep_header == True:
        with open(rmdata_filepath, 'r') as file:
            reader = csv.reader(file)
            for row in reader:
                if row != []:
                    rmdata_list.append(row)
    if keep_header == False:
        with open(rmdata_filepath, 'r') as file:
                reader = csv.reader(file)
                next(reader,None)
                for row in reader:
                    if row != []:
                        rmdata_list.append(row)
    #Refine list as needed
    rmdata_refined_list = []
    if refine:
        limit = current_turn_num - refine
        for transaction in rmdata_list:
            transaction[0] = int(transaction[0])
            transaction[3] = int(transaction[3])
            if transaction[0] >= limit:
                rmdata_refined_list.append(transaction)
    elif refine == False:
        for transaction in rmdata_list:
            transaction[0] = int(transaction[0])
            transaction[3] = int(transaction[3])
            rmdata_refined_list.append(transaction)
    return rmdata_refined_list


#DIPLOMACY SUB-FUNCTIONS
################################################################################

def get_alliance_count(game_id: str, playerdata: list[list]) -> Tuple[int, int]:
    """
    Gets a count of a player's active alliances and their total alliance capacity.

    Params:
        game_id (str): Game ID string.
        playerdata (list): A single playerdata list from playerdata.csv.

    Returns:
        Tuple:
            int: Alliance count.
            int: Alliance limit.
    """

    nation_name = playerdata[1]
    player_research_list = ast.literal_eval(playerdata[26])
    with open('active_games.json', 'r') as json_file:
        active_games_dict = json.load(json_file)
    
    alliance_count = 0
    alliance_table = AllianceTable(game_id)
    alliance_report_dict = alliance_table.report(nation_name)
    alliance_count = alliance_report_dict["Total"] - alliance_report_dict["Non-Aggression Pact"]
    
    alliance_limit = 2
    if playerdata[3] == 'Republic':
        alliance_limit += 1
    if 'Power Broker' in player_research_list:
        alliance_limit += 1
    if 'Improved Logistics' in player_research_list:
        alliance_limit += 1
    if "Shared Fate" in active_games_dict[game_id]["Active Events"]:
        if active_games_dict[game_id]["Active Events"]["Shared Fate"]["Effect"] == "Cooperation":
            alliance_limit += 1

    return alliance_count, alliance_limit

def get_subjects(playerdata_list, overlord_nation_name, subject_type):
    '''Returns a list of all player ids that are subjects of the given nation name.'''
    player_id_list = []
    for index, playerdata in enumerate(playerdata_list):
        status = playerdata[28]
        if overlord_nation_name in status and subject_type in status:
            selected_nation_id = index + 1
            player_id_list.append(selected_nation_id)
    return player_id_list


#ECONOMIC SUB-FUNCTIONS
################################################################################

def get_economy_info(playerdata_list, request_list):
    '''Generates a list of lists of lists for requested economy information. Sub-function for action functions.'''
    index_list = []
    for resource in request_list:
        if resource == 'Dollars':
            index_list.append(9)
        elif resource == 'Political Power':
            index_list.append(10)
        elif resource == 'Technology':
            index_list.append(11)
        elif resource == 'Coal':
            index_list.append(12)
        elif resource == 'Oil':
            index_list.append(13)
        elif resource == 'Green Energy':
            index_list.append(14)
        elif resource == 'Basic Materials':
            index_list.append(15)
        elif resource == 'Common Metals':
            index_list.append(16)
        elif resource == 'Advanced Metals':
            index_list.append(17)
        elif resource == 'Uranium':
            index_list.append(18)
        elif resource == 'Rare Earth Elements':
            index_list.append(19)
    economy_masterlist = []
    for playerdata in playerdata_list:
        economy_list = []
        for i in index_list:
            resource_data_list = ast.literal_eval(playerdata[i])
            economy_list.append(resource_data_list)
        economy_masterlist.append(economy_list)
    return economy_masterlist

def round_total_income(total_income):
    '''Forcibly rounds a given income number to two digits. Sub-function of update_income().'''
    total_income = round(total_income, 2)
    total_income = "{:.2f}".format(total_income)
    return total_income

def update_stockpile(stockpile, cost):
    '''Updates a stockpile by subtracting the improvement cost and then rounding it. Meant to be saved to economydata_masterlist.'''
    stockpile -= cost
    stockpile = round_total_income(stockpile)
    return stockpile

def get_unit_count_list(player_id, game_id):
    
    unit_data_dict = get_scenario_dict(game_id, "Units")
    unit_name_list = sorted(unit_data_dict.keys())
    with open(f'gamedata/{game_id}/regdata.json', 'r') as json_file:
        regdata_dict = json.load(json_file)

    count_list = []
    for unit_name in unit_name_list:
        count = 0
        for region_id in regdata_dict:
            region_unit = Unit(region_id, game_id)
            if region_unit.owner_id == player_id and region_unit.name == unit_name:
                count += 1
        count_list.append(count)

    return count_list

def create_player_yield_dict(player_id: int, game_id: str) -> dict:
    """
    Given a player, this function creates the initial dictionary with the yields of all improvements.

    Params:
        player_id (int): Player ID.
        game_id (str): Game ID.

    Returns:
        dict: Yield dictionary detailing income and multiplier for every improvement.
    """
    
    # load game info
    improvement_data_dict = get_scenario_dict(game_id, "Improvements")
    technology_data_dict = get_scenario_dict(game_id, "Technologies")
    agenda_data_dict = get_scenario_dict(game_id, "Agendas")
    playerdata_filepath = f'gamedata/{game_id}/playerdata.csv'
    playerdata_list = read_file(playerdata_filepath, 1)

    # load player info
    playerdata = playerdata_list[player_id - 1]
    player_research_list = ast.literal_eval(playerdata[26])

    yield_dict = {}
    for improvement_name, improvement_data in improvement_data_dict.items():
        yield_dict[improvement_name] = {}
        for resource_name in improvement_data["Income"]:
            inner_dict = {
                "Income": improvement_data["Income"][resource_name],
                "Income Multiplier": 1
            }
            yield_dict[improvement_name][resource_name] = inner_dict
    
    # get modifiers from each technology and agenda
    for tech_name in player_research_list:   
        if tech_name in technology_data_dict:
            tech_dict = technology_data_dict[tech_name]
        elif tech_name in agenda_data_dict:
            tech_dict = agenda_data_dict[tech_name]
        for target in tech_dict["Modifiers"]: 
            if target not in improvement_data_dict:
                # skip over effects that are not affecting improvements
                continue
            improvement_name = target
            for resource_name, modifier_dict in tech_dict["Modifiers"][improvement_name].items():
                if "Income" in modifier_dict:
                    yield_dict[improvement_name][resource_name]["Income"] += modifier_dict["Income"]
                elif "Income Multiplier" in modifier_dict:
                    yield_dict[improvement_name][resource_name]["Income Multiplier"] += modifier_dict["Income Multiplier"]

    return yield_dict

def create_player_upkeep_dict(player_id: int, game_id: str) -> dict:
    """
    Given a player, this function creates the initial dictionary with the upkeep of all improvements and units.

    Params:
        player_id (int): Player ID.
        game_id (str): Game ID.

    Returns:
        dict: Upkeep dictionary detailing upkeep and upkeep multiplier for every improvement.
    """
    
    # load game info
    unit_data_dict = get_scenario_dict(game_id, "Units")
    improvement_data_dict = get_scenario_dict(game_id, "Improvements")
    technology_data_dict = get_scenario_dict(game_id, "Technologies")
    agenda_data_dict = get_scenario_dict(game_id, "Agendas")
    playerdata_filepath = f'gamedata/{game_id}/playerdata.csv'
    playerdata_list = read_file(playerdata_filepath, 1)

    # load player info
    playerdata = playerdata_list[player_id - 1]
    player_research_list = ast.literal_eval(playerdata[26])

    upkeep_dict = {}
    for improvement_name, improvement_data in improvement_data_dict.items():
        upkeep_dict[improvement_name] = {}
        for resource_name in improvement_data["Upkeep"]:
            inner_dict = {
                "Upkeep": improvement_data["Upkeep"][resource_name],
                "Upkeep Multiplier": 1
            }
            upkeep_dict[improvement_name][resource_name] = inner_dict
    for unit_name, unit_data in unit_data_dict.items():
        upkeep_dict[unit_name] = {}
        for resource_name in unit_data["Upkeep"]:
            inner_dict = {
                "Upkeep": unit_data["Upkeep"][resource_name],
                "Upkeep Multiplier": 1
            }
            upkeep_dict[unit_name][resource_name] = inner_dict
    
    # get modifiers from each technology and agenda
    for tech_name in player_research_list:
        if tech_name in technology_data_dict:
            tech_dict = technology_data_dict[tech_name]
        elif tech_name in agenda_data_dict:
            tech_dict = agenda_data_dict[tech_name]
        for target in tech_dict["Modifiers"]: 
            if target not in improvement_data_dict and target not in unit_data_dict:
                # skip over effects that are not improvements or units
                continue
            for resource_name, modifier_dict in tech_dict["Modifiers"][target].items():
                if "Upkeep" in modifier_dict:
                    upkeep_dict[target][resource_name]["Upkeep"] += modifier_dict["Upkeep"]
                elif "Upkeep Multiplier" in modifier_dict:
                    upkeep_dict[target][resource_name]["Upkeep Multiplier"] += modifier_dict["Upkeep Multiplier"]

    return upkeep_dict

def calculate_upkeep(upkeep_type: str, player_upkeep_dict: dict, player_count_dict: dict) -> float:
    """
    Calculates the total upkeep sum for a player given a specific upkeep type.

    Params:
        upkeep_type (str): Either Dollars, Oil, Uranium, or Energy.
        player_upkeep_dict (dict): Taken from create_player_upkeep_dict().
        player_count_dict (dict): A count of a player's units or improvements.

    Returns:
        float: Upkeep sum.
    """
    sum = 0.0
    for name, count in player_count_dict.items():
        if upkeep_type in player_upkeep_dict[name]:
            resource_upkeep_dict = player_upkeep_dict[name][upkeep_type]
            name_upkeep = resource_upkeep_dict["Upkeep"] * resource_upkeep_dict["Upkeep Multiplier"]
            sum += name_upkeep * count

    return sum


#WAR SUB-FUNCTIONS
################################################################################

def read_military_capacity(player_military_capacity_data):
    player_military_capacity_list = player_military_capacity_data.split('/')
    used_mc = int(player_military_capacity_list[0])
    total_mc = float(player_military_capacity_list[1])
    return used_mc, total_mc

def check_military_capacity(player_military_capacity_data, amount):
    '''Calculates if a player has an amount of military capacity available.'''
    player_military_capacity_list = player_military_capacity_data.split('/')
    used_mc = int(player_military_capacity_list[0])
    total_mc = float(player_military_capacity_list[1])
    if used_mc + amount > total_mc:
        return False
    return True

def add_truce_period(full_game_id, signatories_list, war_outcome, current_turn_num):
    '''Creates a truce period between the players marked in the signatories list. Length depends on war outcome.'''

    #get core lists
    trucedata_filepath = f'gamedata/{full_game_id}/trucedata.csv'
    trucedata_list = read_file(trucedata_filepath, 0)

    #determine truce period length
    if war_outcome == 'Animosity' or war_outcome == 'Border Skirmish':
        truce_length = 4
    else:
        truce_length = 8

    #generate output
    truce_id = len(trucedata_list)
    signatories_list.insert(0, truce_id)
    signatories_list.append(current_turn_num + truce_length)
    trucedata_list.append(signatories_list)

    #update trucedata.csv
    with open(trucedata_filepath, 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerows(trucedata_list)

def check_for_truce(trucedata_list, player_id_1, player_id_2, current_turn_num):
    '''Checks for a truce between two players. Returns True if one is found, otherwise returns False.'''
    for truce in trucedata_list:
        attacker_truce = ast.literal_eval(truce[player_id_1])
        defender_truce = ast.literal_eval(truce[player_id_2])
        if attacker_truce and defender_truce and int(truce[11]) > current_turn_num:
            return True
    return False


#MISC SUB-FUNCTIONS
################################################################################

def date_from_turn_num(current_turn_num):
    remainder = current_turn_num % 4
    if remainder == 0:
        season = 'Winter'
    elif remainder == 1:
        season = 'Spring'
    elif remainder == 2:
        season = 'Summer'
    elif remainder == 3:
        season = 'Fall'
    quotient = current_turn_num // 4
    year = 2021 + quotient
    if season == 'Winter':
        year -= 1
    return season, year

def get_adjacency_list(regdata_list, region_id):
    for region in regdata_list:
         if region[0] == region_id:
            adjacency_list = ast.literal_eval(region[8])
            return adjacency_list

def get_nation_info(playerdata_list):
    '''Gets each nation's name, color, government, and fp info. Sub-function for resolve_research_actions()'''
    nation_info_masterlist = []
    for player in playerdata_list:
        player_nation_name = player[1]
        player_color = player[2]
        player_government = player[3]
        player_fp = player[4]
        player_military_capacity = player[5]
        player_trade_fee = player[6]
        if player_trade_fee != 'No Trade Fee':
            n = int(player_trade_fee[0])
            d = int(player_trade_fee[2])
            player_trade_fee = float(n / d)
        else:
            player_trade_fee = 0
        nation_info_list = [player_nation_name, player_color, player_government, player_fp, player_military_capacity, player_trade_fee]
        nation_info_masterlist.append(nation_info_list)
    return nation_info_masterlist

def search_and_destroy(game_id, player_id, target_improvement):
    '''
    Searches for a specific improvement and removes it.
    '''
    with open(f'gamedata/{game_id}/regdata.json', 'r') as json_file:
        regdata_dict = json.load(json_file)
    
    # find all regions belonging to a player with target improvement
    candidate_region_ids = []
    for region_id in regdata_dict:
        region = Region(region_id, game_id)
        region_improvement = Improvement(region_id, game_id)
        if region_improvement.name == target_improvement and player_id == region.owner_id:
            candidate_region_ids.append(region_id)

    # randomly select one of the candidate regions
    random.shuffle(candidate_region_ids)
    chosen_region_id = candidate_region_ids.pop()
    target_region_improvement = Improvement(chosen_region_id, game_id)
    target_region_improvement.clear()
    
    return chosen_region_id

def search_and_destroy_unit(game_id, player_id, desired_unit_name):
    '''
    Randomly destroys one unit of a given type belonging to a specific player.
    '''
    with open(f'gamedata/{game_id}/regdata.json', 'r') as json_file:
        regdata_dict = json.load(json_file)

    # get list of regions with desired_unit_id owned by player_id
    candidate_region_ids = []
    if desired_unit_name in unit_ids:
        for region_id in regdata_dict:
            region_unit = Unit(region_id, game_id)
            if region_unit.name == desired_unit_name and region_unit.owner_id == player_id:
                candidate_region_ids.append(region_id)
    elif desired_unit_name == 'ANY':
        for region_id in regdata_dict:
            region_unit = Unit(region_id, game_id)
            if region_unit.owner_id == player_id:
                candidate_region_ids.append(region_id)

    # randomly select one of the candidate regions
    random.shuffle(candidate_region_ids)
    chosen_region_id = candidate_region_ids.pop()
    target_region_unit = Unit(chosen_region_id, game_id)
    target_region_unit.clear()

    return chosen_region_id

def verify_ratio(game_id, improvement_count_list, improvement_name):

    improvement_data_dict = get_scenario_dict(game_id, "Improvements")
    refinery_list = ['Advanced Metals Refinery', 'Oil Refinery', 'Uranium Refinery']
    improvement_name_list = sorted(improvement_data_dict.keys())
    
    if improvement_name in refinery_list:
        if improvement_name == 'Advanced Metals Refinery':
            ref_index = improvement_name_list.index('Advanced Metals Refinery')
            sub_index = improvement_name_list.index('Advanced Metals Mine')
        elif improvement_name == 'Oil Refinery':
            ref_index = improvement_name_list.index('Oil Refinery')
            sub_index = improvement_name_list.index('Oil Well')
        elif improvement_name == 'Uranium Refinery':
            ref_index = improvement_name_list.index('Uranium Refinery')
            sub_index = improvement_name_list.index('Uranium Mine')
        ref_count = improvement_count_list[ref_index]
        sub_count = improvement_count_list[sub_index]
        if sub_count == 0:
            return False
        if (ref_count + 1) / sub_count > 0.5:
            return False
    return True

def verify_required_research(required_research, player_research):
    '''
    Checks if a certain research has been researched by a specific player.

    Parameters:
    - required_research: The name of the research in question (string).
    - player_research: A list of all research researched by a specific player.
    '''
    if required_research != None:
        if required_research not in player_research:
            return False
    return True

def has_capital(player_id, game_id):
    '''
    Checks if a player has a capital in their territory.
    '''
    regdata_filepath = f'gamedata/{game_id}/regdata.json'
    with open(regdata_filepath, 'r') as json_file:
        regdata_dict = json.load(json_file)

    for region_id in regdata_dict:
        region = Region(region_id, game_id)
        region_improvement = Improvement(region_id, game_id)
        if region.owner_id == player_id and region_improvement.name == 'Capital':
            return True
        
    return False

def get_scenario_dict(game_id, dictionary_name):
    '''
    Gets a dictionary from the chosen scenario.
    '''

    with open('active_games.json', 'r') as json_file:
        active_games_dict = json.load(json_file)

    if game_id != "TBD":
        scenario_name = active_games_dict[game_id]["Information"]["Scenario"]
        scenario = scenario_name.lower()
    else:
        scenario = "standard"

    filename = f"{dictionary_name.lower()}.json"
    dictionary_filepath = f"scenarios/{scenario}/{filename}"

    with open(dictionary_filepath, 'r') as json_file:
        chosen_dictionary = json.load(json_file)

    return chosen_dictionary

def get_lowest_in_record(game_id, record_name):
    # get core lists
    playerdata_filepath = f'gamedata/{game_id}/playerdata.csv'
    playerdata_list = read_file(playerdata_filepath, 1)

    # get nation names
    nation_name_list = []
    for playerdata in playerdata_list:
        nation_name_list.append(playerdata[1])
    
    #get lowest
    if record_name != "most_transactions":
        record_filepath = f'gamedata/{game_id}/{record_name}.csv'
        record_list = read_file(record_filepath, 0)
        candidates = []
        for index, record in enumerate(record_list):
            if index == 0:
                continue
            if record_name == 'strongest_economy':
                value = float(record[-1])
            else:
                value = int(record[-1])
            nation_name = nation_name_list[index - 1]
            candidates.append([nation_name, value])
        sorted_candidates = sorted(candidates, key = lambda x: x[-1], reverse = False)
        return sorted_candidates[0][0]
    else:
        pass

def get_top_three_transactions(game_id):
    """
    Temporary cringe function to read transactions.
    """
    with open('active_games.json', 'r') as json_file:
        active_games_dict = json.load(json_file)
    
    transactions_dict = active_games_dict[game_id]["Transactions Record"]
    sorted_dict = dict(
        sorted(
            transactions_dict.items(),
            key = lambda item: (-item[1], item[0])
        )
    )

    top_three = tuple(sorted_dict.keys())[:3]
    top_three_list = []
    for index, key in enumerate(top_three):
        top_three_list.append(f"{index+1}. {key} ({sorted_dict[key]})")

    return tuple(top_three_list)


# DISGUSTING GLOBAL VARIABLES
################################################################################

# unfortunately like pulling teeth significant refactoring is required to remove some of these - I'm workin' on it!

#file headers
player_data_header = ["Player", "Nation Name", "Color", "Government", "Foreign Policy", "Military Capacity", "Trade Fee", "Stability Data", "Victory Conditions", "Dollars", "Political Power", "Technology", "Coal", "Oil", "Green Energy", "Basic Materials", "Common Metals", "Advanced Metals", "Uranium", "Rare Earth Elements", "Alliance Data", "Missile Data", "Diplomatic Relations", "Upkeep Manager", "Miscellaneous Information", "Income Details", "Completed Research", "Improvement Count", "Status", "Global ID"]
rmdata_header = ["Turn", "Nation", "Bought/Sold", "Count", "Resource Exchanged"]
rm_header = ["Turn", "Nation", "Bought/Sold", "Count", "Resource Exchanged"]
trucedata_header = ['Truce ID', 'Player #1', 'Player #2', 'Player #3', 'Player #4', 'Player #5', 'Player #6', 'Player #7', 'Player #8', 'Player #9', 'Player #10', 'Expire Turn #']

#government and fp list data
republic_rates = [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100]
technocracy_rates = [100, 100, 120, 100, 100, 100, 100, 100, 100, 100, 100]
oligarchy_rates = [120, 100, 100, 120, 120, 120, 100, 100, 100, 100, 100]
totalitarian_rates = [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100]
remnant_rates = [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100]
protectorate_rates = [100, 80, 100, 100, 100, 100, 120, 100, 100, 100, 100]
military_junta_rates = [100, 100, 80, 100, 100, 100, 100, 100, 100, 100, 100]
crime_syndicate_rates = [80, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100]

#war and unit/improvement list data
RESOURCE_LIST = ['Dollars', 'Political Power', 'Technology', 'Coal', 'Oil', 'Green Energy', 'Basic Materials', 'Common Metals', 'Advanced Metals', 'Uranium', 'Rare Earth Elements']
unit_ids = ['IN', 'AR', 'ME', 'SF', 'MO', 'LT', 'HT', 'BT']

#victory conditions
easy_list = [
    "Breakthrough",
    "Diversified Economy",
    "Energy Economy",
    "Industrial Focus",
    "Leading Defense",
    "Major Exporter",
    "Reconstruction Effort",
    "Secure Strategic Resources"
]
normal_list = [
    "Backstab",
    "Diversified Army",
    "Hegemony",
    "New Empire",
    "Nuclear Deterrent",
    "Reliable Ally",
    "Sphere of Influence",
    "Warmonger"
]
hard_list = [
    "Economic Domination",
    "Influence Through Trade",
    "Military Superpower",
    "Scientific Leader",
    "Territorial Control"
]

#color dictionaries
player_colors_hex = {
    "Brown": "#603913",
    "Coral": "#ff974e",
    "Dark Blue": "#003b84",
    "Dark Green": "#105500",
    "Dark Purple": "#5a009d",
    "Dark Red": "#b30000",
    "Light Blue": "#0096ff",
    "Light Green": "#5bb000",
    "Light Purple": "#b654ff",
    "Light Red": "#ff3d3d",
    "Maroon": "#8b2a1a",
    "Metallic Gold": "#9f8757",
    "Orange": "#ff9600",
    "Pink": "#f384ae",
    "Terracotta": "#b66317",
    "Yellow": "#ffd64b",
    None: "None" 
}

player_colors_rgb = {
    "Brown": (96, 57, 19, 255),
    "Coral": (255, 151, 78, 255),
    "Dark Blue": (0, 59, 132, 255),
    "Dark Green": (16, 85, 0, 255),
    "Dark Purple": (90, 0, 157, 255),
    "Dark Red": (179, 0, 0, 255),
    "Light Blue": (0, 150, 255, 255),
    "Light Green": (91, 176, 0, 255),
    "Light Purple": (182, 84, 255, 255),
    "Light Red": (255, 61, 61, 255),
    "Maroon": (139, 42, 26, 255),
    "Metallic Gold": (159, 135, 87, 255),
    "Orange": (255, 150, 0, 255),
    "Pink": (243, 132, 174, 255),
    "Terracotta": (182, 99, 23, 255),
    "Yellow": (255, 214, 75, 255)
}

player_colors_conversions = {
    "#603913": (96, 57, 19, 255),
    "#ff974e": (255, 151, 78, 255),
    "#003b84": (0, 59, 132, 255),
    "#105500": (16, 85, 0, 255),
    "#5a009d": (90, 0, 157, 255),
    "#b30000": (179, 0, 0, 255),
    "#0096ff": (0, 150, 255, 255),
    "#5bb000": (91, 176, 0, 255),
    "#b654ff": (182, 84, 255, 255),
    "#ff3d3d": (255, 61, 61, 255),
    "#8b2a1a": (139, 42, 26, 255),
    "#9f8757": (159, 135, 87, 255),
    "#ff9600": (255, 150, 0, 255),
    "#f384ae": (243, 132, 174, 255),
    "#b66317": (182, 99, 23, 255),
    "#ffd64b": (255, 214, 75, 255)
}

player_colors_normal_to_occupied = {
    (96, 57, 19, 255): (144, 87, 33, 255),
    (255, 151, 78, 255): (255, 170, 111, 255),
    (0, 59, 132, 255): (0, 78, 174, 255),
    (16, 85, 0, 255): (24, 126, 0, 255),
    (90, 0, 157, 255): (126, 0, 221, 255),
    (179, 0, 0, 255): (212, 0, 0, 255),
    (0, 150, 255, 255): (87, 186, 255, 255),
    (91, 176, 0, 255): (110, 212, 0, 255),
    (182, 84, 255, 255): (200, 127, 255, 255),
    (255, 61, 61, 255): (255, 102, 102, 255),
    (139, 42, 26, 255): (184, 56, 35, 255),
    (159, 135, 87, 255): (175, 154, 110, 255),
    (255, 150, 0, 255): (255, 175, 61, 255),
    (243, 132, 174, 255): (244, 160, 192, 255),
    (182, 99, 23, 255): (197, 116, 41, 255),
    (255, 214, 75, 255): (255, 230, 142, 255),
}

player_colors_normal_to_occupied_hex = {
    (96, 57, 19, 255): "#905721",
    (255, 151, 78, 255): "#ffaa6f",
    (0, 59, 132, 255): "#004eae",
    (16, 85, 0, 255): "#187e00",
    (90, 0, 157, 255): "#7e00dd",
    (179, 0, 0, 255): "#d40000",
    (0, 150, 255, 255): "#57baff",
    (91, 176, 0, 255): "#6ed400",
    (182, 84, 255, 255): "#c87fff",
    (255, 61, 61, 255): "#ff6666",
    (139, 42, 26, 255): "#b83823",
    (159, 135, 87, 255): "#af9a6e",
    (255, 150, 0, 255): "#ffaf3d",
    (243, 132, 174, 255): "#f4a0c0",
    (182, 99, 23, 255): "#c57429",
    (255, 214, 75, 255): "#ffe68e",
}

resource_colors = {
    "Coal": (166, 124, 82, 255),
    "Oil": (96, 57, 19, 255),
    "Basic Materials": (149, 149, 149, 255),
    "Common Metals": (99, 99, 99, 255),
    "Advanced Metals": (71, 157, 223, 255),
    "Uranium": (0, 255, 0, 255),
    "Rare Earth Elements": (241, 194, 50, 255)
}