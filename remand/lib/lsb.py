from remand.lib import proc
from remand.lib import memoize


@memoize
def _get_lsb_info():
    stdout, stderr = proc.run(['lsb_release', '--all', '--short'])
    lines = stdout.splitlines()
    return {
        'dist_id': lines[0],
        'desc': lines[1],
        'release': lines[2],
        'codename': lines[3],
    }


def info_info():
    return _get_lsb_info()


def info_dist_id():
    return _get_lsb_info()['dist_id']


def info_desc():
    return _get_lsb_info()['desc']


def info_release():
    return _get_lsb_info()['release']


def info_codename():
    return _get_lsb_info()['codename']
