from poke_env.battle import Battle
from poke_env.player import Player

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
EVs: 252 SpA / 4 SpD / 252 Spe  
Timid Nature  
IVs: 0 Atk  
- Dynamax Cannon  
- Sludge Bomb  
- Recover  
- Toxic Spikes  

Arceus-Ground @ Earth Plate  
Ability: Multitype  
Tera Type: Ground  
EVs: 252 Atk / 4 SpD / 252 Spe  
Jolly Nature  
- Swords Dance  
- Earthquake  
- Stone Edge  
- Recover   
"""


class CustomAgent(Player):
    def __init__(self, *args, **kwargs):
        super().__init__(team=team, *args, **kwargs)

    def choose_move(self, battle: Battle):
        if battle.finished:
            return

        opponent = battle.opponent_active_pokemon
        active = battle.active_pokemon

        # if low HP, consider switching
        if active.current_hp_fraction < 0.35:
            for mon in battle.team.values():
                if mon is not active and not mon.fainted:
                    # resistance check
                    if opponent and (opponent.type_1 in mon.types or opponent.type_2 in mon.types):
                        return self.create_order(mon)

        # pick highest damage move for baseline
        best_moves = []
        best_damage = -1

        for move in battle.available_moves:
            # estimate simple damage = base power * type effectiveness
            multiplier = 1.0
            if opponent:
                multiplier = move.type.damage_multiplier(
                    opponent.type_1, opponent.type_2, type_chart=battle._data.type_chart
                )

            damage = move.base_power * multiplier

            if damage > best_damage:
                best_damage = damage
                best_moves = [move]
            elif damage == best_damage:
                best_moves.append(move)

        if best_moves:
            import random
            return self.create_order(random.choice(best_moves))

        # fallback: just pick something
        return self.choose_random_move(battle)
