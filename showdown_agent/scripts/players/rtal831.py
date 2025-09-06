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

        # <<< METRICS TRACKING INITIALIZATION >>>
        self.metrics = {
            # Metric 1: Correct KO Identification
            'ko_opportunities': 0,
            'ko_successes': 0,
            # Metric 2: Threatened Switch Success Rate
            'threatened_turns': 0,
            'threatened_switches_successful': 0,
            # Metric 3: Safe Setup Opportunity Utilization
            'safe_setup_opportunities': 0,
            'safe_setup_attempts': 0,
            # ADD THESE LINES FOR METRIC 4
            'threatened_attack_score_sum': 0,
            'threatened_best_switch_score_sum': 0,
            'threatened_attack_count': 0,
            'safe_setup_attack_damage_sum': 0,
            'safe_setup_attack_count': 0,
        }

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

            if potential_damages and active.current_hp and max(potential_damages) >= active.current_hp:
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
        if opponent.moves:
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
        if opponent.moves:
            for mv in opponent.moves.values():
                if getattr(mv, "base_power", 0) > 0:
                    dmg = self._calculate_damage(mv, opponent, active, battle)
                    if active.current_hp and dmg >= active.current_hp:
                        is_in_danger = True
                        break

        if is_in_danger and damage_fraction < 0.5:
            score += 100

        return score

    def choose_move(self, battle: Battle):
        if battle.finished:
            return self.choose_random_move(battle)

        active = battle.active_pokemon
        opponent = battle.opponent_active_pokemon

        # <<< METRICS TRACKING LOGIC (RUNS BEFORE DECISION) >>>
        if opponent and active:
            # Metric 1: Correct KO Identification
            ko_move_available = False
            for move in battle.available_moves:
                damage = self._calculate_damage(move, active, opponent, battle)
                if opponent.current_hp and damage >= opponent.current_hp:
                    ko_move_available = True
                    break
            if ko_move_available:
                self.metrics['ko_opportunities'] += 1

            # Metric 2: Threatened Switch Success
            is_threatened = False
            if opponent.moves:
                for move in opponent.moves.values():
                    damage = self._calculate_damage(move, opponent, active, battle)
                    if active.current_hp and damage >= active.current_hp:
                        is_threatened = True
                        break
            if is_threatened:
                self.metrics['threatened_turns'] += 1

            # Metric 3: Safe Setup Opportunity
            is_safe_opportunity = False
            setup_move_available = any(m.id in ['dragondance', 'stealthrock', 'toxicspikes'] for m in battle.available_moves)
            if setup_move_available:
                max_incoming_dmg = 0
                if opponent.moves:
                    for move in opponent.moves.values():
                        damage = self._calculate_damage(move, opponent, active, battle)
                        if damage > max_incoming_dmg:
                            max_incoming_dmg = damage

                if active.max_hp and (max_incoming_dmg / active.max_hp) < 0.4:
                    is_safe_opportunity = True
                    self.metrics['safe_setup_opportunities'] += 1

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

        action_scores = {}
        for action_info in possible_actions:
            score = 0.0
            action = action_info['action']
            if action_info['type'] == 'move':
                score = self._score_move(action_info['action'], battle)
            elif action_info['type'] == 'switch':
                score = self._score_switch(action_info['action'], battle)

            action_scores[action] = score
            final_score = score + random.uniform(-5, 5)

            if final_score > best_score:
                best_score = final_score
                best_action = action_info['action']

        # <<< METRICS TRACKING LOGIC (RUNS AFTER DECISION) >>>
        if opponent and active and best_action:
            # Metric 1 Update
            if ko_move_available and isinstance(best_action, Move):
                damage = self._calculate_damage(best_action, active, opponent, battle)
                if opponent.current_hp and damage >= opponent.current_hp:
                    self.metrics['ko_successes'] += 1

            # Metric 2 Update
            if is_threatened and isinstance(best_action, Pokemon):
                max_dmg_to_switch_in = 0
                if opponent.moves:
                    for move in opponent.moves.values():
                        damage = self._calculate_damage(move, opponent, best_action, battle)
                        if damage > max_dmg_to_switch_in:
                            max_dmg_to_switch_in = damage
                if best_action.max_hp and (max_dmg_to_switch_in / best_action.max_hp) < 0.5:
                    self.metrics['threatened_switches_successful'] += 1

            # Metric 3 Update
            if is_safe_opportunity and isinstance(best_action, Move):
                if best_action.id in ['dragondance', 'stealthrock', 'toxicspikes']:
                    self.metrics['safe_setup_attempts'] += 1

            if is_threatened and isinstance(best_action, Move):
                self.metrics['threatened_attack_count'] += 1
                self.metrics['threatened_attack_score_sum'] += action_scores.get(best_action, 0)

                best_switch_score = -math.inf
                if battle.available_switches:
                    for switch_poke in battle.available_switches:
                        score = self._score_switch(switch_poke, battle)
                        if score > best_switch_score:
                            best_switch_score = score

                if best_switch_score > -math.inf:
                    self.metrics['threatened_best_switch_score_sum'] += best_switch_score

            if is_safe_opportunity and isinstance(best_action, Move) and best_action.id not in ['dragondance', 'stealthrock', 'toxicspikes']:
                self.metrics['safe_setup_attack_count'] += 1
                damage = self._calculate_damage(best_action, active, opponent, battle)
                if opponent.max_hp and opponent.max_hp > 0:
                    damage_percent = (damage / opponent.max_hp) * 100
                    self.metrics['safe_setup_attack_damage_sum'] += damage_percent

        if best_action:
            return self.create_order(best_action)
        return self.choose_random_move(battle)

    def report_final_metrics(self):
        """
        Calculates and prints the final metrics accumulated across all battles.
        """
        print("\n" + "="*45)
        print(f"FINAL BEHAVIOURAL METRICS REPORT FOR: {self.username}")
        print("-"*45)

        # Metric 1
        ko_opps = self.metrics['ko_opportunities']
        ko_succ = self.metrics['ko_successes']
        ko_rate = (ko_succ / ko_opps * 100) if ko_opps > 0 else float('nan')
        print(f"1. Correct KO Identification Rate: {ko_rate:.1f}% ({ko_succ}/{ko_opps})")

        # Metric 2
        threat_turns = self.metrics['threatened_turns']
        threat_succ = self.metrics['threatened_switches_successful']
        threat_rate = (threat_succ / threat_turns * 100) if threat_turns > 0 else float('nan')
        print(f"2. Threatened Switch Success Rate: {threat_rate:.1f}% ({threat_succ}/{threat_turns})")

        # Metric 3
        safe_opps = self.metrics['safe_setup_opportunities']
        safe_atts = self.metrics['safe_setup_attempts']
        safe_rate = (safe_atts / safe_opps * 100) if safe_opps > 0 else float('nan')
        print(f"3. Safe Setup Opportunity Utilization: {safe_rate:.1f}% ({safe_atts}/{safe_opps})")

        print("\n4. Opportunity Cost Analysis:")
        threat_count = self.metrics['threatened_attack_count']
        if threat_count > 0:
            avg_atk_score = self.metrics['threatened_attack_score_sum'] / threat_count
            avg_sw_score = self.metrics['threatened_best_switch_score_sum'] / threat_count
            print(f"  - On {threat_count} threatened turns, chosen attacks scored an avg of {avg_atk_score:.1f} vs. the best switch's avg of {avg_sw_score:.1f}.")
        else:
            print("  - No threatened turns where an attack was chosen.")

        safe_count = self.metrics['safe_setup_attack_count']
        if safe_count > 0:
            avg_dmg_pct = self.metrics['safe_setup_attack_damage_sum'] / safe_count
            print(f"  - On {safe_count} safe setup turns, chosen attacks dealt an avg of {avg_dmg_pct:.1f}% of opponent's max HP.")
        else:
            print("  - No safe setup opportunities were forgone for an attack.")

        print("="*45 + "\n")
