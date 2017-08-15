# FIXME: this module needs more operations instead of low-level directives
# FIXME: should not be part of stdlib
# FIXME: requires additional dependencies (sqlalchemy, _pgcatalog, psycopg2)

from contextlib import contextmanager, closing
import os
import warnings

from contextlib2 import ExitStack
from sqlalchemy import create_engine, exc as sa_exc
from sqlalchemy.engine.url import URL
from sqlalchemy.sql import text
from sqlalchemy.orm import sessionmaker
import sqlalchemy_pgcatalog as sc
import volatile

from remand import operation, Changed, Unchanged
from .. import proc
from ... import net


class PostgreSQL(object):
    def __init__(self,
                 remote_addr='/var/run/postgresql/.s.PGSQL.5432',
                 user='postgres',
                 database='postgres',
                 password=None,
                 ident='postgres',
                 echo=False):
        self.remote_addr = remote_addr
        self.user = user
        self.database = database
        self.password = password
        self.ident = ident
        self.echo = echo

    @contextmanager
    def manager(self):
        """Create a new postgres manager.

        Any operation done to a postgres database must be performed inside
        a manager. The manage will change the current `uid` for *all*
        operations to `postgres`; for this reason it is important to not
        perform any other operation while inside this contextmanager.

        Furthermore, establishing a connection requires that OpenBSD-style
        netcat is installed on the target system. Be aware that most
        debian-systems install a "traditional" netcat by default (package
        `netcat-traditional` instead of `netcat-openbsd`). Using traditional
        netcat will result in errors proclaiming unexpected closing of the
        socket.
        """
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
            yield Manager(engine)


def pg_valid(s):
    if not s.isalnum():
        raise ValueError('Invalid name (postgres): {!r}'.format(s))
    return s


class Manager(object):
    def __init__(self, engine):
        self.engine = engine
        self.sessionmaker = sessionmaker(bind=engine)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=sa_exc.SAWarning)
            sc.prepare(self.engine)

    @contextmanager
    def session(self, *args, **kwargs):
        with closing(self.sessionmaker(*args, **kwargs)) as session:
            yield session
            if session.is_active:
                session.commit()

    @operation()
    def create_database(self, name, owner):
        assert name.isalnum()
        assert owner.isalnum()

        # check if database exists
        qry = 'SELECT datname FROM pg_database'
        dbs = [row[0] for row in self.engine.execute(qry)]

        if name in dbs:
            return Unchanged('Database {} already exists'.format(name))

        sql = text(' '.join([
            'CREATE DATABASE ' + pg_valid(name), 'WITH OWNER ' +
            pg_valid(owner)
        ]))

        # runs outside transaction
        with self.session(autocommit=True) as sess:
            con = sess.connection()

            con.execute('COMMIT')
            con.execute(sql)

        return Changed(msg='Created database {}'.format(name))

    @operation()
    def create_role(self,
                    name,
                    password=None,
                    superuser=False,
                    createdb=False,
                    createrole=False,
                    inherit=True,
                    login=True,
                    connection_limit=-1):
        # FIXME: should update role if required
        with self.session() as sess:
            for role in sess.query(sc.Role):
                if role.rolname == name:
                    return Unchanged(msg='Role {} already exists'.format(name))

            sql = text(' '.join([
                'CREATE ROLE ' + pg_valid(name),
                'SUPERUSER' if superuser else 'NOSUPERUSER',
                'CREATEDB' if createdb else 'NOCREATEDB',
                'CREATEROLE' if createrole else 'NOCREATEROLE',
                'INHERIT' if inherit else 'NOINHERIT',
                'LOGIN' if login else 'NOLOGIN',
                'CONNECTION LIMIT :connection_limit',
                'PASSWORD :pw' if password is not None else 'NOPASSWORD',
            ]))

            sess.connection().execute(
                sql, name=name, connection_limit=connection_limit, pw=password)

        return Changed(msg='Created role {}'.format(name))
