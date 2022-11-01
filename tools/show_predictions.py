#! /usr/bin/env python

from argparse import ArgumentParser
from copy import copy, deepcopy
from curses.ascii import SO
from pathlib import Path
from typing import Optional

from ardi.dataset import Dataset
from ardi.dataset.zucker import ZuckerDataset
from ardi.prediction import Predictor, LinearPredictor, VelocityCalc, SocialVAEPredictor

from matplotlib import pyplot as plt

class PredictionVisualizer:
    def __init__(self, data: Dataset, obs_horizon: int, pred_horizon: int, predictor: Predictor) -> None:
        self._data = data
        self._obs_horizon = obs_horizon
        self._pred_horizon = pred_horizon
        self._predictor = predictor
        
    def predict(self, time_idx: int, agent_idx: int) -> None:
        if len(self._data.times) - self._obs_horizon <= time_idx + self._pred_horizon:
            raise ValueError(f"Dataset does not have enough timesteps to predict @ " + 
                             f"t_i={time_idx} valid range {self._obs_horizon}-" + 
                             f"{len(self._data.times) - self._pred_horizon}")

        ego_obs = copy(self._data.agents[agent_idx])
        ego_obs.positions = self._data.agents[agent_idx].positions[time_idx - self._obs_horizon:time_idx]

        neighbors_obs = []
        neighbor_keys = [x for x in self._data.agents.keys() if x != agent_idx]
        for nk in neighbor_keys:
            n = copy(self._data.agents[nk])
            n.positions = self._data.agents[nk].positions[time_idx - self._obs_horizon: time_idx]  
            neighbors_obs.append(n)

        preds = self._predictor.predict(ego_obs, neighbors_obs)

        ego_truth = copy(self._data.agents[agent_idx])
        ego_truth.positions = self._data.agents[agent_idx].positions[time_idx:time_idx + self._pred_horizon]

        ade, fde = Predictor.ade_fde(ego_truth.positions, preds)

        neighbors_truth = []
        neighbor_keys = [x for x in self._data.agents.keys() if x != agent_idx]
        for nk in neighbor_keys:
            n = copy(self._data.agents[nk])
            n.positions = self._data.agents[nk].positions[time_idx:time_idx + self._pred_horizon]  
            neighbors_truth.append(n)

        plt.title(f"{str(type(self._predictor)).split('.')[-1][:-2]}\n(ADE: {ade}, FDE: {fde})")
        self._predictor.plot(
            ego_obs.positions,
            [x.positions for x in neighbors_obs],
            ego_truth.positions,
            [x.positions for x in neighbors_truth],
            preds
        )
        plt.show()


    @staticmethod
    def get_predictor(mode: type[Predictor], obs: int, pred: int, ob_radius: float,
                      n_preds: int, vel_calc: VelocityCalc, model_fn: Optional[str]=None) -> Predictor:

        raise ValueError(f"mode: {mode} must be one of linear or socialvae")

    def get_predictor_mode(mode: str):
        if mode == "linear":
            return LinearPredictor
        if mode == "socialvae":
            return SocialVAEPredictor
            
        raise ValueError(f"mode: {mode} must be one of linear or socialvae")
    @staticmethod
    def get_velocity_calc(calc: str) -> VelocityCalc:
        if calc == "LD":
            return VelocityCalc.LAST_DISPLACEMENT
        if calc == "AD":
            return VelocityCalc.AVERAGE_DISPLACEMENT
        if calc == "LT":
            return VelocityCalc.LAST_GROUND_TRUTH
        if calc == "AT":
            return VelocityCalc.AVERAGE_GROUND_TRUTH
        
        raise ValueError(f"calc: {calc} must be one of LD or AD or LT or AT")
        
def main():
    parser = ArgumentParser(description="Generate trajectory visualizations for an agent in a given scene")

    parser.add_argument("input_file", type=Path, help="File to load trajectories from")
    parser.add_argument("agent_idx", type=int, help="Agent index to predict for")
    parser.add_argument("time_idx", type=int, help="Time index to predict at")
    parser.add_argument("mode", type=str, choices=["linear", "socialvae"], help="Prediction algorithm to use")

    parser.add_argument("--obs", type=int, default=5, help="Number of frames to use in observation")
    parser.add_argument("--pred", type=int, default=8, help="Number of frames to use in prediction")
    parser.add_argument("--frameskip", type=int, default=1, help="Number of frames to skip between predictions")
    parser.add_argument("--radius", type=int, default=4, help="Observation radius (socialvae)")
    parser.add_argument("--n_preds", type=int, default=5, help="Number of predictions to use (socialvae)")
    parser.add_argument("--model", type=str, default=None, help="Model checkpoint to use (socialvae)")
    parser.add_argument(
        "--vcalc", type=lambda x: PredictionVisualizer.get_velocity_calc(x), default="LD",
        choices=["LD", "AD", "LT", "AT"],
        help="Method to calculate the velocity given to the model with. " + 
        "Choices are last displacement, average displacement over the last " + 
        "'obs' frames, last ground truth, and average ground truth over the same window."
    )

    args = parser.parse_args()

    
    pred = None
    if args.mode == "linear":
        pred = LinearPredictor(args.pred, args.vcalc)
    elif args.mode == "socialvae":
        pred = SocialVAEPredictor(args.model, args.radius, args.n_preds, args.pred, args.vcalc)
                                            
    data = ZuckerDataset(args.input_file)
    data.frameskip(args.frameskip)

    if args.agent_idx not in data.agents.keys():
        print(f"{args.agent_idx} not in given trajectory ({list(data.agents.keys())})")

    PredictionVisualizer(data, args.obs, args.pred, pred).predict(args.time_idx, args.agent_idx)

if __name__ == "__main__":
    main()