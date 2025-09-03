import math
import random
from typing import Optional

from poke_env.battle import Battle
from poke_env.player import Player
from poke_env.data import GenData
from poke_env.battle.move import Move
from poke_env.battle.pokemon import Pokemon
from poke_env.battle.side_condition import SideCondition

# my ubers team
team = """
Koraidon @ Choice Band  
Ability: Orichalcum Pulse  
Tera Type: Fighting  
EVs: 252 Atk / 4 SpD / 252 Spe  
Jolly Nature  
- Flare Blitz  
- Close Combat  
- U-turn  
- Dragon Claw  

Rayquaza @ Life Orb  
Ability: Air Lock  
Tera Type: Dragon  
EVs: 252 Atk / 4 SpD / 252 Spe  
Jolly Nature  
- Dragon Dance  
- Dragon Ascent  
- Earthquake  
- Extreme Speed  

Necrozma-Dusk-Mane @ Rocky Helmet  
Ability: Prism Armor  
Tera Type: Psychic  
EVs: 252 HP / 252 Def / 4 SpD  
Impish Nature  
- Stealth Rock  
- Morning Sun  
- Sunsteel Strike  
- Knock Off  

Ho-Oh @ Heavy-Duty Boots  
Ability: Regenerator  
Tera Type: Fire  
EVs: 248 HP / 252 Def / 8 Spe  
Impish Nature  
- Brave Bird  
- Sacred Fire  
- Recover  
- Whirlwind  

Eternatus @ Black Sludge  
Ability: Pressure  
Tera Type: Poison  
EVs: 252 HP / 252 SpD / 4 Spe  
Calm Nature  
IVs: 0 Atk  
- Dynamax Cannon  
- Sludge Bomb  
- Recover  
- Toxic Spikes  

Arceus-Ghost @ Spooky Plate  
Ability: Multitype  
Tera Type: Ghost  
EVs: 252 HP / 4 Def / 252 SpD  
Calm Nature  
IVs: 0 Atk  
- Judgment  
- Recover  
- Will-O-Wisp  
- Taunt
"""

class CustomAgent(Player):
    def __init__(self, *args, **kwargs):
        super().__init__(team=team, *args, **kwargs)
        # load gamedata for stats
        try:
            self._gen9 = GenData.from_gen(9)
            self._base_stats = getattr(self._gen9, "base_stats", {}) or {}
        except Exception:
            self._gen9 = None
            self._base_stats = {}

    def _base_stat_fallback(self, poke: Pokemon, stat_name: str) -> int:
        species = getattr(poke, "species", None)
        if not species:
            return 100
        key = species.lower().replace(" ", "").replace("-", "").replace("'", "")
        try:
            base = self._base_stats.get(key, None)
            if base:
                lookup = {
                    'atk': ['atk', 'attack'],
                    'def': ['def', 'defense'],
                    'spa': ['spa', 'spatk', 'spc'],
                    'spd': ['spd', 'spdef'],
                    'spe': ['spe', 'speed'],
                }
                for k in lookup[stat_name]:
                    if k in base:
                        return int(base[k])
        except Exception:
            pass
        return 100

    def _get_stat_safe(self, poke: Pokemon, stat_key: str) -> float:
        val = None
        try:
            val = poke.stats.get(stat_key)
        except Exception:
            val = None

        if val is None:
            # use base stats if unknown
            return float(self._base_stat_fallback(poke, stat_key))
        return float(val)

    def _calculate_damage(
            self, move: Move, attacker: Pokemon, defender: Pokemon, battle: Battle, is_estimate: bool = True
    ) -> int:
        # no dmg on status moves
        base_power = getattr(move, "base_power", None)
        if not base_power or base_power == 0:
            return 0

        level = 100.0

        if move.category.name == 'PHYSICAL':
            attack_stat = self._get_stat_safe(attacker, 'atk')
            defense_stat = self._get_stat_safe(defender, 'def')
            atk_stage = attacker.boosts.get('atk', 0)
            def_stage = defender.boosts.get('def', 0)
        elif move.category.name == 'SPECIAL':
            attack_stat = self._get_stat_safe(attacker, 'spa')
            defense_stat = self._get_stat_safe(defender, 'spd')
            atk_stage = attacker.boosts.get('spa', 0)
            def_stage = defender.boosts.get('spd', 0)
        else:
            return 0

        # stat boosts
        try:
            if atk_stage > 0:
                attack_stat *= (2 + atk_stage) / 2
            else:
                attack_stat *= 2 / (2 - atk_stage)
        except Exception:
            attack_stat = max(1.0, attack_stat)

        try:
            if def_stage > 0:
                defense_stat *= (2 + def_stage) / 2
            else:
                defense_stat *= 2 / (2 - def_stage)
        except Exception:
            defense_stat = max(1.0, defense_stat)

        damage = (((2 * level / 5) + 2) * base_power * (attack_stat / defense_stat)) / 50 + 2

        # weather
        try:
            weather = battle.weather or ""
            if 'SUNNYDAY' in weather and move.type.name == 'FIRE':
                damage *= 1.5
            elif 'SUNNYDAY' in weather and move.type.name == 'WATER':
                damage *= 0.5
            elif 'RAINDANCE' in weather and move.type.name == 'WATER':
                damage *= 1.5
            elif 'RAINDANCE' in weather and move.type.name == 'FIRE':
                damage *= 0.5
        except Exception:
            pass

        # STAB
        try:
            if hasattr(move.type, "name"):
                if move.type.name in [t.name for t in attacker.types]:
                    damage *= 1.5
            else:
                if move.type in attacker.types:
                    damage *= 1.5
        except Exception:
            pass

        # type effectiveness
        try:
            type_multiplier = move.type.damage_multiplier(
                defender.type_1, defender.type_2, type_chart=battle._data.type_chart
            )
            damage *= type_multiplier
        except Exception:
            # assume neutral if unsure
            pass

        # items
        item = getattr(attacker, "item", "") or ""
        try:
            if item.lower() == 'choiceband' and move.category.name == 'PHYSICAL':
                damage *= 1.5
            if item.lower() == 'lifeorb':
                damage *= 1.3
            if item.lower() == 'earthplate' and getattr(move.type, "name", "") == 'GROUND':
                damage *= 1.2
            if item.lower() == 'spookyplate' and getattr(move.type, "name", "") == 'GHOST':
                damage *= 1.2
        except Exception:
            pass

        # abilities
        try:
            if attacker.ability == 'orichalcumpulse' and 'SUNNYDAY' in (battle.weather or "") and move.category.name == 'PHYSICAL':
                damage *= 1.33
            if defender.ability == 'prismarmor' and type_multiplier > 1:
                damage *= 0.75
        except Exception:
            pass

        # avg dmg roll
        if is_estimate:
            damage *= 0.925

        try:
            return max(0, int(damage))
        except Exception:
            return 0

    def _score_move(self, move: Move, battle: Battle) -> float:
        active = battle.active_pokemon
        opponent = battle.opponent_active_pokemon
        score = 0.0

        base_power = getattr(move, "base_power", 0) or 0
        move_id = getattr(move, "id", "")
        move_priority = getattr(move, "priority", 0)
        move_heal = getattr(move, "heal", 0)
        move_self_boost = getattr(move, "self_boost", False)
        move_self_switch = getattr(move, "self_switch", False)

        # 1. damage
        if opponent and base_power > 0:
            damage = self._calculate_damage(move, active, opponent, battle)

            score += (damage / (opponent.max_hp or 1)) * 130

            # be aggressive vs ubers
            if opponent.species and opponent.species.lower() in [
                "koraidon", "miraidon", "rayquaza", "zacian", "calyrex-shadow",
                "necrozma-dusk-mane", "arceus-ghost", "eternatus", "ho-oh"
            ]:
                score += (damage / (opponent.max_hp or 1)) * 50

            # huge bonus for KO
            if damage >= (opponent.current_hp or 1):
                score += 1200

        # healing
        if move_heal > 0 or move_id in ['morningsun', 'recover']:
            # heal if below 70%
            if (active.current_hp_fraction or 1.0) < 0.7:
                score += (1 - (active.current_hp_fraction or 0)) * 150
            else:
                score -= 20  # dont heal at full

        # setup
        if move_self_boost and sum(active.boosts.values()) < 6:
            setup_bonus = 60
            if (active.current_hp_fraction or 0) < 0.5:
                setup_bonus /= 2
            score += setup_bonus

        # hazards
        if getattr(move, "side_condition", None):
            if move_id == 'stealthrock' and SideCondition.STEALTH_ROCK not in battle.opponent_side_conditions:
                score += 70
            if move_id == 'toxicspikes' and battle.opponent_side_conditions.get(SideCondition.TOXIC_SPIKES, 0) < 2:
                score += 50

        # hazard removal
        if move_id == 'defog':
            hazard_count = 0
            if SideCondition.STEALTH_ROCK in battle.side_conditions:
                hazard_count += 1
            hazard_count += battle.side_conditions.get(SideCondition.TOXIC_SPIKES, 0)
            if hazard_count > 0:
                score += 100 * hazard_count

        # disruption
        if move_id == 'whirlwind' and opponent and any(b > 0 for b in (opponent.boosts.values() or [])):
            score += 80
        if move_id == 'knockoff' and opponent and getattr(opponent, "item", None):
            score += 40

        # status moves
        try:
            opp_atk = self._get_stat_safe(opponent, 'atk') if opponent else 0
            opp_spa = self._get_stat_safe(opponent, 'spa') if opponent else 0
            if move_id == 'willowisp' and opponent and not getattr(opponent, "status", None) and opp_atk > opp_spa:
                score += 50
            if move_id == 'sacredfire' and opponent and not getattr(opponent, "status", None):
                score += 25
        except Exception:
            pass

        # safety check
        if opponent and opponent.moves:
            # check for KO risk
            potential_damages = [
                self._calculate_damage(mv, opponent, active, battle)
                for mv in opponent.moves.values()
                if getattr(mv, "base_power", 0) > 0
            ]

            if potential_damages and active.current_hp <= max(potential_damages):
                # if in danger, dont setup
                if base_power == 0:
                    score -= 80

        # pivoting
        if move_self_switch:
            score += 35

        # priority moves
        if move_priority > 0:
            try:
                opp_spe = self._get_stat_safe(opponent, 'spe') if opponent else 0
                active_spe = self._get_stat_safe(active, 'spe')
                if opponent and opp_spe > active_spe:
                    damage = self._calculate_damage(move, active, opponent, battle)
                    if damage >= (opponent.current_hp or 1):
                        score += 50
                    else:
                        score += 20
            except Exception:
                score += 10

        return score

    def _score_switch(self, switch_target: Pokemon, battle: Battle) -> float:
        active = battle.active_pokemon
        opponent = battle.opponent_active_pokemon
        score = 0.0

        if not opponent:
            return -100.0

        # how much dmg will we take?
        max_damage = 0
        for mv in opponent.moves.values():
            if getattr(mv, "base_power", 0) > 0:
                dmg = self._calculate_damage(mv, opponent, switch_target, battle)
                if dmg > max_damage:
                    max_damage = dmg

        damage_fraction = max_damage / (switch_target.max_hp or 1)
        score += (1 - damage_fraction) * 100

        # how much dmg can we do?
        best_damage_output = 0
        for mv in switch_target.moves.values():
            if getattr(mv, "base_power", 0) > 0:
                dmg = self._calculate_damage(mv, switch_target, opponent, battle)
                if dmg > best_damage_output:
                    best_damage_output = dmg

        score += (best_damage_output / (opponent.max_hp or 1)) * 50

        # penalize switching
        score -= 25

        # regenerator bonus
        try:
            if active.ability == 'regenerator' and (active.current_hp_fraction or 0) < 1:
                score += 33
        except Exception:
            pass

        # crisis switch
        is_in_danger = False
        for mv in opponent.moves.values():
            if getattr(mv, "base_power", 0) > 0:
                dmg = self._calculate_damage(mv, opponent, active, battle)
                if dmg >= (active.current_hp or 1):
                    is_in_danger = True
                    break

        if is_in_danger and damage_fraction < 0.5:
            score += 100

        return score

    def choose_move(self, battle: Battle):
        if battle.finished:
            return self.choose_random_move(battle)

        possible_actions = []
        if battle.available_moves:
            for mv in battle.available_moves:
                possible_actions.append({'type': 'move', 'action': mv})
        if battle.available_switches:
            for sw in battle.available_switches:
                possible_actions.append({'type': 'switch', 'action': sw})

        if not possible_actions:
            return self.choose_random_move(battle)

        best_action = None
        best_score = -math.inf

        for action_info in possible_actions:
            score = 0.0
            if action_info['type'] == 'move':
                score = self._score_move(action_info['action'], battle)
            elif action_info['type'] == 'switch':
                score = self._score_switch(action_info['action'], battle)

            score += random.uniform(-5, 5)

            if score > best_score:
                best_score = score
                best_action = action_info['action']

        if best_action:
            return self.create_order(best_action)
        return self.choose_random_move(battle)
