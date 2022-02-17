#!/usr/bin/env python3
import rclpy

import subprocess
import numpy as np
import pickle

from pathlib import Path

from dlp.dataset import Dataset
from dlp.visualizer import Visualizer as DlpVisualizer

from std_msgs.msg import Int16MultiArray
from parksim.srv import OccupancySrv
from parksim.base_node import MPClabNode
from parksim.pytypes import VehicleState, NodeParamTemplate
from parksim.route_planner.graph import WaypointsGraph

class SimulatorNodeParams(NodeParamTemplate):
    """
    template that stores all parameters needed for the node as well as default values
    """
    def __init__(self):
        self.dlp_path = '/dlp-dataset/data/DJI_0012'
        self.timer_period = 0.1
        self.random_seed = 0

        self.spawn_entering = 3
        self.spawn_exiting = 3
        self.spawn_interval_min = 2 # (s)
        self.spawn_interval_mean = 5 # (s)

        self.spots_data_path = ''

class SimulatorNode(MPClabNode):
    """
    Node class for simulation
    """
    def __init__(self):
        super().__init__('simulator')
        self.get_logger().info('Initializing Simulator Node')
        namespace = self.get_namespace()

        param_template = SimulatorNodeParams()
        self.autodeclare_parameters(param_template, namespace)
        self.autoload_parameters(param_template, namespace)

        np.random.seed(self.random_seed)

        # DLP
        home_path = str(Path.home())
        self.get_logger().info('Loading Dataset...')
        ds = Dataset()
        ds.load(home_path + self.dlp_path)
        self.dlpvis = DlpVisualizer(ds)

        # Parking Spaces
        self.parking_spaces, self.occupied = self._gen_occupancy()
        with open(home_path + self.spots_data_path, 'rb') as f:
            data = pickle.load(f)
            self.anchor_points = data['anchor_points']

        # Spawning
        self.spawn_entering_time = sorted(np.random.exponential(self.spawn_interval_mean, self.spawn_entering))
        for i in range(self.spawn_entering):
            self.spawn_entering_time[i] += i * self.spawn_interval_min

        self.spawn_exiting_time = sorted(np.random.exponential(self.spawn_interval_mean, self.spawn_exiting))

        self.start_time = self.get_ros_time()

        self.vehicles = []
        self.num_vehicles = 0

        self.timer = self.create_timer(self.timer_period, self.timer_callback)

        self.occupancy_pub = self.create_publisher(Int16MultiArray, 'occupancy', 10)

        self.occupancy_srv = self.create_service(OccupancySrv, 'occupancy', self.occupancy_srv_callback)

    def occupancy_srv_callback(self, request, response):
        vehicle_id = request.vehicle_id
        idx = request.idx
        new_value = request.new_value

        self.occupied[idx] = new_value

        response.status = True

        self.get_logger().info("Vehicle %d changed the occupancy at %d to be %r" % (vehicle_id, idx, new_value))
        
        return response

    def _gen_occupancy(self):
        # get parking spaces
        arr = self.dlpvis.parking_spaces.to_numpy()
        # array of tuples of x-y coords of centers of spots
        parking_spaces = np.array([[round((arr[i][2] + arr[i][4]) / 2, 3), round((arr[i][3] + arr[i][9]) / 2, 3)] for i in range(len(arr))])

        scene = self.dlpvis.dataset.get('scene', self.dlpvis.dataset.list_scenes()[0])

        # figure out which parking spaces are occupied
        car_coords = [self.dlpvis.dataset.get('obstacle', o)['coords'] for o in scene['obstacles']]
        # 1D array of booleans — are the centers of any of the cars contained within this spot's boundaries?
        occupied = [any([c[0] > arr[i][2] and c[0] < arr[i][4] and c[1] < arr[i][3] and c[1] > arr[i][9] for c in car_coords]) for i in range(len(arr))]

        return parking_spaces, list(map(int, occupied))

    def add_vehicle(self, spot_index: int):

        self.num_vehicles += 1

        self.vehicles.append(
            subprocess.Popen(["ros2", "launch", "parksim", "vehicle.launch.py", "vehicle_id:=%d" % self.num_vehicles, "spot_index:=%d" % spot_index])
        )

        self.get_logger().info("A vehicle with id = %d is added with spot_index = %d" % (self.num_vehicles, spot_index))

    def shutdown_vehicles(self):
        for vehicle in self.vehicles:
            vehicle.terminate()

        print("Vehicle nodes are down")

    def timer_callback(self):
        
        current_time = self.get_ros_time()

        if self.spawn_entering_time and current_time - self.start_time > self.spawn_entering_time[0]:
            self.add_vehicle(np.random.choice(self.anchor_points)) # pick from the anchor points at random
            self.spawn_entering_time.pop(0)

        if self.spawn_exiting_time and current_time - self.start_time > self.spawn_exiting_time[0]:
            empty_spots = [i for i in range(len(self.occupied)) if not self.occupied[i]]
            chosen_spot = np.random.choice(empty_spots)
            self.add_vehicle(-1 * chosen_spot)
            self.occupied[chosen_spot] = True
            self.spawn_exiting_time.pop(0)

        occupancy_msg = Int16MultiArray()
        occupancy_msg.data = self.occupied
        self.occupancy_pub.publish(occupancy_msg)


def main(args=None):
    rclpy.init(args=args)

    simulator = SimulatorNode()

    try:
        rclpy.spin(simulator)
    except KeyboardInterrupt:
        print('Simulation is terminated')
    finally:
        simulator.shutdown_vehicles()
        simulator.destroy_node()
        print('Simulation stopped cleanly')

        rclpy.shutdown()

if __name__ == "__main__":
    main()