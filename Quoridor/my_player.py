from player_quoridor import PlayerQuoridor
from seahorse.game.action import Action
from game_state_quoridor import GameStateQuoridor

class MyPlayer(PlayerQuoridor):
    
    SEARCH_DEPTH = 2
    VICTORY_VALUE = 1000
    DEFEAT_VALUE = -1000
    
    def __init__(self, piece_type: str, goal_row: int=0, name: str = "bob", *args, **kwargs) -> None:
        """
        Initialize the PlayerQuoridor instance.

        Args:
            piece_type (str): Type of the player's game piece
            goal_row (int): The row the player wants to reach
            name (str, optional): Name of the player (default is "bob")
        """
        super().__init__(piece_type, goal_row, name)

    def compute_action(self, current_state: GameStateQuoridor, remaining_time: float = 15*60, **kwargs) -> Action:
        """
        Use the minimax algorithm to choose the best action based on the heuristic evaluation of game states.

        Args:
            current_state (GameStateQuoridor): The current game state.

        Returns:
            Action: The best action as determined by minimax.
        """

        #TODO
        legal_actions = list(current_state.generate_possible_stateless_actions())

        selected_action = legal_actions[0]
        selected_value = float("-inf")

        for candidate_action in legal_actions:
            resulting_state = current_state.apply_action(candidate_action)

            candidate_value = self._search_value(resulting_state,self.SEARCH_DEPTH - 1)

            if candidate_value > selected_value:
                selected_value = candidate_value
                selected_action = candidate_action

        return selected_action

    def _search_value(self, game_state: GameStateQuoridor, remaining_depth: int) -> float:

        if game_state.is_done() or remaining_depth == 0:
            return self._evaluate_position(game_state)

        current_player_id = game_state.active_player.get_id()

        if current_player_id == self.get_id():
            return self._maximize(game_state, remaining_depth)

        return self._minimize(game_state, remaining_depth)

    def _maximize(self, game_state: GameStateQuoridor, remaining_depth: int) -> float:

        legal_actions = list( game_state.generate_possible_stateless_actions())

        if len(legal_actions) == 0:
            return self._evaluate_position(game_state)

        highest_value = float("-inf")

        for action in legal_actions:
            child_state = game_state.apply_action(action)

            child_value = self._search_value(child_state, remaining_depth - 1)

            if child_value > highest_value:
                highest_value = child_value

        return highest_value

    def _minimize(self, game_state: GameStateQuoridor, remaining_depth: int) -> float:

        legal_actions = list(game_state.generate_possible_stateless_actions())

        if len(legal_actions) == 0:
            return self._evaluate_position(game_state)

        lowest_value = float("inf")

        for action in legal_actions:
            child_state = game_state.apply_action(action)

            child_value = self._search_value(child_state, remaining_depth - 1)

            if child_value < lowest_value:
                lowest_value = child_value

        return lowest_value

    def _evaluate_position(self, game_state: GameStateQuoridor) -> float:

        agent = None
        opponent = None

        for player in game_state.players:
            if player.get_id() == self.get_id():
                agent = player
            else:
                opponent = player

        if game_state.is_done():
            agent_score = game_state.scores.get(agent.get_id(), 0.0)

            if agent_score == 1.0:
                return self.VICTORY_VALUE

            return self.DEFEAT_VALUE

        agent_distance = game_state._shortest_path(agent)
        opponent_distance = game_state._shortest_path(opponent)

        return opponent_distance - agent_distance