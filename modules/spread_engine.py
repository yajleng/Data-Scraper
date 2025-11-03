import numpy as np

def calculate_spread_edge(team_sp, opp_sp, line):
    true_diff = team_sp - opp_sp
    implied_win_prob = 1 / (1 + np.exp(-true_diff / 7))
    edge = implied_win_prob - (abs(line) / 30)
    return {"true_diff": true_diff, "win_prob": implied_win_prob, "edge": edge}
