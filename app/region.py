import json
import random
import os
from collections import deque
from typing import Union, Tuple

from app import core

class Region:

    def __init__(self, region_id: str, game_id: str):

        # check if game files exist
        regdata_filepath = f"gamedata/{game_id}/regdata.json"
        graph_filepath = f"maps/{core.get_map_str(game_id)}/graph.json"
        if not (os.path.exists(regdata_filepath) and os.path.exists(graph_filepath)):
            raise FileNotFoundError(f"Error: Unable to locate required game files during Region class initialization.")
        
        # load game files
        with open(regdata_filepath, 'r') as json_file:
            regdata_dict = json.load(json_file)
        with open(graph_filepath, 'r') as json_file:
            graph_dict = json.load(json_file)

        # set attributes
        self.game_id: str = game_id
        self.region_id: str = region_id
        self.data: dict = regdata_dict[region_id]["regionData"]
        self.owner_id: int = self.data["ownerID"]
        self.occupier_id: int = self.data["occupierID"]
        self.purchase_cost: int = self.data["purchaseCost"]
        self.resource: str = self.data["regionResource"]
        self.fallout: int = self.data["nukeTurns"]
        self.is_edge: bool = graph_dict[self.region_id]["isEdgeOfMap"]
        self.is_significant: bool = graph_dict[self.region_id]["hasRegionalCapital"]
        self.is_magnified: bool = graph_dict[self.region_id]["isMagnified"]
        self.is_start: bool = graph_dict[self.region_id]["randomStartAllowed"]
        self.additional_region_coordinates: list = graph_dict[self.region_id]["additionalRegionCords"]
        self.adjacent_regions: dict = graph_dict[self.region_id]["adjacencyMap"]
        self.claim_list = []
    
    def __eq__(self, other):
        """
        Equality comparison.
        """
        if isinstance(other, Region):
            return self.region_id == other.region_id
        return False

    def _save_changes(self) -> None:
        """
        Saves changes made to Region object to game files.
        """

        regdata_filepath = f"gamedata/{self.game_id}/regdata.json"
        with open(regdata_filepath, 'r') as json_file:
            regdata_dict = json.load(json_file)
        
        self.data["ownerID"] = self.owner_id
        self.data["occupierID"] = self.occupier_id
        self.data["purchaseCost"] = self.purchase_cost
        self.data["regionResource"] = self.resource
        self.data["nukeTurns"] = self.fallout
        
        regdata_dict[self.region_id]["regionData"] = self.data
        with open(regdata_filepath, 'w') as json_file:
            json.dump(regdata_dict, json_file, indent=4)

    def set_owner_id(self, new_owner_id: int) -> None:
        """
        Changes the owner of a region.
        """
        self.owner_id = new_owner_id
        self._save_changes()
    
    def set_occupier_id(self, new_owner_id: int) -> None:
        """
        Changes the occupier of a region.
        """
        self.occupier_id = new_owner_id
        self._save_changes()
    
    def increase_purchase_cost(self, amount=5) -> None:
        """
        Increases purchase cost of the region. 
        
        Params:
            amount (int): Amount of dollars to increase cost by. Default value is 5 dollars.
        """
        self.purchase_cost += amount
        self._save_changes()
 
    def set_resource(self, new_resource: str) -> None:
        """
        Changes the resource in a region.
        """
        self.resource = new_resource
        self._save_changes()

    def set_fallout(self, amount=4) -> None:
        """
        Sets fallout amount.

        Params:
            amount (int): Amount of fallout. Default value is 4 turns.
        """
        self.fallout = amount
        self._save_changes()
    
    def decrease_fallout(self) -> None:
        """
        Decreases fallout by one turn.
        """
        self.data["nukeTurns"] -= 1
        self._save_changes()

    def add_claim(self, player_id: int) -> None:
        """
        Adds player id to claim list. Used for region purchase action.
        """
        self.claim_list.append(player_id)


    # basic methods
    ################################################################################

    def owned_adjacent_regions(self) -> list:
        """
        Gets a list of regions adjacent to this one owned by same player.

        Returns:
            list: region_ids of adjacent region owned by the player.
        """
        owned_adjacent_list = []
        for region_id in self.adjacent_regions:
            temp = Region(region_id, self.game_id)
            if temp.owner_id == self.owner_id:
                owned_adjacent_list.append(region_id)
        return owned_adjacent_list

    def get_regions_in_radius(self, radius: int) -> set:
        """
        Gets a set of regions within a set radius of this region.

        Parameters:
            radius (int): radius to check

        Returns:
            set: region_ids within a set radius of this region, including original region.
        """
        
        visited = set([self.region_id])
        queue = deque([(self.region_id, 0)])
        
        while queue:

            current_region_id, depth = queue.popleft()
            
            if depth < radius:
                current_region = Region(current_region_id, self.game_id)
                for adjacent_id in current_region.adjacent_regions:
                    if adjacent_id not in visited:
                        visited.add(adjacent_id)
                        queue.append((adjacent_id, depth + 1))
        
        return visited
    
    def check_for_adjacent_improvement(self, improvement_names: set) -> bool:
        """
        Checks if there is an improvement in improvement_names in an owned adjacent region.
        
        Parameters:
            improvement_names (set): A set of improvement names.

        Returns:
            bool: True if improvement found. False otherwise.
        """
        from app.improvement import Improvement
        
        for region_id in self.owned_adjacent_regions():
            region_improvement = Improvement(region_id, self.game_id)
            if region_improvement.name in improvement_names:
                return True

        return False
    
    def check_for_adjacent_unit(self, unit_names: set, unit_owner_id: 0) -> bool:
        """
        Checks if there is an unit in unit_names in an adjacent region.
        
        Parameters:
            unit_names (set): A set of unit names.
            unit_owner_id (int): Expected owner of the unit.
        
        Returns:
            bool: True if unit found. False otherwise.
        """
        from app.unit import Unit
        
        for region_id in self.adjacent_regions:
            region_unit = Unit(region_id, self.game_id)
            if unit_owner_id != 0 and unit_owner_id != region_unit.owner_id:
                continue
            if region_unit.name in unit_names:
                return True

        return False
    
    def find_suitable_region(self) -> str | None:
        """
        Finds a region to move the unit in this region to.
        Called only for withdraws at the moment, but this function could be generalized in the future.

        Returns:
            str: Suitable region_id if found, otherwise None.
        """

        from app.unit import Unit

        withdrawing_unit = Unit(self.region_id, self.game_id)
        queue = deque([self.region_id])
        visited = set()

        while queue:
            
            current_region_id = queue.popleft()

            # skip if we have already checked this region
            if current_region_id in visited:
                continue
            visited.add(current_region_id)

            current_region = Region(current_region_id, self.game_id)
            current_region_unit = Unit(current_region_id, self.game_id)

            # check if region is suitable
            if (
                current_region.owner_id == withdrawing_unit.owner_id    # region must be owned by the unit owner
                and current_region_unit.name is None                    # region must not have another unit in it
                and current_region.occupier_id == 0                     # region must not be occupied by another nation
            ):
                return current_region_id
            
            # if not add adjacent regions to queue
            for adjacent_id in current_region.adjacent_regions:
                if adjacent_id not in visited:
                    queue.append(adjacent_id)

        # return None if we failed to find a region
        return None
    
    # combat methods
    ################################################################################

    def is_valid_move(self, other_player_id: int) -> bool:
        """
        Determines if a unit owned by other_player_id can move into this region.
        Only takes into account ownership. Does not consider adjacency or other disqualifiers.

        Params:
            other_player_id (int): player_id to compare to
        
        Returns:
            bool: True if all checks pass. False otherwise.
        """
        
        from app.war import WarTable
        war_table = WarTable(self.game_id)

        # you can always move into regions owned by you
        if self.owner_id == other_player_id:
            return True

        # you may move into unoccupied regions owned by an enemy
        if war_table.get_war_name(str(self.owner_id), str(other_player_id)) is not None and self.occupier_id == 0:
            return True
        
        # you may move into occupied regions owned by an enemy in two cases
        elif war_table.get_war_name(str(self.owner_id), str(other_player_id)) is not None and self.occupier_id != 0:
            # you are the occupier
            if self.occupier_id == other_player_id:
                return True
            # you are also at war with the occupier
            if war_table.get_war_name(str(self.owner_id), str(other_player_id)) is not None:
                return True
            
        # foreign invasion may move into unclaimed regions
        if self.owner_id == 0 and other_player_id == 99:
            return True
                
        return False

    # event specific methods
    ################################################################################

    def infection(self) -> int:
        """
        Returns infection score of region.
        Used for Pandemic event.
        """
        return self.data["infection"]
    
    def add_infection(self, amount=1) -> None:
        """
        Increases infection score of region.
        Used for Pandemic event.
        """
        self.data["infection"] += amount
        if self.data["infection"] > 5:
            self.data["infection"] = 5
        elif self.data["infection"] < 0:
            self.data["infection"] = 0
        self._save_changes()
    
    def is_quarantined(self) -> bool:
        """
        Returns True if region is quarantined.
        Used for Pandemic event.
        """
        return self.data["quarantine"]
    
    def set_quarantine(self, enable=True) -> None:
        """
        Toggles region. quarantine
        Used for Pandemic event.
        """
        self.data["quarantine"] = enable
        self._save_changes()

    
        