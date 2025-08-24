from poke_env.battle import Battle
from poke_env.player import Player

team = """
Koraidon @ Choice Band  
Ability: Orichalcum Pulse  
Tera Type: Fighting  
EVs: 252 SpA / 4 SpD / 252 Spe  
Jolly Nature  
- Flare Blitz  
- Close Combat  
- U-turn  
- Dragon Claw  

Rayquaza @ Life Orb  
Ability: Air Lock  
Tera Type: Dragon  
EVs: 252 SpA / 4 SpD / 252 Spe  
Jolly Nature  
- Dragon Dance  
- Dragon Ascent  
- Earthquake  
- Extreme Speed  

Necrozma-Dusk-Mane @ Rocky Helmet  
Ability: Prism Armor  
Tera Type: Psychic  
EVs: 252 SpA / 4 SpD / 252 Spe  
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
EVs: 252 SpA / 4 SpD / 252 Spe  
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

        opponent_pokemon = battle.opponent_active_pokemon

        best_moves = []
        best_damage = -1

        for move in battle.available_moves:
            damage = move.base_power * move.type.damage_multiplier(
                opponent_pokemon.type_1, opponent_pokemon.type_2, type_chart=battle._data.type_chart
            )

            if damage > best_damage:
                best_damage = damage
                best_moves = [move]

            elif damage == best_damage:
                best_moves.append(move)

        if best_moves:
            import random
            best_move = random.choice(best_moves)
            return self.create_order(best_move)

        return self.choose_random_move(battle)
