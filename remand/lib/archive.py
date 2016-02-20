from . import proc, fs
from remand import remote
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
    # FIXME: should check if remote_dest is an existing directory or create it
    # FIXME: add a way to extract arbitrary archives locally and send?
    if fn.endswith('.zip'):

        with fs.remote_tmpdir() as tmp:
            archive_name = remote.path.join(tmp, 'archive.zip')

            fs.upload_file(fn, archive_name)
            proc.run(['unzip', archive_name], cwd=remote_dest)
    else:
        # tar
        for ext, flag in TAR_DECOMP_FLAGS.items():
            if fn.endswith(ext):
                decomp_flag = flag
                break
        else:
            raise ValueError(
                'Unsupported archive type (determined by file ending): {}'
                .format(fn))

        args = ['tar', decomp_flag + 'xf', '-', '-C', remote_dest]

        with open(fn, 'rb') as inp:
            proc.run(args, input=inp)

    return Changed(msg='Extracted archive {} to {}'.format(fn, remote_dest))
