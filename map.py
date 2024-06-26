#STANDARD IMPORTS
import ast
import csv
from datetime import datetime
import json
import os
import random
import shutil

#UWS ENVIROMENT IMPORTS
from PIL import Image, ImageDraw

#UWS SOURCE IMPORTS
import core

#MAP CLASSES
class MainMap:
    
    '''Creates and updates the main map for United We Stood games.'''

    #INITIALIZE
    def __init__(self, game_id, map_name, current_turn_num):
        self.game_id = game_id
        self.map_name = map_name
        self.turn_num = current_turn_num


    #PLACE RANDOM IMPROVEMENTS
    def place_random(self):
        
        #get filepaths and lists
        regdata_location = f'gamedata/game{self.game_id}/regdata.csv'
        regdata_list = core.read_file(regdata_location, 2)
        improvement_exclusion_list = ['Capital', 'Missile Defense System', 'Missile Defense Network', 'Oil Refinery', 'Advanced Metals Refinery', 'Uranium Refinery', 'Nuclear Power Plant', 'Surveillance Center']
        improvement_candidates_list = []
        for improvement_name in core.improvement_data_dict:
            if core.improvement_data_dict[improvement_name]['Required Resource'] == None and improvement_name not in improvement_exclusion_list:
                improvement_candidates_list.append(improvement_name)
        
        #update regdata.csv
        count = 0
        placement_quota = 5
        placement_odds = 5
        while count < placement_quota:
            for region in regdata_list:
                placement_roll = random.randint(1, 100)
                if placement_roll <= placement_odds:
                    control_data = ast.literal_eval(region[2])
                    resource_name = region[3]
                    improvement_data = ast.literal_eval(region[4])
                    contains_regional_capital = ast.literal_eval(region[10])
                    if control_data[0] == 0 and improvement_data == [None, 99]:
                        match resource_name:
                            case 'Coal':
                                region[4] = ['Coal Mine', 99]
                            case 'Oil':
                                region[4] = ['Oil Well', 99]
                            case 'Basic Materials':
                                region[4] = ['Industrial Zone', 99]
                            case 'Common Metals':
                                region[4] = ['Common Metals Mine', 99]
                            case 'Advanced Metals':
                                region[4] = ['Advanced Metals Mine', 99]
                            case 'Uranium':
                                region[4] = ['Uranium Mine', 99]
                            case 'Rare Earth Elements':
                                region[4] = ['Rare Earth Elements Mine', 99]
                            case _:
                                if contains_regional_capital:
                                    improvement_candidates_list.append('Capital')
                                improvement_roll = random.randint(0, len(improvement_candidates_list) - 1)
                                improvement_name = improvement_candidates_list[improvement_roll]
                                if core.improvement_data_dict[improvement_name]['Health'] != 99:
                                    region[4] = [improvement_name, 1]
                                else:
                                    region[4] = [improvement_name, 99]
                                if contains_regional_capital:
                                    improvement_candidates_list.remove('Capital')
                        count += 1
                                
        #save regdata.csv
        with open(regdata_location, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(core.regdata_header_a)
            writer.writerow(core.regdata_header_b)
            writer.writerows(regdata_list)
    
    
    #UPDATE
    def update(self):
        print("Updating main map...")
        
        #Get Filepaths
        full_game_id = f'game{self.game_id}'
        match self.turn_num:
            case "Starting Region Selection in Progress" | "Nation Setup in Progress":
                main_map_save_location = f'gamedata/{full_game_id}/images/mainmap.png'
            case _:
                main_map_save_location = f'gamedata/{full_game_id}/images/{self.turn_num - 1}.png'
        regdata_location = f'gamedata/{full_game_id}/regdata.csv'
        playerdata_location = f'gamedata/{full_game_id}/playerdata.csv'
        temp_save_location = f'gamedata/game{self.game_id}/images/temp.png'
        temp2_save_location = f'gamedata/game{self.game_id}/images/temp2.png'
        temp3_save_location = f'gamedata/game{self.game_id}/images/temp3.png'
        temp4_save_location = f'gamedata/game{self.game_id}/images/temp4.png'
        temp5_save_location = f'gamedata/game{self.game_id}/images/temp5.png'
        background_file, magnified_file, main_file, text_file, texture_file = get_map_filepaths(self.map_name)
        
        #Build Needed Lists
        playerdata_list = core.read_file(playerdata_location, 1)
        nation_info_masterlist = core.get_nation_info(playerdata_list)
        regdata_list = core.read_file(regdata_location, 2)
        player_color_list = generate_player_color_list(playerdata_location)

        #Get Cordinate Dictionaries
        match self.map_name:
            case "United States 2.0":
                cords_filepath = "maps/united_states"
            case _ :
                cords_filepath = "maps/united_states"
        with open(f'{cords_filepath}/improvement_cords.json', 'r') as json_file:
            improvement_cords_dict = json.load(json_file)
        with open(f'{cords_filepath}/unit_cords.json', 'r') as json_file:
            unit_cords_dict = json.load(json_file)
        
        #Color Regions in Map Image
        main_image = Image.open(main_file)
        for region in regdata_list:
            region_id = region[0]
            control_data_list = ast.literal_eval(region[2])
            owner_id = control_data_list[0]
            occupier_id = control_data_list[1]
            start_cords = improvement_cords_dict[region_id]
            if start_cords != () and owner_id != 0:
                cord_x = (start_cords[0] + 25)
                cord_y = (start_cords[1] + 25)
                start_cords_updated = (cord_x, cord_y)
                start_cords_finalized = check_region_fill_exceptions(region_id, self.map_name, start_cords_updated)
                map_color_fill(owner_id, occupier_id, player_color_list, region_id, main_image, start_cords_finalized)
        main_image.save(temp_save_location)
        #add texture and background to temp image
        apply_textures(texture_file, background_file, temp_save_location, temp2_save_location, temp3_save_location)
        #add magnified regions
        magnified_image = Image.open(magnified_file)
        temp3_image = Image.open(temp3_save_location)
        mask = magnified_image.split()[3]
        temp3_image.paste(magnified_image, (0,0), mask)
        temp3_image.save(temp4_save_location)
        #color magnified regions
        temp4_image = Image.open(temp4_save_location)
        for region in regdata_list:
            region_id = region[0]
            control_data_list = ast.literal_eval(region[2])
            owner_id = control_data_list[0]
            occupier_id = control_data_list[1]
            improvement_start_cords = improvement_cords_dict[region_id]
            if self.map_name == "United States 2.0":
                magnified_regions_list = ["LOSAN", "FIRCT", "TAMPA", "GACST", "HAMPT", "EASMD", "DELEW", "RHODE", "NTHMA", "STHMA"]
            if improvement_start_cords != () and owner_id != 0 and region_id in magnified_regions_list:
                fill_color = player_color_list[owner_id -1]
                if occupier_id != 0:
                    fill_color = core.player_colors_normal_to_occupied[fill_color]
                cord_x = (improvement_start_cords[0] + 25)
                cord_y = (improvement_start_cords[1] + 25)
                improvement_box_start_cords = (cord_x, cord_y)
                cord_x = (improvement_start_cords[0] + 55)
                cord_y = (improvement_start_cords[1] + 25)
                main_box_start_cords = (cord_x, cord_y)
                cord_x = (improvement_start_cords[0] + 70)
                cord_y = (improvement_start_cords[1] + 25)
                unit_box_start_cords = (cord_x, cord_y)
                ImageDraw.floodfill(temp4_image, improvement_box_start_cords, fill_color, border=(0, 0, 0, 255))
                ImageDraw.floodfill(temp4_image, main_box_start_cords, fill_color, border=(0, 0, 0, 255))
                ImageDraw.floodfill(temp4_image, unit_box_start_cords, fill_color, border=(0, 0, 0, 255))
        temp4_image.save(temp5_save_location)
        
        #Place Improvements
        temp5_image = Image.open(temp5_save_location)
        nuke_image = Image.open('static/nuke.png')
        for region in regdata_list:
            region_id = region[0]
            improvement_data_list = ast.literal_eval(region[4])
            improvement_name = improvement_data_list[0]
            improvement_health = improvement_data_list[1]
            nuke_data = ast.literal_eval(region[6])
            nuke = nuke_data[0]
            improvement_start_cords = improvement_cords_dict[region_id]
            #place nuclear explosion
            if nuke:
                mask = nuke_image.split()[3]
                temp5_image.paste(nuke_image, improvement_start_cords, mask)
                continue
            if improvement_start_cords != () and improvement_name is not None:
                #place improvement image
                if improvement_name != "Embassy":
                    improvement_filepath = f'static/improvements/{improvement_name}.png'
                else:
                    partner_player_id = improvement_data_list[2]
                    if partner_player_id != 0:
                        embassy_color_str = nation_info_masterlist[partner_player_id - 1][1]
                        improvement_filepath = f'static/improvements/{improvement_name}{embassy_color_str}.png'
                    else:
                        improvement_filepath = f'static/improvements/{improvement_name}.png'
                improvement_image = Image.open(improvement_filepath)
                temp5_image.paste(improvement_image, improvement_start_cords)
                #place improvement health
                if improvement_health != 99:
                    cord_x = (improvement_start_cords[0] - 13)
                    cord_y = (improvement_start_cords[1] + 54)
                    health_start_cords = (cord_x, cord_y)
                    if improvement_name in core.ten_health_improvements_list:
                        health_filepath = f'static/health/{improvement_health}-10.png'
                    else:
                        health_filepath = f'static/health/{improvement_health}-5.png'
                    health_image = Image.open(health_filepath)
                    temp5_image.paste(health_image, health_start_cords)
        
        #Place Units
        temp5_image = temp5_image.convert("RGBA")
        for region in regdata_list:
            region_id = region[0]
            unit_data_list = ast.literal_eval(region[5])
            unit_abbr = unit_data_list[0]
            unit_name = next((unit for unit, data in core.unit_data_dict.items() if data.get('Abbreviation') == unit_abbr), None)
            if unit_name is not None:
                unit_health = unit_data_list[1]
                unit_owner_id = unit_data_list[2]
                #get cords
                if region_id not in unit_cords_dict:
                    #unit placement is the standard 15 pixels to the right of improvement
                    improvement_cords = improvement_cords_dict[region_id]
                    cord_x = (improvement_cords[0] + 65)
                    cord_y = (improvement_cords[1])
                    unit_cords = (cord_x, cord_y)
                else:
                    #unit placement is custom
                    unit_cords = unit_cords_dict[region_id]
                    cord_x = (unit_cords[0])
                    cord_y = (unit_cords[1] - 20)
                    unit_cords = (cord_x, cord_y)
                #get unit color
                player_color_str = nation_info_masterlist[unit_owner_id - 1][1]
                unit_filepath = f'static/units/{unit_abbr}{player_color_str}.png'
                #place unit
                unit_image = Image.open(unit_filepath)
                mask = unit_image.split()[3]
                temp5_image.paste(unit_image, unit_cords, mask)
                #place unit health
                health_filepath = f"static/health/U{unit_health}-{core.unit_data_dict[unit_name]['Health']}.png"
                health_image = Image.open(health_filepath)
                mask = health_image.split()[3]
                temp5_image.paste(health_image, unit_cords, mask)
        temp5_image.save(main_map_save_location)
        
        #Delete Temp Files
        os.remove(temp_save_location)
        os.remove(temp2_save_location)
        os.remove(temp3_save_location)
        os.remove(temp4_save_location)
        os.remove(temp5_save_location)

class ResourceMap:
    
    '''Creates and updates the resource map for United We Stood games.'''

    #RESOURCE LISTS
    united_states_resource_list = ["Coal","Coal","Coal","Coal","Coal","Coal","Coal","Coal","Coal","Coal","Coal","Coal","Coal","Coal","Coal","Coal","Coal","Coal","Oil","Oil","Oil","Oil","Oil","Oil","Oil","Oil","Oil","Oil","Oil","Oil","Oil","Oil","Oil","Oil","Oil","Oil","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Basic Materials","Common Metals","Common Metals","Common Metals","Common Metals","Common Metals","Common Metals","Common Metals","Common Metals","Common Metals","Common Metals","Common Metals","Common Metals","Common Metals","Common Metals","Common Metals","Common Metals","Common Metals","Common Metals","Common Metals","Common Metals","Common Metals","Common Metals","Common Metals","Common Metals","Common Metals","Common Metals","Common Metals","Common Metals","Common Metals","Common Metals","Advanced Metals","Advanced Metals","Advanced Metals","Advanced Metals","Advanced Metals","Advanced Metals","Advanced Metals","Advanced Metals","Advanced Metals","Advanced Metals","Uranium","Uranium","Uranium","Uranium","Uranium","Uranium","Uranium","Uranium","Uranium","Uranium","Rare Earth Elements","Rare Earth Elements","Rare Earth Elements","Rare Earth Elements","Rare Earth Elements","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty","Empty"]

    #INITIALIZE
    def __init__(self, game_id, map_name):
        self.game_id = game_id
        self.map_name = map_name

    #CREATE RESOURCE MAP DATA
    def create(self):
        #Identify needed resource list and shuffle it
        if self.map_name == "United States 2.0":
            resource_list = random.sample(self.united_states_resource_list, len(self.united_states_resource_list))
        #Update regdata.csv
        regdata_location = f'gamedata/game{self.game_id}/regdata.csv'
        regdata_list = core.read_file(regdata_location, 0)
        resource_list.insert(0, "Resource Name")
        resource_list.insert(0, "Resource Data")
        for i, region in enumerate(regdata_list):
            region[3] = resource_list[i]
        #Save regdata.csv
        with open(regdata_location, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerows(regdata_list)

    #UPDATE
    def update(self):
        print("Updating resource map...")

        #Get Filepaths
        full_game_id = f'game{self.game_id}'
        resource_map_save_location = f'gamedata/{full_game_id}/images/resourcemap.png'
        regdata_location = f'gamedata/{full_game_id}/regdata.csv'
        playerdata_location = f'gamedata/{full_game_id}/playerdata.csv'
        temp_save_location = f'gamedata/game{self.game_id}/images/temp.png'
        temp2_save_location = f'gamedata/game{self.game_id}/images/temp2.png'
        background_file, magnified_file, main_file, text_file, texture_file = get_map_filepaths(self.map_name)
        
        #Build Needed Lists
        regdata_list = core.read_file(regdata_location, 2)
        
        #Get Cordinate Dictionaries
        match self.map_name:
            case "United States 2.0":
                cords_filepath = "maps/united_states"
            case _ :
                cords_filepath = "maps/united_states"
        with open(f'{cords_filepath}/improvement_cords.json', 'r') as json_file:
            improvement_cords_dict = json.load(json_file)
        
        #Color Regions in Map Image
        main_image = Image.open(main_file)
        for region in regdata_list:
            region_id = region[0]
            resource_type = region[3]
            start_cords = improvement_cords_dict[region_id]
            if start_cords != () and resource_type != 'Empty':
                cord_x = (start_cords[0] + 25)
                cord_y = (start_cords[1] + 25)
                start_cords_updated = (cord_x, cord_y)
                start_cords_finalized = check_region_fill_exceptions(region_id, self.map_name, start_cords_updated)
                if region_id == "HAMPT" and self.map_name == "United States 2.0":
                    ImageDraw.floodfill(main_image, (4430, 1520), core.resource_colors[resource_type], border=(0, 0, 0, 255))
                ImageDraw.floodfill(main_image, start_cords_finalized, core.resource_colors[resource_type], border=(0, 0, 0, 255))
        main_image.save(temp_save_location)
        
        #Put Images Together
        background_image = Image.open(background_file)
        temp_image = Image.open(temp_save_location)
        mask = temp_image.split()[3]
        background_image.paste(temp_image, (0,0), mask)
        background_image.save(temp2_save_location)
        #add text
        text_over_map(temp2_save_location, text_file, resource_map_save_location)
        
        #Delete Temp Files
        os.remove(temp_save_location)
        os.remove(temp2_save_location)

class ControlMap:

    '''Creates and updates the control map for United We Stood games.'''

    #INITIALIZE
    def __init__(self, game_id, map_name):
        self.game_id = game_id
        self.map_name = map_name

    #GENERATE CONTROL MAP IMAGE
    def update(self):
        print("Updating control map...")
        
        #Get Filepaths
        full_game_id = f'game{self.game_id}'
        control_map_save_location = f'gamedata/{full_game_id}/images/controlmap.png'
        regdata_location = f'gamedata/{full_game_id}/regdata.csv'
        playerdata_location = f'gamedata/{full_game_id}/playerdata.csv'
        temp_save_location = f'gamedata/game{self.game_id}/images/temp.png'
        temp2_save_location = f'gamedata/game{self.game_id}/images/temp2.png'
        temp3_save_location = f'gamedata/game{self.game_id}/images/temp3.png'
        background_file, magnified_file, main_file, text_file, texture_file = get_map_filepaths(self.map_name)
       
        #Build Needed Lists
        regdata_list = core.read_file(regdata_location, 2)
        player_color_list = generate_player_color_list(playerdata_location)

        #Get Cordinate Dictionaries
        match self.map_name:
            case "United States 2.0":
                cords_filepath = "maps/united_states"
            case _ :
                cords_filepath = "maps/united_states"
        with open(f'{cords_filepath}/improvement_cords.json', 'r') as json_file:
            improvement_cords_dict = json.load(json_file)

        #Color Regions in Map Image
        main_image = Image.open(main_file)
        for region in regdata_list:
            region_id = region[0]
            control_data_list = ast.literal_eval(region[2])
            owner_id = control_data_list[0]
            occupier_id = control_data_list[1]
            start_cords = improvement_cords_dict[region_id]
            if start_cords != () and owner_id != 0:
                cord_x = (start_cords[0] + 25)
                cord_y = (start_cords[1] + 25)
                start_cords_updated = (cord_x, cord_y)
                start_cords_finalized = check_region_fill_exceptions(region_id, self.map_name, start_cords_updated)
                map_color_fill(owner_id, occupier_id, player_color_list, region_id, main_image, start_cords_finalized)
        main_image.save(temp_save_location)
        #put images together
        apply_textures(texture_file, background_file, temp_save_location, temp2_save_location, temp3_save_location)
        #add text
        text_over_map(temp3_save_location, text_file, control_map_save_location)
        
        #Delete Temp Files
        os.remove(temp_save_location)
        os.remove(temp2_save_location)
        os.remove(temp3_save_location)
        print("Map updates complete!")

#FILEPATH GATHERING FUNCTIONS
def get_map_filepaths(map_name):
    '''Returns a series of variables representing the filepaths of the map generation image based on the map type.'''
    if map_name == "United States 2.0":
        background_file = 'maps/united_states/image_resources/background.png'
        magnified_file = 'maps/united_states/image_resources/magnified.png'
        main_file = 'maps/united_states/image_resources/main.png'
        text_file = 'maps/united_states/image_resources/text.png'
        texture_file = 'maps/united_states/image_resources/texture.png'
    return background_file, magnified_file, main_file, text_file, texture_file

#MAP GENERATION FUNCTIONS
def generate_player_color_list(playerdata_location):
    player_color_list = []
    with open(playerdata_location, 'r') as file:
        reader = csv.reader(file)
        next(reader,None)
        for row in reader:
            if row != []:
                player_color_hex = row[2]
                player_color_rgb = core.player_colors_conversions[player_color_hex]
                player_color_list.append(player_color_rgb)
    return player_color_list

def check_region_fill_exceptions(region_id, map_name, start_cords_updated):
    '''Changes start_cords_updated for maginified regions.'''
    if map_name == "United States 2.0":
        if region_id == "LOSAN":
            start_cords_updated = (563, 1866)
        elif region_id == "FIRCT":
            start_cords_updated = (4040, 2489)
        elif region_id == "TAMPA":
            start_cords_updated = (3997, 2697)
        elif region_id == "GACST":
            start_cords_updated = (4014, 2297)
        elif region_id == "HAMPT":
            start_cords_updated = (4358, 1590)
        elif region_id == "EASMD":
            start_cords_updated = (4413, 1447)
        elif region_id == "DELEW":
            start_cords_updated = (4410, 1379)
        elif region_id == "RHODE":
            start_cords_updated = (4676, 995)
        elif region_id == "NTHMA":
            start_cords_updated = (4660, 923)
        elif region_id == "STHMA":
            start_cords_updated = (4700, 960)
    return start_cords_updated

def map_color_fill(owner_id, occupier_id, player_color_list, region_id, main_image, start_cords_updated):
    '''Determines what fill color to use for main map and control map generation, depending on region ownership and occupation.'''
    fill_color = player_color_list[owner_id -1]
    if occupier_id != 0:
        #use an occupation player color because region is occupied
        fill_color = player_color_list[occupier_id -1]
        fill_color = core.player_colors_normal_to_occupied[fill_color]
    if region_id == "HAMPT":
        ImageDraw.floodfill(main_image, (4430, 1520), fill_color, border=(0, 0, 0, 255))
    ImageDraw.floodfill(main_image, start_cords_updated, fill_color, border=(0, 0, 0, 255))

def apply_textures(texture_file, background_file, temp_save_location, temp2_save_location, temp3_save_location):
    '''Applies the texture and background images to the temp image file.'''
    texture_image = Image.open(texture_file)
    temp_image = Image.open(temp_save_location)
    temp2_image = Image.blend(texture_image, temp_image, 0.75)
    temp2_image.save(temp2_save_location)
    background_image = Image.open(background_file)
    temp2_image = Image.open(temp2_save_location)
    mask = temp2_image.split()[3]
    background_image.paste(temp2_image, (0,0), mask)
    background_image.save(temp3_save_location)

def text_over_map(temp_map, text_file, map_save_location):
    '''Adds text over given temp map image and saves it.'''
    temp_image = Image.open(temp_map)
    text_image = Image.open(text_file)
    mask = text_image.split()[3]
    temp_image.paste(text_image, (0,0), mask)
    temp_image.save(map_save_location)

def update_preview_image(game_id, current_turn_num):
    match current_turn_num:
        case "Starting Region Selection in Progress" | "Nation Setup in Progress":
            filename = 'mainmap.png'
        case _:
            filename = f'{current_turn_num - 1}.png'
    mainmap_file = f'gamedata/game{game_id}/images/{filename}'
    filepath_new = f'static/game{game_id}_image.png'
    preview_destination = 'static'
    shutil.copy(mainmap_file, preview_destination)
    filepath_old = f'static/{filename}'
    shutil.move(filepath_old, filepath_new)
