#STANDARD IMPORTS
import ast
from queue import PriorityQueue 
import csv
from datetime import datetime
import json
from operator import itemgetter
import os
import re
import uuid

#UWS SOURCE IMPORTS
from app import core
from app import checks
from app import events
from app import palette
from app.wardata import WarData
from app.testing import map_tests
from app.notifications import Notifications
from app.alliance import AllianceTable
from app.alliance import Alliance
from app import map

#ENVIROMENT IMPORTS
from flask import Flask, Blueprint, render_template, request, redirect, url_for, send_file
app = Flask(__name__)
main = Blueprint('main', __name__)
@main.route('/')
def main_function():
    return render_template('index.html')

#SITE FUNCTIONS
################################################################################

#COLOR CORRECTION
def check_color_correction(color):
    swap_list = ['#b30000', '#105500', '#003b84', '#603913', '#8b2a1a', '#5bb000'] 
    if color in swap_list:
        player_color_rgb = core.player_colors_conversions[color]
        color = core.player_colors_normal_to_occupied_hex[player_color_rgb]
    return color

#COLOR NATION NAMES
def color_nation_names(string, full_game_id):
    playerdata_filepath = f'gamedata/{full_game_id}/playerdata.csv'
    nation_name_list = []
    nation_color_list = []
    with open(playerdata_filepath, 'r') as file:
        reader = csv.reader(file)
        next(reader,None)
        for row in reader:
            if row != []:
                nation_name = row[1]
                nation_color = row[2]
                nation_color = check_color_correction(nation_color)
                nation_name_list.append(nation_name)
                nation_color_list.append(nation_color)
    for index, nation_name in enumerate(nation_name_list):
        if nation_name in string:
            string = string.replace(nation_name, f"""<span style="color:{nation_color_list[index]}">{nation_name}</span>""")
    return string
        
#REFINE PLAYERDATA FUNCTION FOR ACTIVE GAMES
def generate_refined_player_list_active(full_game_id, current_turn_num):
    playerdata_list = core.read_file(f'gamedata/{full_game_id}/playerdata.csv', 1)
    refined_player_data_a = []
    refined_player_data_b = []
    for index, playerdata in enumerate(playerdata_list):
        profile_id = playerdata[29]
        gov_fp_string = f"""{playerdata[4]} - {playerdata[3]}"""
        username = player_records_dict[profile_id]["Username"]
        username_str = f"""<a href="profile/{profile_id}">{username}</a>"""
        player_color = playerdata[2]
        player_color = check_color_correction(player_color)
        player_vc_score = 0
        if current_turn_num != 0:
            vc_results = checks.check_victory_conditions(full_game_id, index + 1, current_turn_num)
            for entry in vc_results:
                if entry:
                    player_vc_score += 1
        if player_vc_score > 0:
            refined_player_data_a.append([playerdata[1], player_vc_score, gov_fp_string, username_str, player_color, player_color])
        else:
            refined_player_data_b.append([playerdata[1], player_vc_score, gov_fp_string, username_str, player_color, player_color])
    filtered_player_data_a = sorted(refined_player_data_a, key=itemgetter(0), reverse=False)
    filtered_player_data_a = sorted(filtered_player_data_a, key=itemgetter(1), reverse=True)
    filtered_player_data_b = sorted(refined_player_data_b, key=itemgetter(0), reverse=False)
    refined_player_data = filtered_player_data_a + filtered_player_data_b
    return refined_player_data

#REFINE PLAYERDATA FUNCTION FOR INACTIVE GAMES
def generate_refined_player_list_inactive(game_data):
    refined_player_data_a = []
    refined_player_data_b = []
    players_who_won = []
    for select_profile_id, player_data in game_data.get("Player Data", {}).items():
        player_data_list = []
        player_data_list.append(player_data.get("Nation Name"))
        player_data_list.append(player_data.get("Score"))
        gov_fp_string = f"""{player_data.get("Foreign Policy")} - {player_data.get("Government")}"""
        player_data_list.append(gov_fp_string)
        username = player_records_dict[select_profile_id]["Username"]
        username_str = f"""<a href="profile/{select_profile_id}">{username}</a>"""
        player_data_list.append(username_str)
        player_color = player_data.get("Color")
        player_data_list.append(player_color)
        player_color_occupied_hex = check_color_correction(player_color)
        player_data_list.append(player_color_occupied_hex)
        if player_data.get("Victory") == 1:
            players_who_won.append(player_data.get("Nation Name"))
        if player_data.get("Score") > 0:
            refined_player_data_a.append(player_data_list)
        else:
            refined_player_data_b.append(player_data_list)
    filtered_player_data_a = sorted(refined_player_data_a, key=itemgetter(0), reverse=False)
    filtered_player_data_a = sorted(filtered_player_data_a, key=itemgetter(1), reverse=True)
    filtered_player_data_b = sorted(refined_player_data_b, key=itemgetter(0), reverse=False)
    refined_player_data = filtered_player_data_a + filtered_player_data_b
    return refined_player_data, players_who_won


#CORE SITE PAGES
################################################################################

#GAMES PAGE
@main.route('/games')
def games():
    
    #read json files
    username_list = []
    for profile_id, player_data in player_records_dict.items():
        username_list.append(player_data.get("Username"))
    
    #get dict of active games
    with open('active_games.json', 'r') as json_file:
        active_games_dict = json.load(json_file)

    #read active games
    for game_id, game_data in active_games_dict.items():
        current_turn = game_data["Statistics"]["Current Turn"]
        if current_turn == "Turn N/A":
            continue
        
        match current_turn:

            case "Starting Region Selection in Progress":
                #get title and game link
                game_name = game_data["Game Name"]
                game_data["Title"] = f"""<a href="/{game_id}">{game_name}</a>"""
                #get status
                game_data["Status"] = current_turn
                #get player information
                refined_player_data = []
                playerdata_list = core.read_file(f'gamedata/{game_id}/playerdata.csv', 1)
                for playerdata in playerdata_list:
                    profile_id = playerdata[30]
                    username = player_records_dict[profile_id]["Username"]
                    username_str = f"""<a href="profile/{profile_id}">{username}</a>"""
                    refined_player_data.append([playerdata[1], 0, 'TBD', username_str, '#ffffff', '#ffffff'])
                #get image
                game_map = game_data["Information"]["Map"]
                if game_map == "United States 2.0":
                    game_map = "united_states"
                image_url = url_for('main.get_mainmap', full_game_id=game_id)
                pass

            case "Nation Setup in Progress":
                #get title and game link
                game_name = game_data["Game Name"]
                game_data["Title"] = f"""<a href="/{game_id}">{game_name}</a>"""
                #get status
                game_data["Status"] = current_turn
                #get player information
                refined_player_data = []
                playerdata_list = core.read_file(f'gamedata/{game_id}/playerdata.csv', 1)
                for playerdata in playerdata_list:
                    profile_id = playerdata[30]
                    username = player_records_dict[profile_id]["Username"]
                    username_str = f"""<a href="profile/{profile_id}">{username}</a>"""
                    player_color = playerdata[2]
                    player_color_2 = check_color_correction(player_color)
                    refined_player_data.append([playerdata[1], 0, 'TBD', username_str, player_color, player_color_2])
                #get image
                image_url = url_for('main.get_mainmap', full_game_id=game_id)
                pass

            case _:
                #get title and game link
                game_name = game_data["Game Name"]
                game_data["Title"] = f"""<a href="/{game_id}">{game_name}</a>"""
                #get status
                if game_data["Game Active"]:
                    game_data["Status"] = f"Turn {current_turn}"
                else:
                    game_data["Status"] = "Game Over!"
                #get player information
                refined_player_data = generate_refined_player_list_active(game_id, current_turn)
                #get image
                image_url = url_for('main.get_mainmap', full_game_id=game_id)
                pass
        
        game_data["Playerdata Masterlist"] = refined_player_data
        game_data["image_url"] = image_url
    
    return render_template('temp_games.html', dict = active_games_dict, full_game_id = game_id)

#SETTINGS PAGE
@main.route('/settings')
def settings():
    username_list = []
    for profile_id, player_data in player_records_dict.items():
        username_list.append(player_data.get("Username"))
    return render_template('temp_settings.html', username_list = username_list)

#SETTINGS PAGE - Create Game Procedure
@main.route('/create_game', methods=['POST'])
def create_game():
    
    #get game record dictionaries
    with open('active_games.json', 'r') as json_file:
        active_games_dict = json.load(json_file)
    with open('game_records.json', 'r') as json_file:
        game_records_dict = json.load(json_file)

    #get username list
    username_list = []
    with open('player_records.json', 'r') as json_file:
        player_records_dict = json.load(json_file)
    for profile_id, player_data in player_records_dict.items():
        username_list.append(player_data.get("Username"))
    
    #get values from settings form
    form_data_dict = {
        "Game Name": request.form.get('name_input'),
        "Player Count": request.form.get('pc_dropdown'),
        "Victory Conditions": request.form.get('vc_dropdown'),
        "Map": request.form.get('map_dropdown'),
        "Accelerated Schedule": request.form.get('as_dropdown'),
        "Turn Length": request.form.get('td_dropdown'),
        "Fog of War": request.form.get('fow_dropdown'),
        "Deadlines on Weekends": request.form.get('dow_dropdown'),
        "Scenario": request.form.get('scenario_dropdown')
    }
    profile_ids_list = []
    for index, username in enumerate(username_list):
        #if checked, checkbox returns True. Otherwise returns none.
        add_player_value = request.form.get(username)
        if add_player_value:
            profile_ids_list.append(profile_id_list[index])

    #erase all active games override
    if form_data_dict["Game Name"] == "5EQM8Z5VoLxvxqeP1GAu":
        active_games = [key for key, value in active_games_dict.items() if value.get("Game Active")]
        for active_game_id in active_games:
            active_games_dict[active_game_id] = {
                "Game Name": "Open Game Slot",
                "Game #": 0,
                "Game Active": False,
                "Information": {
                    "Version": "TBD",
                    "Scenario": "TBD",
                    "Map": "TBD",
                    "Victory Conditions": "TBD",
                    "Fog of War": "TBD",
                    "Turn Length": "TBD",
                    "Accelerated Schedule": "TBD",
                    "Deadlines on Weekends": "TBD"
                },
                "Statistics": {
                    "Player Count": "0",
                    "Region Disputes": 0,
                    "Current Turn": "Turn N/A",
                    "Days Ellapsed": 0,
                    "Game Started": "TBD",
                },
                "Inactive Events": [],
                "Active Events": {},
                "Current Event": {}
            }
            core.erase_game(active_game_id)
        active_games = [key for key, value in game_records_dict.items() if value.get("Statistics").get("Game Ended") == "Present"]
        for active_game_name in active_games:
            del game_records_dict[active_game_name]
        with open('active_games.json', 'w') as json_file:
            json.dump(active_games_dict, json_file, indent=4)
        with open('game_records.json', 'w') as json_file:
            json.dump(game_records_dict, json_file, indent=4)
        return redirect(f'/games')

    #check if a game slot is available
    full_game_id = None
    for select_game_id, value in active_games_dict.items():
        if not value.get("Game Active"):
            full_game_id = select_game_id
            break
    if full_game_id != None:
        core.create_new_game(full_game_id, form_data_dict, profile_ids_list)
        return redirect(f'/games')
    else:
        print("Error: No inactive game found to overwrite.")
        quit()

#GAMES ARCHIVE PAGE
@main.route('/archived_games')
def archived_games():
    
    with open('game_records.json', 'r') as json_file:
        game_records_dict = json.load(json_file)
    
    #take information from game_record_dict
    ongoing_list = []
    for game_name, game_data in game_records_dict.items():
        
        if game_data["Statistics"]["Game Ended"] == "Present":
            ongoing_list.append(game_name)
            continue
        
        #get playerdata
        archived_player_data_list, players_who_won_list = generate_refined_player_list_inactive(game_data)
        if len(players_who_won_list) == 1:
            victors_str = players_who_won_list[0]
            game_data["Winner String"] = f'{victors_str} Victory!'
        elif len(players_who_won_list) > 1:
            victors_str = ' & '.join(players_who_won_list)
            game_data["Winner String"] = f'{victors_str} Victory!'
        elif len(players_who_won_list) == 0:
            game_data["Winner String"] = 'Draw!'
        game_data["Playerdata Masterlist"] = archived_player_data_list

        #get game images
        image_name_list = []
        filename = "graphic.png"
        filepath = os.path.join(f"app/static/archive/{game_data["Game ID"]}/", filename)
        if os.path.isfile(filepath):
            image_name_list.append(filename)
        turn_number = game_data["Statistics"]["Turns Ellapsed"]
        if game_data["Statistics"]["Turns Ellapsed"] % 4 != 0:
            filename = f"{turn_number}.png"
            filepath = os.path.join(f"app/static/archive/{game_data["Game ID"]}/", filename)
            if os.path.isfile(filepath):
                image_name_list.append(filename)
            while turn_number % 4 != 0:
                turn_number -= 1
        while turn_number >= 0:
            filename = f"{turn_number}.png"
            filepath = os.path.join(f"app/static/archive/{game_data["Game ID"]}/", filename)
            if os.path.isfile(filepath):
                image_name_list.append(filename)
            turn_number -= 4
        game_data["Slideshow Images"] = image_name_list
    
    #display games from newest to oldest
    game_records_dict = dict(sorted(game_records_dict.items(), key=lambda item: item[1]['Game #'], reverse=True))

    #hide ongoing games
    for game_name in ongoing_list:
        del game_records_dict[game_name]

    #get gameid list (needed for slideshows)
    game_id_list = []
    for game_name, game_data in game_records_dict.items():
        game_id_list.append(game_data["Game ID"])
    game_id_list.reverse()
    slide_index_list = [1] * len(game_id_list)
    
    return render_template('temp_archive.html', dict = game_records_dict, game_id_list = game_id_list, slide_index_list = slide_index_list)

#LEADERBOARD PAGE
@main.route('/leaderboard')
def leaderboard():
    
    leaderboard_data = []
    with open('leaderboard.csv', 'r') as file:
        reader = csv.reader(file)
        for row in reader:
            if row != []:
                leaderboard_data.append(row)
    
    username_list = []
    for profile_id, player_data in player_records_dict.items():
        username_list.append(player_data.get("Username"))
    
    profile_ids = []
    for entry in leaderboard_data:
        username = entry[0]
        profile_id = username_list.index(username)
        profile_id = str(profile_id + 1)
        while len(profile_id) < 3:
            profile_id = f'0{profile_id}'
        profile_ids.append(profile_id)
        entry[0] = f"""<a href="profile/{profile_id}">{entry[0]}</a>"""
    
    with open('leaderboard_records.json', 'r') as json_file:
        leaderboard_records_dict = json.load(json_file)
    
    return render_template('temp_leaderboard_new.html', leaderboard_data = leaderboard_data, profile_ids = profile_ids, leaderboard_records_dict = leaderboard_records_dict)

#GENRATE PROFILE PAGES
def generate_profile_route(profile_id):
    route_name = f'profile_route_{uuid.uuid4().hex}'
    @main.route(f'/profile/{profile_id}', endpoint=route_name)
    def load_profile():
        #read needed files
        with open('game_records.json', 'r') as json_file:
            game_records_dict = json.load(json_file)
        leaderboard_list = []
        with open('leaderboard.csv', 'r') as file:
            reader = csv.reader(file)
            for row in reader:
                leaderboard_list.append(row)
        #get data from player_records.json
        username = player_records_dict[profile_id]["Username"]
        joined = player_records_dict[profile_id]["Join Date"]
        resignations = player_records_dict[profile_id]["Resignations"]
        #get data from game_records.json
        game_starts = []
        game_ends = []
        governments_played = {
            'Republic': 0,
            'Technocracy': 0,
            'Oligarchy': 0,
            'Totalitarian': 0,
            'Remnant': 0,
            'Protectorate': 0,
            'Military Junta': 0,
            'Crime Syndicate': 0,
            'Plutocracy': 0,
            'United States Remnant': 0,
        }
        foreign_policies_played = {
            'Diplomatic': 0,
            'Commercial': 0,
            'Isolationist': 0,
            'Imperialist': 0,
        }
        first_game = ''
        latest_game = ''
        draws = 0
        for game_name, game_data in game_records_dict.items():
            if "Test Game" in game_name:
                continue
            players_who_won = []
            players_who_lost = []
            for select_profile_id, player_data in game_data.get("Player Data", {}).items():
                if player_data.get("Victory") == 0:
                    players_who_lost.append(select_profile_id)
                    if profile_id in players_who_lost and len(players_who_lost) == len(game_records_dict[game_name]["Player Data"]):
                        draws += 1
                else:
                    players_who_won.append(select_profile_id)
            if profile_id in players_who_lost or profile_id in players_who_won:
                game_starts.append(game_data['Statistics']["Game Started"])
                game_ends.append(game_data['Statistics']["Game Ended"])
                government_choice = game_records_dict[game_name]["Player Data"][profile_id]["Government"]
                foreign_policy_choice = game_records_dict[game_name]["Player Data"][profile_id]["Foreign Policy"]
                governments_played[government_choice] += 1
                foreign_policies_played[foreign_policy_choice] += 1
        first_game = game_starts.pop(0)
        latest_game = game_ends.pop(0)
        for date_str in game_starts:
            date_obj_leading = datetime.strptime(first_game, "%m/%d/%Y")
            data_obj_contender = datetime.strptime(date_str, "%m/%d/%Y")
            if data_obj_contender < date_obj_leading:
                first_game = date_str
        for date_str in game_ends:
            date_obj_leading = datetime.strptime(latest_game, "%m/%d/%Y")
            data_obj_contender = datetime.strptime(date_str, "%m/%d/%Y")
            if data_obj_contender > date_obj_leading:
                latest_game = date_str
        favorite_gov_score = max(governments_played.values())
        favorite_govs = [key for key, value in governments_played.items() if value == favorite_gov_score]
        favorite_gov = "/".join(favorite_govs)
        favorite_fp_score = max(foreign_policies_played.values())
        favorite_fps = [key for key, value in foreign_policies_played.items() if value == favorite_fp_score]
        favorite_fp = "/".join(favorite_fps)
        #get data from leaderboard.csv
        for index, entry in enumerate(leaderboard_list):
            if entry[0] == username:
                rank = index + 1
                wins = entry[1]
                score = entry[2]
                average = entry[3]
                games = entry[4]
                break
        losses = int(games) - int(wins) - int(draws)
        reliability = (float(games) - float(resignations)) / float(games)
        reliability = round(reliability, 2)
        reliability = reliability * 100
        reliability = int(reliability)
        reliability = f'{reliability}%'
        return render_template('temp_profile.html', username = username, joined = joined, first_game = first_game, latest_game = latest_game, rank = rank, reliability = reliability, wins = wins, draws = draws, losses = losses, score = score, average = average, games = games, favorite_gov = favorite_gov, favorite_fp = favorite_fp)
with open('player_records.json', 'r') as json_file:
    player_records_dict = json.load(json_file)
profile_id_list = list(player_records_dict.keys())
for profile_id in profile_id_list:
    generate_profile_route(profile_id)


#GAME LOADING
################################################################################

#LOAD GAME PAGE
@main.route(f'/<full_game_id>')
def game_load(full_game_id):
    
    #define additional functions
    def define_victory_conditions(row8, row9):
        vc_set1 = ast.literal_eval(row8)
        vc1a = vc_set1[0]
        vc2a = vc_set1[1]
        vc3a = vc_set1[2]
        vc_set2 = ast.literal_eval(row9)
        vc1b = vc_set2[0]
        vc2b = vc_set2[1]
        vc3b = vc_set2[2]
        return vc1a, vc2a, vc3a, vc1b, vc2b, vc3b
    
    #read the contents of active_games.json
    with open('active_games.json', 'r') as json_file:
        active_games_dict = json.load(json_file)
    game1_title = active_games_dict[full_game_id]["Game Name"]
    game1_turn = active_games_dict[full_game_id]["Statistics"]["Current Turn"]
    game1_active_bool = active_games_dict[full_game_id]["Game Active"]
    game1_extendedtitle = f"Divided We Stand - {game1_title}" 
    
    #load images
    main_url = url_for('main.get_mainmap', full_game_id=full_game_id)
    resource_url = url_for('main.get_resourcemap', full_game_id=full_game_id)
    control_url = url_for('main.get_controlmap', full_game_id=full_game_id)
    #load inactive state
    if not game1_active_bool:
        with open('game_records.json', 'r') as json_file:
            game_records_dict = json.load(json_file)
        game_data = game_records_dict[game1_title]
        largest_nation_tup = checks.get_top_three(full_game_id, 'largest_nation', True)
        strongest_economy_tup = checks.get_top_three(full_game_id, 'strongest_economy', True)
        largest_military_tup = checks.get_top_three(full_game_id, 'largest_military', True)
        most_research_tup = checks.get_top_three(full_game_id, 'most_research', True)
        largest_nation_list = list(largest_nation_tup)
        strongest_economy_list = list(strongest_economy_tup)
        largest_military_list = list(largest_military_tup)
        most_research_list = list(most_research_tup)
        for i in range(len(largest_nation_list)):
            largest_nation_list[i] = color_nation_names(largest_nation_list[i], full_game_id)
            strongest_economy_list[i] = color_nation_names(strongest_economy_list[i], full_game_id)
            largest_military_list[i] = color_nation_names(largest_military_list[i], full_game_id)
            most_research_list[i] = color_nation_names(most_research_list[i], full_game_id)
        archived_player_data_list, players_who_won_list = generate_refined_player_list_inactive(game_data)
        if len(players_who_won_list) == 1:
            victors_str = players_who_won_list[0]
            victory_string = (f"""{victors_str} has won the game.""")
        elif len(players_who_won_list) > 1:
            victors_str = ' and '.join(players_who_won_list)
            victory_string = (f'{victors_str} have won the game.')
        elif len(players_who_won_list) == 0:
            victory_string = (f'Game drawn.')
        victory_string = color_nation_names(victory_string, full_game_id)
        return render_template('temp_stage4.html', game1_title = game1_title, game1_extendedtitle = game1_extendedtitle, main_url = main_url, resource_url = resource_url, control_url = control_url, archived_player_data_list = archived_player_data_list, largest_nation_list = largest_nation_list, strongest_economy_list = strongest_economy_list, largest_military_list = largest_military_list, most_research_list = most_research_list, victory_string = victory_string)
    
    #load active state
    match game1_turn:
        
        case "Starting Region Selection in Progress":
            form_key = "main.stage1_resolution"
            player_data = []
            with open(f'gamedata/{full_game_id}/playerdata.csv', 'r') as file:
                reader = csv.reader(file)
                next(reader,None)
                for index, row in enumerate(reader):
                    if row != []:
                        player_number = row[0]
                        player_color = row[2]
                        player_id = f'p{index + 1}'
                        regioninput_id = f'regioninput_{player_id}'
                        colordropdown_id = f'colordropdown_{player_id}'
                        vc1a, vc2a, vc3a, vc1b, vc2b, vc3b = define_victory_conditions(row[8], row[9])
                        refined_player_data = [player_number, player_id, player_color, vc1a, vc2a, vc3a, vc1b, vc2b, vc3b, regioninput_id, colordropdown_id]
                        player_data.append(refined_player_data)
                active_player_data = player_data.pop(0)
            return render_template('temp_stage1.html', active_player_data = active_player_data, player_data = player_data, game1_title = game1_title, game1_extendedtitle = game1_extendedtitle, main_url = main_url, resource_url = resource_url, control_url = control_url, full_game_id = full_game_id, form_key = form_key)
        
        case "Nation Setup in Progress":
            form_key = "main.stage2_resolution"
            player_data = []
            with open(f'gamedata/{full_game_id}/playerdata.csv', 'r') as file:
                reader = csv.reader(file)
                next(reader,None)
                for index, row in enumerate(reader):
                    if row != []:
                        player_number = row[0]
                        player_color = row[2]
                        player_id = f'p{index + 1}'
                        nameinput_id = f"nameinput_{player_id}"
                        govinput_id = f"govinput_{player_id}"
                        fpinput_id = f"fpinput_{player_id}"
                        vcinput_id = f"vcinput_{player_id}"
                        vc1a, vc2a, vc3a, vc1b, vc2b, vc3b = define_victory_conditions(row[8], row[9])
                        refined_player_data = [player_number, player_id, player_color, vc1a, vc2a, vc3a, vc1b, vc2b, vc3b, nameinput_id, govinput_id, fpinput_id, vcinput_id]
                        player_data.append(refined_player_data)
                active_player_data = player_data.pop(0)
            return render_template('temp_stage2.html', active_player_data = active_player_data, player_data = player_data, game1_title = game1_title, game1_extendedtitle = game1_extendedtitle, main_url = main_url, resource_url = resource_url, control_url = control_url, full_game_id = full_game_id, form_key = form_key)
        
        case _:
            form_key = "main.turn_resolution"
            main_url = url_for('main.get_mainmap', full_game_id=full_game_id)
            player_data = []
            with open(f'gamedata/{full_game_id}/playerdata.csv', 'r') as file:
                reader = csv.reader(file)
                next(reader,None)
                for index, row in enumerate(reader):
                    if row != []:
                        player_number = row[0]
                        nation_name = row[1]
                        player_color = row[2]
                        player_id = f'p{index + 1}' 
                        public_actions_textarea_id = f"public_textarea_{player_id}"
                        private_actions_textarea_id = f"private_textarea_{player_id}"
                        nation_sheet_url = f'{full_game_id}/player{index + 1}'
                        refined_player_data = [player_number, player_id, player_color, nation_name, public_actions_textarea_id, private_actions_textarea_id, nation_sheet_url]
                        player_data.append(refined_player_data)
                active_player_data = player_data.pop(0)
            with open(f'active_games.json', 'r') as json_file:  
                active_games_dict = json.load(json_file)
            current_event_dict = active_games_dict[full_game_id]["Current Event"]
            if current_event_dict != {}:
                form_key = "main.event_resolution"
            return render_template('temp_stage3.html', active_player_data = active_player_data, player_data = player_data, game1_title = game1_title, game1_extendedtitle = game1_extendedtitle, main_url = main_url, resource_url = resource_url, control_url = control_url, full_game_id = full_game_id, form_key = form_key)

#GENERATE NATION SHEET PAGES
def generate_player_route(full_game_id, player_id):
    route_name = f'player_route_{uuid.uuid4().hex}'
    @main.route(f'/{full_game_id}/player{player_id}', endpoint=route_name)
    def player_route():
        page_title = f'Player #{player_id} Nation Sheet'
        game_id = int(full_game_id[-1])
        current_turn_num = core.get_current_turn_num(game_id)
        player_information_dict = core.get_data_for_nation_sheet(full_game_id, player_id, current_turn_num)
        return render_template('temp_nation_sheet.html', page_title=page_title, player_information_dict=player_information_dict)

#GENERATION PROCEDURE
game_ids = ['game1', 'game2']
map_names = ['mainmap', 'resourcemap', 'controlmap']
player_ids = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
for full_game_id in game_ids:
    for player_id in player_ids:
        generate_player_route(full_game_id, player_id)

#WARS PAGE
@main.route('/<full_game_id>/wars')
def wars(full_game_id):

    # define helper functions
    def camel_to_title(camel_str):
        # Insert a space before each uppercase letter and capitalize the words
        title_str = re.sub(r'([A-Z])', r' \1', camel_str).title()
        return title_str.strip()
    
    # read from game files
    from app.wardata import WarData
    with open('active_games.json', 'r') as json_file:
        active_games_dict = json.load(json_file)
    game_name = active_games_dict[full_game_id]["Game Name"]
    page_title = f'{game_name} Wars List'
    current_turn_num = core.get_current_turn_num(int(full_game_id[-1]))
    wardata = WarData(full_game_id)

    # read wars
    for war_name, war_data in wardata.wardata_dict.items():
        
        #get war timeframe
        war_start = war_data["startTurn"]
        season, year = core.date_from_turn_num(war_start)
        war_start = f'{season} {year}'
        war_end = war_data["endTurn"]
        if war_end != 0:
            war_end = int(war_end)
            season, year = core.date_from_turn_num(war_end)
            war_end = f'{season} {year}'
        else:
            war_end = "Present"
        wardata.wardata_dict[war_name]["timeframe"] = f'{war_start} - {war_end}'

        # get war score information
        attacker_war_score = war_data["attackerWarScore"]["total"]
        defender_war_score = war_data["defenderWarScore"]["total"]
        attacker_threshold, defender_threshold = wardata.calculate_score_threshold(war_name)
        ma_name, md_name = wardata.get_main_combatants(war_name)

        # implement a score bar using an html table >:)
        war_status = wardata.wardata_dict[war_name]["outcome"]
        attacker_color = """background-image: linear-gradient(#cc4125, #eb5a3d)"""
        defender_color = """background-image: linear-gradient(#3c78d8, #5793f3)"""
        white_color = """background-image: linear-gradient(#c0c0c0, #b0b0b0)"""
        match war_status:
            case "Attacker Victory":
                # set bar entirely red
                war_status_bar = [attacker_color] * 1
            case "Defender Victory":
                # set bar entirely blue
                war_status_bar = [defender_color] * 1
            case "White Peace":
                # set bar entirely white
                war_status_bar = [white_color] * 1
            case "TBD":
                # color bar based on percentage
                attacker_score = wardata.wardata_dict[war_name]["attackerWarScore"]["total"]
                defender_score = wardata.wardata_dict[war_name]["defenderWarScore"]["total"]
                if attacker_score != 0 and defender_score == 0:
                    war_status_bar = [attacker_color] * 1
                elif attacker_score == 0 and defender_score != 0:
                    war_status_bar = [defender_color] * 1
                elif attacker_score == 0 and defender_score == 0:
                    war_status_bar = [attacker_color] * 1
                    war_status_bar += [defender_color] * 1
                else:
                    # calculate attacker value
                    attacker_percent = float(attacker_score) / float(attacker_score + defender_score)
                    attacker_percent = round(attacker_percent, 2)
                    attacker_points = int(attacker_percent * 100)
                    attacker_steps = round(attacker_points / 5)
                    # calculate defender value
                    defender_percent = float(defender_score) / float(attacker_score + defender_score)
                    defender_percent = round(defender_percent, 2)
                    defender_points = int(defender_percent * 100)
                    defender_steps = round(defender_points / 5)
                    # add to score bar
                    war_status_bar = [attacker_color] * attacker_steps
                    war_status_bar += [defender_color] * defender_steps
        wardata.wardata_dict[war_name]["scoreBar"] = war_status_bar

        # convert warscore keys from camel case to title case with spaces
        copy = {}
        for key, value in wardata.wardata_dict[war_name]["attackerWarScore"].items():
            new_key = camel_to_title(key)
            if new_key == "Total":
                new_key += " War Score"
            elif new_key == "Enemy Improvements Destroyed":
                new_key = "Enemy Impr. Destroyed"
            copy[new_key] = value
        wardata.wardata_dict[war_name]["attackerWarScore"] = copy
        copy = {}
        for key, value in wardata.wardata_dict[war_name]["defenderWarScore"].items():
            new_key = camel_to_title(key)
            if new_key == "Total":
                new_key += " War Score"
            elif new_key == "Enemy Improvements Destroyed":
                new_key = "Enemy Impr. Destroyed"
            copy[new_key] = value
        wardata.wardata_dict[war_name]["defenderWarScore"] = copy

        # create war resolution strings
        match war_status:
            
            case "Attacker Victory":

                war_end_str = """This war concluded with an <span class="color-red">attacker victory</span>."""
                wardata.wardata_dict[war_name]["warEndStr"] = war_end_str
            
            case "Defender Victory":
                
                war_end_str = """This war concluded with a <span class="color-blue">defender victory</span>."""
                wardata.wardata_dict[war_name]["warEndStr"] = war_end_str
            
            case "White Peace":
                
                war_end_str = """This war concluded with a white peace."""
                wardata.wardata_dict[war_name]["warEndStr"] = war_end_str
            
            case "TBD":
            
                if current_turn_num - war_data["startTurn"] < 4:
                    can_end_str = f"A peace deal may be negotiated by the main combatants in {(war_data["startTurn"] + 4) - current_turn_num} turns."
                else:
                    can_end_str = f"A peace deal may be negotiated by the main combatants at any time."
                wardata.wardata_dict[war_name]["canEndStr"] = can_end_str
                
                if attacker_war_score > defender_war_score:
                    if attacker_threshold is not None:
                        forced_end_str = f"""The <span class="color-red"> attackers </span> will win this war upon reaching <span class="color-red"> {attacker_threshold} </span> war score."""
                    else:
                        forced_end_str = f"""The <span class="color-red"> attackers </span> cannot win this war using war score since <span class="color-blue"> {md_name} </span> is a Crime Syndicate."""
                else:
                    if defender_threshold is not None:
                        forced_end_str = f"""The <span class="color-blue"> defenders </span> will win this war upon reaching <span class="color-blue"> {defender_threshold} </span> war score."""
                    else:
                        forced_end_str = f"""The <span class="color-blue"> defenders </span> cannot win this war using war score since <span class="color-red"> {ma_name} </span> is a Crime Syndicate."""
                    
                wardata.wardata_dict[war_name]["forcedEndStr"] = forced_end_str

    return render_template('temp_wars.html', page_title = page_title, dict = wardata.wardata_dict)

#RESEARCH PAGE
@main.route('/<full_game_id>/technologies')
def technologies(full_game_id):
    
    # read the contents of active_games.json
    with open('active_games.json', 'r') as json_file:
        active_games_dict = json.load(json_file)
    game_name = active_games_dict[full_game_id]["Game Name"]
    page_title = f'{game_name} - Technology Trees'
    scenario = active_games_dict[full_game_id]["Information"]["Scenario"]


    # Get Research Information
    refined_dict = {}
    research_data_dict = core.get_scenario_dict(full_game_id, "Technologies")
    
    # get scenario data
    if scenario == "Standard":
        categories = ["Energy", "Infrastructure", "Military", "Defense"]
        for category in categories:
            refined_dict[f'{category} Technologies'] = {}
        refined_dict["Energy Technologies"]["Colors"] = ["#5555554D", "#CC58264D", "#106A254D", "NONE"]
        refined_dict["Infrastructure Technologies"]["Colors"] = ["#F9CB304D", "#754C244D", "#5555554D", "#0583C54D"]
        refined_dict["Military Technologies"]["Colors"] = ["#C419194D", "#5F2F8C4D", "#106A254D", "#CC58264D"]
        refined_dict["Defense Technologies"]["Colors"] = ["#0583C54D", "#F9CB304D", "#C419194D", "NONE"]
        color_complements_dict = {
            "#555555": "#636363",
            "#CC5826": "#E0622B",
            "#106A25": "#197B30",
            "#F9CB30": "#FFDF70",
            "#754C24": "#8C6239",
            "#0583C5": "#1591D1",
            "#5F2F8C": "#713BA4",
            "#C41919": "#D43939"
        }
    
    # create research table
    for category in categories:
        table_contents = {
            "A": [None] * 4,
            "B": [None] * 4,
            "C": [None] * 4,
            "D": [None] * 4,
        }
        refined_dict[f'{category} Technologies']["Table"] = table_contents
    
    # hide fow techs if not fog of war
    if active_games_dict[full_game_id]["Information"]["Fog of War"] == "Disabled":
        del research_data_dict["Surveillance Operations"]
        del research_data_dict["Economic Reports"]
        del research_data_dict["Military Intelligence"]

    # add player research data
    playerdata_filepath = f'gamedata/{full_game_id}/playerdata.csv'
    playerdata_list = core.read_file(playerdata_filepath, 1)
    for research_name in research_data_dict:
        research_data_dict[research_name]["Player Research"] = [None] * len(playerdata_list)
    for index, playerdata in enumerate(playerdata_list):
        player_research_list = ast.literal_eval(playerdata[26])
        for research_name in player_research_list:
            if research_name in research_data_dict:
                research_data_dict[research_name]["Player Research"][index] = (playerdata[2][1:], playerdata[1])

    # load techs to table
    for key, value in research_data_dict.items():
        research_type = value["Research Type"]
        if research_type in categories:
            pos = value["Location"]
            row_pos = pos[0]
            col_pos = int(pos[1])
            value["Name"] = key
            refined_dict[research_type + " Technologies"]["Table"][row_pos][col_pos] = value
    
    return render_template('temp_research.html', page_title = page_title, dict = refined_dict, complement = color_complements_dict)

#AGENDAS PAGE
@main.route('/<full_game_id>/agendas')
def agendas(full_game_id):
    
    # read the contents of active_games.json
    with open('active_games.json', 'r') as json_file:
        active_games_dict = json.load(json_file)
    game_name = active_games_dict[full_game_id]["Game Name"]
    page_title = f'{game_name} - Political Agendas'
    scenario = active_games_dict[full_game_id]["Information"]["Scenario"]


    # Get Research Information
    refined_dict = {}
    agenda_data_dict = core.get_scenario_dict(full_game_id, "Agendas")
    
    # get scenario data
    if scenario == "Standard":
        categories = ["Agendas"]
        for category in categories:
            refined_dict[category] = {}
        refined_dict["Agendas"]["Colors"] = ["#0583C54D", "#106A254D", "#5F2F8C4D", "#C419194D"]
        color_complements_dict = {
            "#555555": "#636363",
            "#CC5826": "#E0622B",
            "#106A25": "#197B30",
            "#F9CB30": "#FFDF70",
            "#754C24": "#8C6239",
            "#0583C5": "#1591D1",
            "#5F2F8C": "#713BA4",
            "#C41919": "#D43939"
        }
    
    # create research table
    for category in categories:
        table_contents = {
            "A": [None] * 4,
            "B": [None] * 4,
            "C": [None] * 4,
            "D": [None] * 4,
        }
        refined_dict[category]["Table"] = table_contents

    # add player research data
    playerdata_filepath = f'gamedata/{full_game_id}/playerdata.csv'
    playerdata_list = core.read_file(playerdata_filepath, 1)
    for research_name in agenda_data_dict:
        agenda_data_dict[research_name]["Player Research"] = [None] * len(playerdata_list)
    for index, playerdata in enumerate(playerdata_list):
        player_research_list = ast.literal_eval(playerdata[26])
        for research_name in player_research_list:
            if research_name in agenda_data_dict:
                agenda_data_dict[research_name]["Player Research"][index] = (playerdata[2][1:], playerdata[1])

    # load techs to table
    for key, value in agenda_data_dict.items():
        pos = value["Location"]
        row_pos = pos[0]
        col_pos = int(pos[1])
        value["Name"] = key
        refined_dict["Agendas"]["Table"][row_pos][col_pos] = value
    
    return render_template('temp_agenda.html', page_title = page_title, dict = refined_dict, complement = color_complements_dict)

# UNITS REF PAGE
@main.route('/<full_game_id>/units')
def units_ref(full_game_id):
    
    # read the contents of active_games.json
    with open('active_games.json', 'r') as json_file:
        active_games_dict = json.load(json_file)
    game_name = active_games_dict[full_game_id]["Game Name"]
    page_title = f'{game_name} - Unit Reference'
    
    # get unit dict
    unit_dict = core.get_scenario_dict(full_game_id, "Units")

    # add reference colors
    for unit_name in unit_dict:
        if "Motorized Infantry" == unit_name:
            unit_dict[unit_name]["stat_color"] = "stat-purple"
            continue
        if "Infantry" in unit_name or "Artillery" in unit_name or "Special Forces" in unit_name:
            unit_dict[unit_name]["stat_color"] = "stat-red"
        elif "Tank" in unit_name:
            unit_dict[unit_name]["stat_color"] = "stat-purple"

    return render_template('temp_units.html', page_title = page_title, dict = unit_dict)

# IMPROVEMENTS REF PAGE
@main.route('/<full_game_id>/improvements')
def improvements_ref(full_game_id):
    
    # read the contents of active_games.json
    with open('active_games.json', 'r') as json_file:
        active_games_dict = json.load(json_file)
    game_name = active_games_dict[full_game_id]["Game Name"]
    page_title = f'{game_name} - Improvement Reference'
    
    # get unit dict
    improvement_dict: dict = core.get_scenario_dict(full_game_id, "Improvements")

    # filter improvements
    improvement_dict_filtered = {}
    for improvement_name, improvement_data in improvement_dict.items():

        # assign color
        # to do - make a function that assigns color based on improvement's required tech
        match improvement_name:
            case 'Boot Camp' | 'Crude Barrier' | 'Military Base' | 'Military Outpost' | 'Missile Defense Network' | 'Missile Defense System' | 'Missile Silo':
                improvement_data["stat_color"] = "stat-red"
            case 'Coal Mine' | 'Nuclear Power Plant' | 'Oil Refinery' | 'Oil Well' | 'Solar Farm' | 'Wind Farm' | 'Strip Mine':
                improvement_data["stat_color"] = "stat-yellow"
            case 'Advanced Metals Mine' | 'Common Metals Mine' | 'Industrial Zone' | 'Uranium Mine' | 'Rare Earth Elements Mine':
                improvement_data["stat_color"] = "stat-grey"
            case 'Capital' | 'Central Bank' | 'City' | 'Research Institute' | 'Research Laboratory':
                improvement_data["stat_color"] = "stat-blue"
            case _:
                improvement_data["stat_color"] = "stat-grey"

        # hide fog of war techs
        if active_games_dict[full_game_id]["Information"]["Fog of War"] != "Enabled" and improvement_data.get("Fog of War Improvement", None):
            continue
        improvement_dict_filtered[improvement_name] = improvement_data

    improvement_dict_filtered = {key: improvement_dict_filtered[key] for key in sorted(improvement_dict_filtered)}
    return render_template('temp_improvements.html', page_title = page_title, dict = improvement_dict_filtered)

# RESOURCE MARKET PAGE
@main.route('/<full_game_id>/resource_market')
def resource_market(full_game_id):

    # read the contents of active_games.json
    with open('active_games.json', 'r') as json_file:
        active_games_dict = json.load(json_file)
    game_name = active_games_dict[full_game_id]["Game Name"]
    page_title = f'{game_name} - Resource Market'

    # get resource market records
    # todo - move contents of rmdata.csv into gamedata.json so we can use a dictionary for this instead of a cringe list of lists
    # todo - make all of this shit code better when I get around to the playerdata rework
    rmdata_filepath = f'gamedata/{full_game_id}/rmdata.csv'
    current_turn_num = core.get_current_turn_num(int(full_game_id[-1]))
    request_list = ['Dollars', 'Technology', 'Coal', 'Oil', 'Basic Materials', 'Common Metals', 'Advanced Metals', 'Uranium', 'Rare Earth Elements']
    total_exchanged = [[0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0]]
    rmdata_recent_transaction_list = core.read_rmdata(rmdata_filepath, current_turn_num, 12, False)
    # check if there are records to display
    if len(rmdata_recent_transaction_list) != 0:
        records_flag = True
        rmdata_recent_transaction_list = rmdata_recent_transaction_list[::-1]
    else:
        records_flag = False
    # add up transactions
    for transaction in rmdata_recent_transaction_list: 
        exchange = transaction[2]
        count = transaction[3]
        resource = transaction[4]
        resource_index = request_list.index(resource) - 1
        if exchange == 'Bought':    
            total_exchanged[resource_index][0] += count
        elif exchange == 'Sold':
            total_exchanged[resource_index][1] += count

    # calculate resource market prices
    # why doesn't this match the sell price calculation exactly? because the sell price calculation is done in the previous turn, this is prices as of the start of current turn
    base_prices = [5.00, 3.00, 3.00, 5.00, 5.00, 10.00, 10.00, 20.00]
    current_prices = [5, 3, 3, 5, 5, 10, 10, 20]
    for i in range(len(base_prices)):
        base_price = base_prices[i]
        bought_last_12 = total_exchanged[i][0]
        sold_last_12 = total_exchanged[i][1]
        next_turn_price = base_price * ( (bought_last_12 + 25) / (sold_last_12 + 25) )
        if "Market Inflation" in active_games_dict[full_game_id]["Active Events"]:
            for resource_name in active_games_dict[full_game_id]["Active Events"]["Market Inflation"]["Affected Resources"]:
                event_resource_index = request_list.index(resource_name) - 1
                if i == event_resource_index:
                    next_turn_price *= 2
        elif "Market Recession" in active_games_dict[full_game_id]["Active Events"]:
            for resource_name in active_games_dict[full_game_id]["Active Events"]["Market Recession"]["Affected Resources"]:
                event_resource_index = request_list.index(resource_name) - 1
                if i == event_resource_index:
                    next_turn_price *= 0.5
        current_price = round(next_turn_price, 2)
        current_prices[i] =  f"{current_price:.2f}"
    
    # format price information into a dictionary
    market_prices_dict = {}
    for index, resource in enumerate(request_list):
        if resource == "Dollars":
            continue
        inner_dict = {}
        inner_dict["Base"] = f"{base_prices[index - 1]:.2f}"
        inner_dict["Bought"] = total_exchanged[index - 1][0]
        inner_dict["Sold"] = total_exchanged[index - 1][1]
        inner_dict["Current"] = current_prices[index - 1]
        market_prices_dict[resource] = inner_dict

    return render_template('temp_resource_market.html', page_title = page_title, records_list = rmdata_recent_transaction_list, records_flag = records_flag, prices_dict = market_prices_dict)

# ANNOUNCEMENT PAGE
@main.route('/<full_game_id>/announcements')
def announcements(full_game_id):

    # get game data
    playerdata_filepath = f'gamedata/{full_game_id}/playerdata.csv'
    trucedata_filepath = f'gamedata/{full_game_id}/trucedata.csv'
    playerdata_list = core.read_file(playerdata_filepath, 1)
    trucedata_list = core.read_file(trucedata_filepath, 1)
    alliance_table = AllianceTable(full_game_id)
    wardata = WarData(full_game_id)
    notifications = Notifications(full_game_id)
    with open('active_games.json', 'r') as json_file:
        active_games_dict = json.load(json_file)

    # read the contents of active_games.json
    game_name = active_games_dict[full_game_id]["Game Name"]
    page_title = f'{game_name} - Announcements Page'
    current_turn_num = int(active_games_dict[full_game_id]["Statistics"]["Current Turn"])
    accelerated_schedule_str = active_games_dict[full_game_id]["Information"]["Accelerated Schedule"]
    current_event_dict = active_games_dict[full_game_id]["Current Event"]
    if current_event_dict != {}:
        event_pending = True
    else:
        event_pending = False

    # get needed data from playerdata.csv
    nation_name_list = []
    for player in playerdata_list:
        nation_name = [player[1]]
        nation_name_list.append(nation_name)
    while len(nation_name_list) < 10:
        nation_name_list.append(['N/A'])

    # calculate date information
    if not event_pending:
        season, year = core.date_from_turn_num(current_turn_num)
        date_output = f'{season} {year} - Turn {current_turn_num}'
    else:
        current_turn_num -= 1
        season, year = core.date_from_turn_num(current_turn_num)
        date_output = f'{season} {year} - Turn {current_turn_num} Bonus Phase'


    # Build Diplomacy String
    diplomacy_list = []
    # expansion rules reminder
    if current_turn_num <= 4:
        diplomacy_list.append('First year expansion rules are in effect.')
    elif current_turn_num == 5:
        diplomacy_list.append('Normal expansion rules are now in effect.')
    # accelerate schedule reminder
    if accelerated_schedule_str == 'Enabled' and current_turn_num <= 10:
        diplomacy_list.append('Accelerated schedule is in effect until turn 11.')
    elif accelerated_schedule_str == 'Enabled' and current_turn_num == 11:
        diplomacy_list.append('Normal turn schedule is now in effect.')
    # get all ongoing wars
    for war in wardata.wardata_dict:
        if wardata.wardata_dict[war]["outcome"] == "TBD":
            diplomacy_list.append(f'{war} is ongoing.')
    # get all ongoing truces
    for truce in trucedata_list:
        truce_participants_list = []
        for i in range(1, 11):
            truce_status = ast.literal_eval(truce[i])
            if truce_status:
                select_nation_name = nation_name_list[i - 1][0]
                truce_participants_list.append(select_nation_name)
        truce_name = ' - '.join(truce_participants_list)
        truce_end_turn = int(truce[11])
        if truce_end_turn >= current_turn_num:
            diplomacy_list.append(f"{truce_name} truce until turn {truce_end_turn}.")
        if truce_end_turn < current_turn_num:
            diplomacy_list.append(f'{truce_name} truce has expired.')
    # get all ongoing alliances
    for alliance in alliance_table:
        if alliance.is_active:
            diplomacy_list.append(f"{alliance.name} is active.")
    # format diplomacy string
    diplomacy_string = "<br>".join(diplomacy_list)
    diplomacy_string = palette.color_nation_names(diplomacy_string, full_game_id)

    
    # Build Notifications String
    notifications_list = []
    q = PriorityQueue()
    for key, value in notifications:
        q.put(key, value)
    while not q.empty():
        ntf = q.get()
        notifications_list.append(ntf)
    notifications_string = "<br>".join(notifications_list)
    notifications_string = palette.color_nation_names(notifications_string, full_game_id)


    # Build Statistics String
    statistics_list = []
    statistics_list.append(f"Total alliances: {len(alliance_table)}")
    longest_alliance_name, longest_alliance_duration = alliance_table.get_longest_alliance()
    if longest_alliance_name is not None:
        statistics_list.append(f"Longest alliance: {longest_alliance_name} - {longest_alliance_duration} turns")
    else:
        statistics_list.append(f"Longest alliance: N/A")
    statistics_list.append(f"Total wars: {wardata.war_count()}")
    statistics_list.append(f"Units lost in war: {wardata.unit_casualties()}")
    statistics_list.append(f"Improvements destroyed in war: {wardata.improvement_casualties()}")
    statistics_list.append(f"Missiles launched: {wardata.missiles_launched_count()}")
    war_name, war_duration = wardata.get_longest_war()
    if war_name is not None:
        statistics_list.append(f"Longest war: {war_name} - {war_duration} turns")
    else:
        statistics_list.append("Longest war: N/A")
    dispute_count = active_games_dict[full_game_id]["Statistics"]["Region Disputes"]
    statistics_list.append(f"Region disputes: {dispute_count}")
    statistics_string = "<br>".join(statistics_list)
    statistics_string = palette.color_nation_names(statistics_string, full_game_id)


    # get top three standings
    standings_dict = {}
    records = ['largest_nation', 'largest_military', 'most_research', 'strongest_economy']
    for record in records:
        standings_dict[record] = list(checks.get_top_three(full_game_id, record, True))
    standings_dict["most_transactions"] = list(core.get_top_three_transactions(full_game_id))
    for record, record_data in standings_dict.items():
        for i in range(len(record_data)):
            standings_dict[record][i] = palette.color_nation_names(record_data[i], full_game_id)
    
    # update scoreboard
    scoreboard_dict = {}
    for index, playerdata in enumerate(playerdata_list):
        player_id = index + 1
        nation_name = playerdata[1]
        player_color_hex = playerdata[2]
        vc_results = checks.check_victory_conditions(full_game_id, player_id, current_turn_num)
        player_vc_score = 0
        for result in vc_results:
            if result == True:
                player_vc_score += 1
        inner_dict = {}
        inner_dict["color"] = player_color_hex
        inner_dict["score"] = player_vc_score
        scoreboard_dict[nation_name] = inner_dict
    
    # sort scoreboard
    scoreboard_dict = dict(
        sorted(
            scoreboard_dict.items(),
            key = lambda item: (-item[1]["score"], item[0])
        )
    )

    return render_template('temp_announcements.html', game_name = game_name, page_title = page_title, date_output = date_output, scoreboard_dict = scoreboard_dict, standings_dict = standings_dict, statistics_string = statistics_string, diplomacy_string = diplomacy_string, notifications_string = notifications_string)

# ALLIANCE PAGE
@main.route('/<full_game_id>/alliances')
def alliances(full_game_id):

    with open('active_games.json', 'r') as json_file:
        active_games_dict = json.load(json_file)
    game_name = active_games_dict[full_game_id]["Game Name"]
    page_title = f'{game_name} - Alliance Page'

    playerdata_filepath = f'gamedata/{full_game_id}/playerdata.csv'
    playerdata_list = core.read_file(playerdata_filepath, 1)
    nation_name_list = []
    nation_colors = []
    for player in playerdata_list:
        nation_name_list.append(player[1])
        nation_colors.append(player[2])

    alliance_table = AllianceTable(full_game_id)
    alliance_dict = alliance_table.data
    misc_data_dict = core.get_scenario_dict(full_game_id, "Misc")
    alliance_type_dict = misc_data_dict["allianceTypes"]

    alliance_dict_filtered = {}
    for alliance_name, alliance_data in alliance_dict.items():
        if alliance_data["turnEnded"] == 0:
            
            # adds alliance establishment string
            turn_started = alliance_data["turnCreated"]
            season, year = core.date_from_turn_num(turn_started)
            date_str = f"{season} {year} (Turn {turn_started})"
            alliance_data["turnCreated"] = date_str

            # add color to nation names
            alliance_data["currentMembersFormatted"] = {}
            for nation_name, turn_joined in alliance_data["currentMembers"].items():
                # can't wait to do the playerdata rework to get rid of this garbage color management code
                index = nation_name_list.index(nation_name)
                bad_primary_colors_set = {"#603913", "#105500", "#8b2a1a"}
                if nation_colors[index] in bad_primary_colors_set:
                    color = palette.normal_to_occupied[nation_colors[index]]
                else:
                    color = nation_colors[index]
                # add to new dict
                alliance_data["currentMembersFormatted"][nation_name] = {}
                alliance_data["currentMembersFormatted"][nation_name]["turnJoined"] = turn_joined
                alliance_data["currentMembersFormatted"][nation_name]["nationColor"] = color
            
            # adds alliance color
            alliance_data["color"] = palette.str_to_hex(alliance_type_dict[alliance_data["allianceType"]]["colorTheme"])

            alliance_dict_filtered[alliance_name] = alliance_data

    return render_template('temp_alliances.html', alliance_dict = alliance_dict_filtered, abilities_dict = alliance_type_dict, page_title = page_title)

#MAP IMAGES
@main.route('/<full_game_id>/mainmap.png')
def get_mainmap(full_game_id):
    with open('active_games.json', 'r') as json_file:
        active_games_dict = json.load(json_file)
    current_turn_num = active_games_dict[full_game_id]["Statistics"]["Current Turn"]
    map_str = map.get_map_str(active_games_dict[full_game_id]["Information"]["Map"])
    try:
        current_turn_num = int(current_turn_num)
        filepath = f'..\\gamedata\\{full_game_id}\\images\\{current_turn_num - 1}.png'
    except:
        if current_turn_num == "Nation Setup in Progress":
            filepath = f'..\\gamedata\\{full_game_id}\\images\\0.png'
        else:
            filepath = f'..\\app\\static\\images\\map_images\\{map_str}\\blank.png'
    return send_file(filepath, mimetype='image/png')
@main.route('/<full_game_id>/resourcemap.png')
def get_resourcemap(full_game_id):
    filepath = f'../gamedata/{full_game_id}/images/resourcemap.png'
    return send_file(filepath, mimetype='image/png')
@main.route('/<full_game_id>/controlmap.png')
def get_controlmap(full_game_id):
    filepath = f'../gamedata/{full_game_id}/images/controlmap.png'
    return send_file(filepath, mimetype='image/png')


#ACTION PROCESSING
################################################################################
@main.route('/stage1_resolution', methods=['POST'])
def stage1_resolution():
    #process form data
    full_game_id = request.form.get('full_game_id')
    starting_region_list  = []
    player_color_list = []
    for i in range(1, 11):
        starting_region_str = request.form.get(f'regioninput_p{i}')
        if starting_region_str:
            starting_region_list.append(starting_region_str)
        player_color_str = request.form.get(f'colordropdown_p{i}')
        if player_color_str:
            player_color_list.append(player_color_str)
    core.resolve_stage1_processing(full_game_id, starting_region_list, player_color_list)
    return redirect(f'/{full_game_id}')

@main.route('/stage2_resolution', methods=['POST'])
def stage2_resolution():
    #process form data
    full_game_id = request.form.get('full_game_id')
    player_nation_name_list = []
    player_government_list = []
    player_foreign_policy_list = []
    player_victory_condition_set_list = []
    for i in range(1, 11):
        player_nation_name = request.form.get(f'nameinput_p{i}')
        if player_nation_name:
            player_nation_name_list.append(player_nation_name)
        player_government = request.form.get(f'govinput_p{i}')
        if player_government:
            player_government_list.append(player_government)
        player_foreign_policy = request.form.get(f'fpinput_p{i}')
        if player_foreign_policy:
            player_foreign_policy_list.append(player_foreign_policy)
        player_vc_set = request.form.get(f'vcinput_p{i}')
        if player_vc_set:
            player_victory_condition_set_list.append(player_vc_set)
    core.resolve_stage2_processing(full_game_id, player_nation_name_list, player_government_list, player_foreign_policy_list, player_victory_condition_set_list)
    return redirect(f'/{full_game_id}')

@main.route('/turn_resolution', methods=['POST'])
def turn_resolution():
    #process form data
    full_game_id = request.form.get('full_game_id')
    public_actions_list = []
    private_actions_list = []
    for i in range(1, 11):
        public_str = request.form.get('public_textarea_p' + str(i))
        if public_str:
            #if this player submitted public actions, convert actions into a list
            player_public_list = public_str.split('\r\n')
            public_actions_list.append(player_public_list)
        else:
            public_actions_list.append([])
        private_str = request.form.get('private_textarea_p' + str(i))
        if private_str:
            #if this player submitted private actions, convert actions into a list
            player_private_list = private_str.split('\r\n')
            private_actions_list.append(player_private_list)
        else:
            private_actions_list.append([])
    core.resolve_turn_processing(full_game_id, public_actions_list, private_actions_list)
    return redirect(f'/{full_game_id}')

@main.route('/event_resolution', methods=['POST'])
def event_resolution():
    '''
    Handles current event and runs end of turn checks & updates when activated.
    Redirects back to selected game.
    '''
    
    full_game_id = request.form.get('full_game_id')
    game_id = int(full_game_id[-1])
    playerdata_filepath = f'gamedata/{full_game_id}/playerdata.csv'
    playerdata_list = core.read_file(playerdata_filepath, 1)
    with open(f'active_games.json', 'r') as json_file:  
        active_games_dict = json.load(json_file)
    
    current_turn_num = core.get_current_turn_num(game_id)
    player_count = len(playerdata_list)
    
    events.handle_current_event(active_games_dict, full_game_id)
    core.run_end_of_turn_checks(full_game_id, current_turn_num, player_count)

    return redirect(f'/{full_game_id}')

#map_tests.run()