from contextlib import contextmanager
import os

from contextlib2 import ExitStack
from sqlalchemy import create_engine
from sqlalchemy.engine.url import URL
from sqlalchemy.sql.expression import text
import volatile

from . import proc
from ..operation import operation
from .. import net


class AbortTransaction(Exception):
    pass


class PostgreSQL(object):
    def __init__(self,
                 remote_addr='/var/run/postgresql/.s.PGSQL.5432',
                 user='postgres',
                 database='postgres',
                 password=None,
                 ident='postgres',
                 echo=True):
        self.remote_addr = remote_addr
        self.user = user
        self.database = database
        self.password = password
        self.ident = ident
        self.echo = echo

    def abort_transaction(self):
        raise AbortTransaction()

    @contextmanager
    def db_engine(self):
        with ExitStack() as stack:
            dtmp = stack.enter_context(volatile.dir())
            sock_addr = os.path.join(dtmp, '.s.PGSQL.5432')

            if self.ident:
                stack.enter_context(proc.sudo(self.ident))

            stack.enter_context(net.local_forward(self.remote_addr, sock_addr))
            url = URL(
                drivername='postgresql',
                username=self.user,
                password=self.password,
                database=self.database,
                query={'host': dtmp})

            engine = create_engine(url, echo=self.echo)
            yield engine

    @contextmanager
    def transaction(self):
        with self.db_engine() as engine:
            con = engine.connect()
            trans = con.begin()

            try:
                yield con
            except AbortTransaction:
                trans.close()
            except Exception:
                trans.close()
                raise
            else:
                trans.commit()


# FIXME: maybe this needs a full blown reflection/support for the postgres
# schema
def get_role(con, name):
    res = con.execute(text('SELECT * FROM pg_roles WHERE rolname = :name'),
                      name=name)

    return res
