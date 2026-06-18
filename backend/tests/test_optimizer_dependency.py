import optuna


def test_optuna_tpe_and_median_pruner_are_available() -> None:
    sampler = optuna.samplers.TPESampler(seed=7)
    pruner = optuna.pruners.MedianPruner()

    assert sampler.__class__.__name__ == "TPESampler"
    assert pruner.__class__.__name__ == "MedianPruner"
