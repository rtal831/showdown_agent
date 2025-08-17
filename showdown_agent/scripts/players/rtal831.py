from poke_env.battle import Battle
from poke_env.player import Player

team = """
Pikachu @ Focus Sash  
Ability: Static  
Tera Type: Electric  
EVs: 8 HP / 248 SpA / 252 Spe  
Timid Nature  
IVs: 0 Atk  
- Thunder Wave  
- Thunder  
- Reflect
- Thunderbolt  
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
