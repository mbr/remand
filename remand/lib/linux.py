from remand.operation import operation, Changed, Unchanged
from remand import remote, info
from remand.lib import proc, fs


@operation()
def enable_module(module_name, load=True, modules_file='/etc/modules'):
    mods = info['linux.modules']

    c = False

    # load module if not loaded
    if load and module_name not in mods:
        proc.run(['modprobe', module_name])
        c = True

    # ensure module is found in modules_files
    with fs.edit(modules_file) as mf:
        mf.insert_line(module_name)

    c |= mf.changed

    if c:
        return Changed(msg='Kernel module {}, enabled in {}'.format(
            module_name, modules_file))

    return Unchanged(msg='Kernel module {} already enabled in {}'.format(
        module_name, modules_file))


def info_modules():
    mods = {}
    with remote.file('/proc/modules') as pm:
        for line in pm:
            name, size, loaded, dependencies, state, offset = line.split()
            deps = dependencies.strip(',').split(
                ',') if dependencies != '-' else []
            mods[name] = {
                'name': name,
                'size': int(size),
                'loaded': int(loaded),
                'dependencies': deps,
                'state': state,
                'offset': int(offset, 16),
            }

    return mods
