import pickle
import numpy as np
import matplotlib.pyplot as plt

PARKED_DEADBAND = 2 # distance to spot where a stopped car would be considered in that spot
MOVING_DEADBAND = 0.0001
IDLE_MIN_TIME = 15 # number of seconds car must be at 0 velocity before it's considered idle

with open('raw_agent_data.pickle', 'rb') as f: # file generated by generate_agent_data in dlp-dataset
    agent_data = pickle.load(f)

final_json = {}

for agent_token in agent_data:

    agent = agent_data[agent_token]

    json_dict = {"task_profile": []}

    spawn_index = -1
    i = 0

    while spawn_index == -1:
        if agent["v"][i] >= MOVING_DEADBAND:
            spawn_index = i
            json_dict["init_time"] = agent["t"][i]
        else:
            i += 1

    if agent["dist_to_closest_spot"][max(spawn_index - 1, 0)] < PARKED_DEADBAND:
        json_dict["init_spot"] = agent["closest_spot"][max(spawn_index - 1, 0)]
        json_dict["init_heading"] = np.pi / 2 if agent["heading"][max(spawn_index - 1, 0)] < np.pi else 3 * np.pi / 2
    else:
        json_dict["init_coords"] = agent["coords"][0]
        json_dict["init_heading"] = agent["heading"][max(spawn_index - 1, 0)]
    json_dict["init_v"] = agent["v"][0]
    json_dict["width"] = agent["size"][1]
    json_dict["length"] = agent["size"][0]

    # i is at spawn_time

    sec_start = spawn_index # the start of this section, or if in a zero section, the start of the section before the zero section
    zero_sec_start = -1 # -1 if not currently in a zero section, else the first index of this zero section
    sec_max_speed = -1

    def add_non_idle_section(end_step): # end timestep is the last timestep of the non-idle section 
        if agent["dist_to_closest_spot"][end_step] < PARKED_DEADBAND: # cruise + park
            json_dict["task_profile"].append({"name": "CRUISE", "v_cruise": sec_max_speed, "target_spot_index": agent["closest_spot"][end_step]})
            json_dict["task_profile"].append({"name": "PARK", "target_spot_index": agent["closest_spot"][end_step]})
        else: # just cruise
            json_dict["task_profile"].append({"name": "CRUISE", "v_cruise": sec_max_speed, "target_coords": agent["coords"][end_step]})

    while i < len(agent["v"]):
        if agent["v"][i] < MOVING_DEADBAND: # not moving
            if zero_sec_start == -1: # this is the start of a zero section
                zero_sec_start = i
        else:
            if zero_sec_start != -1: # ending a zero section
                if agent["t"][i] - agent["t"][zero_sec_start] >= IDLE_MIN_TIME: # been zero for a while, so idle section
                    # add unpark if necessary
                    if agent["dist_to_closest_spot"][max(sec_start - 1, 0)] < PARKED_DEADBAND:
                        json_dict["task_profile"].append({"name": "UNPARK", "target_spot_index": agent["closest_spot"][max(sec_start - 1, 0)]})
                    if zero_sec_start - sec_start > 0: # add a non-idle section if there is one
                        add_non_idle_section(zero_sec_start - 1)
                    json_dict["task_profile"].append({"name": "IDLE", "duration": agent["t"][i] - agent["t"][zero_sec_start]})
                    sec_start = i + 1 # new section start
                    sec_max_speed = -1
            else:
                sec_max_speed = max(sec_max_speed, agent["v"][i])
            zero_sec_start = -1 # not in zero section anymore
        i += 1

    # get final section
    if zero_sec_start != -1: # ending a zero section
        if agent["t"][i - 1] - agent["t"][zero_sec_start] >= IDLE_MIN_TIME: # been zero for a while, so idle section
            # add unpark if necessary
            if agent["dist_to_closest_spot"][max(sec_start - 1, 0)] < PARKED_DEADBAND:
                json_dict["task_profile"].append({"name": "UNPARK", "target_spot_index": agent["closest_spot"][max(sec_start - 1, 0)]})
            if zero_sec_start - sec_start > 0: # add a non-idle section if there is one
                add_non_idle_section(zero_sec_start - 1)
            json_dict["task_profile"].append({"name": "IDLE", "duration": agent["t"][i - 1] - agent["t"][zero_sec_start]})
        else: # just add a normal section
            add_non_idle_section(i - 1)
    else: # just add a normal section
        # add unpark if necessary
        if agent["dist_to_closest_spot"][max(sec_start - 1, 0)] < PARKED_DEADBAND:
            json_dict["task_profile"].append({"name": "UNPARK", "target_spot_index": agent["closest_spot"][max(sec_start - 1, 0)]})
        add_non_idle_section(i - 1)

    # remove last section if it is idle
    if len(json_dict["task_profile"]) > 0 and json_dict["task_profile"][-1]["name"] == "IDLE":
        json_dict["task_profile"].pop()

    final_json[agent_token] = json_dict

    # if agent_token == 20:
    #     print(json_dict)

x = [i[0] for i in agent_data[16]["coords"]]
y = [i[1] for i in agent_data[16]["coords"]]
plt.scatter(x, y, c=range(len(x)))
plt.show()

with open('agents_data.pickle', 'wb') as f:
    pickle.dump(final_json, f)