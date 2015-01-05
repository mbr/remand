from pathlib import Path
import zipfile

from six.moves import cStringIO as StringIO


def zipup_package(pkg_path, outfile=None, compression=zipfile.ZIP_DEFLATED):
    if outfile is None:
        out = StringIO()
    else:
        out = outfile

    pkg_path = Path(pkg_path)

    with zipfile.ZipFile(out, mode='w', compression=compression) as z:
        for pyfile in pkg_path.glob('**/*.py'):
            relname = pyfile.relative_to(pkg_path)
            z.write(str(pyfile), str(relname))

    if outfile is None:
        return out.getvalue()
