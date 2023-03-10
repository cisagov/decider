from app.conf import conf_configs
import time


def messaged_timer(msg):
    # Decorator factory that makes this nice print-out for running long actions
    # ___________Building Technique Table
    # \_  15.0s_/
    def decorator(fn):
        def wrapper(*args, **kwargs):
            print(f"___________{msg}")
            t0 = time.time()
            result = fn(*args, **kwargs)
            elapsed = time.time() - t0
            print(f"\\_{elapsed:>6.1f}s_/")  # allows up to thousands to display, long enough
            return result

        return wrapper

    return decorator


def get_config_option_map():
    # gives config options from conf.py indexed by their names
    return {opt.__name__: opt for opt in conf_configs}


def option_selector(
    # set/list {'a', 'b'} or dict of option names to their objects: { 'a': obj, 'b': obj }
    option_map,
    # default selected option by key: 'a'
    default=None,
    # initial print, used in the form: "{initial_msg}: [a, b]"
    initial_msg="Available options",
    # prompt for choice, used in the form: "{prompt_msg} [{default}]: "
    prompt_msg="Which option to use",
    # print on incorrect pick, used in the form: "{cmdline_pick/pick} {invalid_msg} {option_list}. Exiting/Try again."
    invalid_msg="is NOT a valid option from",
    cmdline_pick=None,
):

    if isinstance(option_map, (set, list)):
        option_map = {o: o for o in option_map}

    option_list = list(option_map.keys())

    # command-line selection defined
    if cmdline_pick is not None:

        # valid -> return object picked
        if cmdline_pick in option_map:
            return option_map[cmdline_pick]

        # invalid -> raise exception with invalid choice message
        else:
            raise Exception(f"{cmdline_pick} {invalid_msg} {option_list}. Exiting.")

    # present user with opening message / options
    print(f"{initial_msg}: {option_list}\n")

    # loop until valid selection
    pick = None
    while pick is None:

        # no default, plain prompt
        if default is None:
            pick = input(f"{prompt_msg}: ")

        # default, prompt with value that is set on empty input
        else:
            pick = input(f"{prompt_msg} [{default}]: ")
            if pick.strip() == "":
                pick = default

        # check selection validity, prompt for retry on fail
        if pick not in option_map:
            print(f"{pick} {invalid_msg} {option_list}. Try again.")
            pick = None

    # return selected object
    return option_map[pick]


def app_config_selector(cmdline_config):
    return option_selector(
        get_config_option_map(),
        default="DefaultConfig",
        initial_msg="Available app/database configs",
        prompt_msg="Which config to use",
        invalid_msg="is NOT a valid config from",
        cmdline_pick=cmdline_config,
    )
