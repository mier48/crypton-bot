import optuna
from typing import Callable, Dict, Any

class ParameterOptimizer:
    """
    Optimize strategy parameters using Bayesian optimization (Optuna).
    """
    def __init__(self, n_trials: int = 50):
        self.n_trials = n_trials

    def optimize(self, param_space: Dict[str, Any], objective_fn: Callable[[Dict[str, Any]], float]) -> Dict[str, Any]:
        """
        param_space: {'param_name': (low, high) | [choices]}
        objective_fn: function receiving param dict, returns metric to maximize.
        """
        def objective(trial):
            params = {}
            for name, space in param_space.items():
                if isinstance(space, (list, tuple)) and len(space) == 2 and all(isinstance(x, (int, float)) for x in space):
                    low, high = space
                    if isinstance(low, int) and isinstance(high, int):
                        params[name] = trial.suggest_int(name, low, high)
                    else:
                        params[name] = trial.suggest_float(name, low, high)
                elif isinstance(space, list):
                    params[name] = trial.suggest_categorical(name, space)
                else:
                    raise ValueError(f"Invalid space for {name}: {space}")
            return objective_fn(params)

        study = optuna.create_study(direction="maximize")
        study.optimize(objective, n_trials=self.n_trials)
        return study.best_params
