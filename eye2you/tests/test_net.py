# pylint: disable=redefined-outer-name
import os
import pathlib

import pytest
import torch
import yaml

import eye2you
from eye2you import factory
from eye2you.meter_functions import TotalAccuracyMeter

LOCAL_DIR = pathlib.Path(os.path.dirname(os.path.realpath(__file__)))


def test_net_setup():
    config = yaml.full_load('''
    device: cpu
    model_name: inception_v3_xs
    model_kwargs:
    criterion_name: BCEWithLogitsLoss
    criterion_kwargs:
    optimizer_name: Adam
    optimizer_kwargs:
    use_scheduler: True
    scheduler_kwargs:
        step_size: 5
    performance_meters:
    ''')

    net = eye2you.net.Network(**config)
    assert net is not None
    assert net.model is not None
    assert net.optimizer is not None
    assert net.criterion is not None
    assert net.scheduler is not None

    config = yaml.full_load('''
    device: cpu
    model_name: inception_v3_xs
    model_kwargs:
        num_classes: 7
    criterion_name: BCEWithLogitsLoss
    criterion_kwargs:
    optimizer_name: Adam
    optimizer_kwargs:
        lr: 0.001
    use_scheduler: True
    scheduler_kwargs:
        step_size: 10
        gamma: 0.25
    performance_meters:
        - mf.TotalAccuracyMeter()
        - mf.SingleAccuracyMeter(5)
    ''')

    net = eye2you.net.Network(**config)
    assert net is not None


def test_network_warning_false_names():
    config = yaml.full_load('''
    device: cpu
    model_name: 
    model_kwargs:
    criterion_name: 
    criterion_kwargs:
    optimizer_name: 
    optimizer_kwargs:
    use_scheduler: False
    scheduler_kwargs:
    performance_meters:
    ''')

    with pytest.warns(Warning):
        _ = eye2you.net.Network(**config)

    config = yaml.full_load('''
    device: cpu
    model_name: inception_v3_xs
    model_kwargs:
    criterion_name: test
    criterion_kwargs:
    optimizer_name: test
    optimizer_kwargs:
    use_scheduler: False
    scheduler_kwargs:
    performance_meters:
    ''')

    with pytest.warns(Warning):
        _ = eye2you.net.Network(**config)

    config = yaml.full_load('''
    device: cpu
    model_name: inception_v3_xs
    model_kwargs:
    criterion_name: L1Loss
    criterion_kwargs:
    optimizer_name: test
    optimizer_kwargs:
    use_scheduler: False
    scheduler_kwargs:
    performance_meters:
    ''')

    with pytest.warns(Warning):
        _ = eye2you.net.Network(**config)

    config = yaml.full_load('''
    device: cpu
    model_name: inception_v3_xs
    model_kwargs:
    criterion_name: L1Loss
    criterion_kwargs:
    optimizer_name: Adam
    optimizer_kwargs:
    use_scheduler: True
    scheduler_kwargs:
    performance_meters:
    ''')

    with pytest.raises(ValueError):
        _ = eye2you.net.Network(**config)


def test_network_train():
    config = factory.config_from_yaml(LOCAL_DIR / 'data/example.yaml')
    config['dataset']['csv'] = str(LOCAL_DIR / config['dataset']['csv'])
    config['dataset']['root'] = str(LOCAL_DIR / config['dataset']['root'])
    config['dataset']['validation']['csv'] = config['dataset']['csv']
    config['dataset']['validation']['root'] = config['dataset']['root']

    dataprep = eye2you.datasets.DataPreparation(**config['data_preparation'])
    train_data, _ = factory.data_from_config(config['dataset'])
    train_data.preparation = dataprep
    train_loader = factory.get_loader(config['training'], train_data)
    net = eye2you.net.Network(**config['net'])
    assert net is not None

    net.train(train_loader)

    config['net']['model_name'] = 'inception_v3_s'
    net = eye2you.net.Network(**config['net'])
    assert net is not None

    net.train(train_loader)


def test_network_train_value_error():
    config = factory.config_from_yaml(LOCAL_DIR / 'data/example.yaml')
    config['dataset']['csv'] = str(LOCAL_DIR / config['dataset']['csv'])
    config['dataset']['root'] = str(LOCAL_DIR / config['dataset']['root'])
    config['dataset']['validation']['csv'] = config['dataset']['csv']
    config['dataset']['validation']['root'] = config['dataset']['root']

    dataprep = eye2you.datasets.DataPreparation(**config['data_preparation'])
    train_data, _ = factory.data_from_config(config['dataset'])
    train_data.preparation = dataprep
    train_loader = factory.get_loader(config['training'], train_data)
    net = eye2you.net.Network(**config['net'])
    optimizer = net.optimizer
    net.optimizer = None
    assert net is not None

    with pytest.raises(ValueError):
        net.train(train_loader)

    net.optimizer = optimizer
    net.criterion = None
    with pytest.raises(ValueError):
        net.train(train_loader)


def test_network_validate():
    config = factory.config_from_yaml(LOCAL_DIR / 'data/example.yaml')
    config['dataset']['csv'] = str(LOCAL_DIR / config['dataset']['csv'])
    config['dataset']['root'] = str(LOCAL_DIR / config['dataset']['root'])
    config['dataset']['validation']['csv'] = config['dataset']['csv']
    config['dataset']['validation']['root'] = config['dataset']['root']

    dataprep = eye2you.datasets.DataPreparation(**config['data_preparation'])

    _, validate_data = factory.data_from_config(config['dataset'])

    validate_data.preparation = dataprep

    validate_loader = factory.get_loader(config['validation'], validate_data)

    net = eye2you.net.Network(**config['net'])

    net.validate(validate_loader)


def test_from_and_to_state_dict():
    config = factory.config_from_yaml(LOCAL_DIR / 'data/example.yaml')
    net1 = eye2you.net.Network(**config['net'])

    net_before = str(net1)

    state_dict = net1.get_state_dict()
    state_dict['performance_meters'] = [
        p if not isinstance(p, str) else eval(p) for p in state_dict['performance_meters']
    ]

    net2 = eye2you.net.Network.from_state_dict(state_dict)

    net_after = str(net2)
    assert net_before == net_after
    assert compare_network_weights(net1, net2)


def test_load_state_dict():
    config = factory.config_from_yaml(LOCAL_DIR / 'data/example.yaml')
    net1 = eye2you.net.Network(**config['net'])
    state_dict = net1.get_state_dict()

    net2 = eye2you.net.Network(**config['net'])
    net2.load_state_dict(state_dict)

    assert compare_network_weights(net1, net2)


def compare_network_weights(net1, net2):
    par1 = list(net1.model.parameters())
    par2 = list(net2.model.parameters())

    for p1, p2 in zip(par1, par2):
        assert p1.allclose(p2)

    pg1 = net1.optimizer.param_groups
    pg2 = net2.optimizer.param_groups

    for par1, par2 in zip(pg1, pg2):
        assert sorted(par1.keys()) == sorted(par2.keys())
        for key in par1.keys():
            if isinstance(par1[key], (list, tuple)):
                for p1, p2 in zip(par1[key], par2[key]):
                    if hasattr(p1, 'allclose'):
                        assert p1.allclose(p2)
                    else:
                        assert p1 == p2
            elif isinstance(par1[key], torch.nn.parameter.Parameter):
                assert par1[key].allclose(par2[key])
            else:
                assert par1[key] == par2[key]

    return True


def test_network_print():
    pass
