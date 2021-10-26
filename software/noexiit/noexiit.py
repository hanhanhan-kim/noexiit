from pathlib import Path
from pprint import pprint

import click
import yaml

from noexiit.utils import parse_readme_for_docstrings, docstring_parameter

docstrings = parse_readme_for_docstrings("../README.md")
pass_config = click.make_pass_decorator(dict)

# TODO: add a DEFAULT_CONFIG ?

def load_config(fname):
    if fname == None:
        fname = "config.yaml"

    if Path(fname).exists():
        with open(fname) as f:
            config = yaml.safe_load(f) 
    else:
        config = dict()
        exit("You did not pass in a .yaml file! Please pass in a .yaml file.")

    return config

@click.group()
@click.option('--config', type=click.Path(exists=True, dir_okay=False),
              help='The config file to use instead of the default `config.yaml`.')
@click.pass_context
def cli(ctx, config):
    ctx.obj = load_config(config)

@cli.command()
@pass_config
@docstring_parameter(docstrings["print-config"])
def print_config(config):
    """
    {0}
    """
    print(docstrings[0])
    print("")
    pprint(config)
    print("")

@cli.command()
@pass_config
@docstring_parameter(docstrings["calibrate"])
def calibrate(config):
    """
    {0}
    """
    from noexiit import calib
    click.echo("\nCalibrating ...")
    calib.main(config)

@cli.command()
@pass_config
@docstring_parameter(docstrings["plot-pid-live"])
def plot_pid_live(config):
    """
    {0}
    """
    from noexiit import live_plot_PID
    click.echo("\nPlotting real-time PID data ...")
    live_plot_PID.main(config)

@cli.command()
@pass_config
@docstring_parameter(docstrings["expt-pt-to-pt"][0], 
                     docstrings["expt-pt-to-pt"][1])
def expt_pt_to_pt(config):
    """
    {0}
    \b
    {1}
    """
    from noexiit import pt_to_pt_stream_expt
    click.echo("\nRunning 'point to point' (open-loop) experiment ...")
    pt_to_pt_stream_expt.main(config)

# TODO: Make an open-loop experiment file and command with odour delivery + servo stim

@cli.command()
@pass_config
@docstring_parameter(docstrings["expt-still-robot"])
def expt_still_robot(config):
    """
    {0}
    """
    from noexiit import c_loop_still_robot_expt
    click.echo("\nRunning 'still robot' (closed-loop) experiment ...")
    c_loop_still_robot_expt.main(config)

@cli.command()
@pass_config
@docstring_parameter(docstrings["sniff-and-puff"])
def sniff_and_puff(config):
    """
    {0}
    """
    from noexiit import sniff_puff_and_stream
    click.echo("\nAcquiring PID data and controlling valves ...")
    sniff_puff_and_stream.main(config)


if __name__ == "__main__":
    cli()