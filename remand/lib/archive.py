from . import proc
from remand.operation import Changed

TAR_DECOMP_FLAGS = {
    '.tar': '',
    '.tar.gz': 'z',
    '.tgz': 'z',
    '.tar.Z': 'Z',
    '.tar.bz2': 'j',
    '.tar.xz': 'J',
}


def extract(fn, remote_dest):
    # FIXME: add a way to extract arbitrary archives locally and send?
    for ext, flag in TAR_DECOMP_FLAGS.items():
        if fn.endswith(ext):
            decomp_flag = flag
            break
    else:
        raise ValueError(
            'Unsupported archive type (determined by file ending)')

    args = ['tar', decomp_flag + 'xf', '-', '-C', remote_dest]

    with open(fn, 'rb') as inp:
        proc.run(args, input=inp)

    return Changed(msg='Extracted archive {} to {}'.format(fn, remote_dest))
