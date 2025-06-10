import json
from collections import defaultdict

from app import core
from app.nationdata import Nation
from app.nationdata import NationTable
from app.alliance import AllianceTable
from app.war import WarTable


# easy

def ambassador(nation: Nation) -> bool:

    # load game data
    GAME_ID = nation.game_id
    alliance_table = AllianceTable(GAME_ID)
    
    # count alliances
    alliances_found = defaultdict(int)
    for alliance in alliance_table:
        if nation.name in alliance.founding_members and alliance.type != "Non-Aggression Pact":
            alliances_found[alliance.type] += 1
    
    # if at least 3 of same type vc fullfilled
    for count in alliances_found.values():
        if count >= 3:
            return True
        
    return False

def backstab(nation: Nation) -> bool:

    # load game data
    GAME_ID = nation.game_id
    nation_table = NationTable(GAME_ID)
    alliance_table = AllianceTable(GAME_ID)
    war_table = WarTable(GAME_ID)

    # get set of all nations defeated in war
    nations_defeated = set()
    for war in war_table:
        if war.outcome == "TBD" or nation.name not in war.combatants:
            # we do not care about wars player was not involved in
            continue
        if "Attacker" in war.get_role(nation.id):
            nation_side = "Attacker"
        else:
            nation_side = "Defender"
        if nation_side not in war.outcome:
            # we do not care about wars the player lost or white peaced
            continue
        for combatant_id in war.combatants:
            if nation_side not in war.get_role(combatant_id):
                nations_defeated.add(combatant_id)
    
    # get set of all nations you lost a war to
    nations_lost_to = set()
    for war in war_table:
        if war.outcome == "TBD" or nation.name not in war.combatants:
            # we do not care about wars player was not involved in
            continue
        if "Attacker" in war.get_role(nation.id):
            nation_side = "Attacker"
        else:
            nation_side = "Defender"
        if nation_side in war.outcome or "White Peace" == war.outcome:
            # we do not care about wars the player won or white peaced
            continue
        for combatant_id in war.combatants:
            if nation_side not in war.get_role(combatant_id):
                nations_lost_to.add(combatant_id)
    
    # get set of all former allies
    current_allies = set()
    former_allies = set()
    for alliance in alliance_table:
        if alliance.is_active and nation.name in alliance.current_members:
            for ally_name in alliance.current_members:
                current_allies.add(ally_name)
            for ally_name in alliance.former_members:
                former_allies.add(ally_name)
        elif not alliance.is_active and nation.name in alliance.former_members:
            for ally_name in alliance.former_members:
                former_allies.add(ally_name)
    if nation.name in current_allies:
        current_allies.remove(nation.name)
    if nation.name in former_allies:
        former_allies.remove(nation.name)
    former_allies_filtered = set()
    for ally_name in former_allies:
        if ally_name not in current_allies:
            former_allies_filtered.add(ally_name)
    former_allies = former_allies_filtered
    
    # win a war against a former ally
    for former_ally in former_allies:
        temp = nation_table.get(former_ally)
        if temp.id in nations_defeated:
            return True
    
    # win a war against someone you lost to
    for enemy_id in nations_lost_to:
        if enemy_id in nations_defeated:
            return True
    
    return False

def breakthrough(nation: Nation) -> bool:

    # load game data
    GAME_ID = nation.game_id
    nation_table = NationTable(GAME_ID)
    tech_data_dict = core.get_scenario_dict(GAME_ID, "Technologies")

    # build set of all techs other players have researched so we can compare
    completed_research_all = set()
    for temp in nation_table:
        if temp.name != nation.name:
            temp_research_list = list(temp.completed_research.keys())
            completed_research_all.update(temp_research_list)
    
    # find 20 point or greater tech that is not in completed_research_all
    for tech_name in nation.completed_research:
        if (tech_name in tech_data_dict
            and tech_name not in completed_research_all
            and tech_data_dict[tech_name]["Cost"] >= 20):
            return True

    return False

def diverse_economy(nation: Nation) -> bool:

    non_zero_count = 0
    for improvement_name, improvement_count in nation.improvement_counts.items():
        if improvement_count > 0:
            non_zero_count += 1
    
    if non_zero_count >= 16:
        return True

    return False

def double_down(nation: Nation) -> bool:

    # load game data
    GAME_ID = nation.game_id
    war_table = WarTable(GAME_ID)

    # count wars
    wars_found = defaultdict(int)
    for war in war_table:
        
        if nation.id not in war.combatants:
            continue
        
        if war.outcome == "Attacker Victory" and "Attacker" in war.get_combatant(nation.id).role:
            for temp_id in war.combatants:
                if temp_id != nation.id and not war.is_on_same_side(nation.id, temp_id):
                    wars_found[temp_id] += 1
                    
        elif war.outcome == "Defender Victory" and "Defender" in war.get_combatant(nation.id).role:
            for temp_id in war.combatants:
                if temp_id != nation.id and not war.is_on_same_side(nation.id, temp_id):
                    wars_found[temp_id] += 1

    # check
    for count in wars_found.values():
        if count >= 2:
            return True

    return False

def new_empire(nation: Nation) -> bool:

    if nation.improvement_counts["Capital"] >= 2:
        return True

    return False

def reconstruction_effort(nation: Nation) -> bool:

    # load game data
    GAME_ID = nation.game_id
    nation_table = NationTable(GAME_ID)

    # get score improvement count list
    sum_dict = {}
    for temp in nation_table:
        sum_dict[temp.name] = 0
        sum_dict[temp.name] += temp.improvement_counts["Settlement"]
        sum_dict[temp.name] += temp.improvement_counts["City"] * 3
        sum_dict[temp.name] += temp.improvement_counts["Capital"] * 10
    
    # check if nation has the greatest sum
    nation_name_sum = sum_dict[nation.name]
    for temp_nation_name, sum in sum_dict.items():
        if temp_nation_name != nation.name and sum >= nation_name_sum:
            return False

    return True

def reliable_ally(nation: Nation) -> bool:

    # load game data
    GAME_ID = nation.game_id
    alliance_table = AllianceTable(GAME_ID)

    longest_alliance_name, duration = alliance_table.get_longest_alliance()
    if longest_alliance_name is not None:
        longest_alliance = alliance_table.get(longest_alliance_name)
        if nation.name in longest_alliance.founding_members:
            return True
        
    return False

def secure_strategic_resources(nation: Nation) -> bool:

    if (nation.improvement_counts["Advanced Metals Mine"] > 0
        and nation.improvement_counts["Uranium Mine"] > 0
        and nation.improvement_counts["Rare Earth Elements Mine"] > 0):
        return True

    return False

def threat_containment(nation: Nation) -> bool:

    # load game data
    GAME_ID = nation.game_id
    war_table = WarTable(GAME_ID)

    # check if war won with specific war justification
    for war in war_table:

        if nation.id not in war.combatants:
            continue

        combatant =  war.get_combatant(nation.id)
        if war.outcome == "Attacker Victory" and "Attacker" in combatant.role and combatant.justification == "Containment":
            return True
        elif war.outcome == "Defender Victory" and "Defender" in combatant.role and combatant.justification == "Containment":
            return True

    return False

# medium

def energy_focus(nation: Nation) -> bool:

    # load game data
    GAME_ID = nation.game_id
    nation_table = NationTable(GAME_ID)

    # get gross income sums for each nation using gross income data
    sum_dict = {}
    for temp in nation_table:
        sum_dict[temp.name] = 0
        for resource_name in temp._resources:
            if resource_name in ["Coal", "Oil", "Energy"]:
                sum_dict[temp.name] += float(temp.get_gross_income(resource_name))
    
    # check if nation has the greatest sum
    nation_name_sum = sum_dict[nation.name]
    for temp_nation_name, sum in sum_dict.items():
        if temp_nation_name != nation.name and sum >= nation_name_sum:
            return False

    return True

def industrial_focus(nation: Nation) -> bool:

    # load game data
    GAME_ID = nation.game_id
    nation_table = NationTable(GAME_ID)

    # get gross income sums for each nation using gross income data
    sum_dict = {}
    for temp in nation_table:
        sum_dict[temp.name] = 0
        for resource_name in temp._resources:
            if resource_name in ["Basic Materials", "Common Metals", "Advanced Metals"]:
                sum_dict[temp.name] += float(temp.get_gross_income(resource_name))
    
    # check if nation has the greatest sum
    nation_name_sum = sum_dict[nation.name]
    for temp_nation_name, sum in sum_dict.items():
        if temp_nation_name != nation.name and sum >= nation_name_sum:
            return False

    return True

def hegemony(nation: Nation) -> bool:

    # load game data
    GAME_ID = nation.game_id
    nation_table = NationTable(GAME_ID)
    
    puppet_str = f"{nation.name} Puppet State"
    for temp in nation_table:
        if puppet_str == temp.status:
            return True

    return False

def monopoly(nation: Nation) -> bool:

    # load game data
    GAME_ID = nation.game_id
    nation_table = NationTable(GAME_ID)

    # create tag for tracking this if it doesn't already exist
    if "Monopoly" not in nation.tags:
        new_tag = {
            "Expire Turn": 99999
        }
        nation.tags["Monopoly"] = new_tag

    # check resources
    for resource_name in nation._resources:
        
        if resource_name == "Military Capacity":
            continue
        
        # check nation gross income of resource vs all other players
        if any(float(nation.get_gross_income(resource_name)) <= float(temp.get_gross_income(resource_name)) for temp in nation_table):
            if resource_name in nation.tags["Monopoly"]:
                # reset streak if broken by deleting record
                del nation.tags["Monopoly"][resource_name]
            continue
        
        # update monopoly streak
        if resource_name in nation.tags["Monopoly"]:
            nation.tags["Monopoly"][resource_name] += 1
        else:
            nation.tags["Monopoly"][resource_name] = 1

        # return true if streak has reached thresh
        if nation.tags["Monopoly"][resource_name] >= 16:
            return True

    return False

def nuclear_deterrent(nation: Nation) -> bool:

    # load game data
    GAME_ID = nation.game_id
    nation_table = NationTable(GAME_ID)

    # get nuke counts
    sum_dict = {}
    for temp in nation_table:
        sum_dict[temp.name] = temp.nuke_count
    
    # check if nation has the greatest sum
    nation_name_sum = sum_dict[nation.name]
    for temp_nation_name, sum in sum_dict.items():
        if temp_nation_name != nation.name and sum >= nation_name_sum:
            return False
        
    # check if nation has at least 6 nukes
    if nation.nuke_count < 6:
        return False

    return True

def strong_research_agreement(nation: Nation) -> bool:

    # load game data
    GAME_ID = nation.game_id
    alliance_table = AllianceTable(GAME_ID)

    for alliance in alliance_table:
        if nation.name in alliance.current_members and alliance.type == "Research Agreement":
            amount, resource_name = alliance.get_yield()
            if amount >= 8:
                return True

    return False

def strong_trade_agreement(nation: Nation) -> bool:

    # load game data
    GAME_ID = nation.game_id
    alliance_table = AllianceTable(GAME_ID)

    for alliance in alliance_table:
        if nation.name in alliance.current_members and alliance.type == "Trade Agreement":
            amount, resource_name = alliance.get_yield()
            if amount >= 24:
                return True

    return False

def sphere_of_influence(nation: Nation) -> bool:

    # load game data
    GAME_ID = nation.game_id
    agenda_data_dict = core.get_scenario_dict(GAME_ID, "Agendas")

    agenda_count = 0
    for research_name in nation.completed_research:
        if research_name in agenda_data_dict:
            agenda_count += 1
    
    if agenda_count >= 8:
        return True

    return False

def underdog(nation: Nation) -> bool:

    # load game data
    GAME_ID = nation.game_id
    war_table = WarTable(GAME_ID)

    # search for an underdog victory
    for war in war_table:

        # skip wars player not involved in
        if nation.id not in war.combatants:
            continue
        
        # skip wars player did not win
        if not ("Attacker" in war.outcome and "Attacker" in war.get_role(nation.id)
            or "Defender" in war.outcome and "Defender" in war.get_role(nation.id)):
            continue
        
        # count sides
        friendly_count = 0
        hostile_count = 0
        for combatant_id in war.combatants:
            if combatant_id == nation.id:
                friendly_count += 1
                continue
            if war.is_on_same_side(combatant_id, nation.id):
                friendly_count += 1
            else:
                hostile_count += 1

        # vc fullfilled if friendly side outnumbered
        if friendly_count < hostile_count:
            return True

    return False

def warmonger(nation: Nation) -> bool:

    # load game data
    GAME_ID = nation.game_id
    war_table = WarTable(GAME_ID)

    count = 0
    for war in war_table:
        if war.outcome == "Attacker Victory" and war.get_role(nation.id) == "Main Attacker":
            count += 1
    
    if count >= 3:
        return True

    return False

# hard

def economic_domination(nation: Nation) -> bool:

    # load game data
    GAME_ID = nation.game_id
    nation_table = NationTable(GAME_ID)

    # check if first and not tied
    first, second, third = nation_table.get_top_three("netIncome")
    if nation.name in first[0] and (first[1] > second[1]):
        return True

    return False

def influence_through_trade(nation: Nation) -> bool:

    # load game data
    GAME_ID = nation.game_id
    nation_table = NationTable(GAME_ID)

    # check if first and not tied
    first, second, third = nation_table.get_top_three("transactionCount")
    if nation.name in first[0] and (first[1] > second[1]):
        return True

    return False

def military_superpower(nation: Nation) -> bool:

    # load game data
    GAME_ID = nation.game_id
    nation_table = NationTable(GAME_ID)

    # check if first and not tied
    first, second, third = nation_table.get_top_three("militaryStrength")
    if nation.name in first[0] and (first[1] > second[1]):
        return True

    return False

def scientific_leader(nation: Nation) -> bool:

    # load game data
    GAME_ID = nation.game_id
    nation_table = NationTable(GAME_ID)

    # check if first and not tied
    first, second, third = nation_table.get_top_three("researchCount")
    if nation.name in first[0] and (first[1] > second[1]):
        return True

    return False

def territorial_control(nation: Nation) -> bool:

    # load game data
    GAME_ID = nation.game_id
    nation_table = NationTable(GAME_ID)

    # check if first and not tied
    first, second, third = nation_table.get_top_three("nationSize")
    if nation.name in first[0] and (first[1] > second[1]):
        return True

    return False