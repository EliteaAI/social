"""Executable harness for the folder-permission code (#6524).

The point of this file is that the tests below it run the *real* models and the *real*
RPC bodies, not a copy of their logic: the security of the feature lives in the SQL those
bodies emit, and a reimplementation in the test file cannot verify SQL.

Fidelity notes:
- Each project gets its own attached in-memory SQLite database and the session is opened
  with `schema_translate_map={'tenant': 'p_<id>'}` - the same mechanism the real db layer
  uses to point a tenant-schema model at one project's schema.
- `flask` is stubbed rather than installed so request-context presence (which drives the
  per-request memo and `auth.current_user()`) is deterministic.
- Postgres-only column types are compiled down for SQLite; nothing else about the models
  is altered.

Set SOCIAL_TEST_PG_DSN to run the same suite against a real Postgres instead.
"""

import contextlib
import importlib.util
import os
import pathlib
import queue
import sys
import types

from sqlalchemy import Column, Integer, String, create_engine, event
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool


PLUGIN_ROOT = pathlib.Path(__file__).resolve().parents[2]
SHARED_TOOLS = PLUGIN_ROOT.parent / 'shared' / 'tools' / 'serialize.py'
TENANT_SCHEMA = 'tenant'

_COMPILED = False


def _compile_pg_types_for_sqlite():
    """JSONB/UUID have no SQLite compiler; give them one instead of editing the models."""
    global _COMPILED  # pylint: disable=W0603
    if _COMPILED:
        return
    @compiles(JSONB, 'sqlite')
    def _jsonb(type_, compiler, **kw):  # pylint: disable=W0612
        return 'JSON'

    @compiles(UUID, 'sqlite')
    def _uuid(type_, compiler, **kw):  # pylint: disable=W0612
        return 'CHAR(36)'
    _COMPILED = True


def _load_serialize():
    spec = importlib.util.spec_from_file_location('_social_test_serialize', SHARED_TOOLS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.serialize


# --- stub: flask -----------------------------------------------------------

class _FlaskStub(types.ModuleType):
    """Only `has_request_context()` and `g` are touched by the code under test."""

    def __init__(self):
        super().__init__('flask')
        self._in_request = False
        self.g = types.SimpleNamespace()

    def has_request_context(self):
        return self._in_request

    @contextlib.contextmanager
    def request_context(self):
        prev_flag, prev_g = self._in_request, self.g
        self._in_request, self.g = True, types.SimpleNamespace()
        try:
            yield self.g
        finally:
            self._in_request, self.g = prev_flag, prev_g


# --- stub: pylon runtime ---------------------------------------------------

def _pylon_stub():
    log = types.SimpleNamespace(
        info=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        error=lambda *a, **k: None,
        debug=lambda *a, **k: None,
        exception=lambda *a, **k: None,
        critical=lambda *a, **k: None,
    )

    def rpc(*_a, **_k):
        def deco(func):
            return func
        return deco

    def sio_or_event(*_a, **_k):
        def deco(func):
            return func
        return deco

    web = types.SimpleNamespace(rpc=rpc, event=sio_or_event, method=sio_or_event, sio=sio_or_event)
    pylon = types.ModuleType('pylon')
    core = types.ModuleType('pylon.core')
    tools = types.ModuleType('pylon.core.tools')
    tools.log = log
    tools.web = web
    sys.modules['pylon'] = pylon
    sys.modules['pylon.core'] = core
    sys.modules['pylon.core.tools'] = tools


# --- fake RPC/event bus ----------------------------------------------------

class FakeRpcManager:
    """Unregistered RPC names raise queue.Empty, exactly like an absent plugin."""

    def __init__(self):
        self.registry = {}
        self.calls = []

    def timeout(self, _seconds):
        return self

    @property
    def call(self):
        return self

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        registry = self.__dict__['registry']
        if name not in registry:
            raise queue.Empty(name)
        impl = registry[name]

        def _invoke(**kwargs):
            self.__dict__['calls'].append((name, kwargs))
            if isinstance(impl, Exception):
                raise impl
            if callable(impl):
                return impl(**kwargs)
            return impl
        return _invoke


class FakeEventManager:
    def __init__(self):
        self.fired = []

    def fire_event(self, name, payload):
        self.fired.append((name, payload))


class FakeContext:
    def __init__(self):
        self.rpc_manager = FakeRpcManager()
        self.event_manager = FakeEventManager()


# --- environment -----------------------------------------------------------

class Env:
    """Everything a test needs: the composed module, the db, and context controls."""

    def __init__(self, projects, flask_stub, engine, session_factory, models, module, context):
        self.projects = list(projects)
        self.flask = flask_stub
        self.engine = engine
        self._session_factory = session_factory
        self.models = models
        self.module = module
        self.context = context
        self.statements = []
        self.current_user_id = None

    # -- db
    @contextlib.contextmanager
    def session(self, project_id):
        session = self._session_factory(
            bind=self.engine.execution_options(
                schema_translate_map={TENANT_SCHEMA: f'p_{project_id}'}
            )
        )
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # -- request context / identity
    @contextlib.contextmanager
    def request(self, user_id=None):
        prev = self.current_user_id
        self.current_user_id = user_id
        try:
            with self.flask.request_context():
                yield
        finally:
            self.current_user_id = prev

    @contextlib.contextmanager
    def user(self, user_id):
        """Identity without a request context (background/runtime callers)."""
        prev = self.current_user_id
        self.current_user_id = user_id
        try:
            yield
        finally:
            self.current_user_id = prev

    # -- rpc bus
    def register_rpc(self, name, impl):
        self.context.rpc_manager.registry[name] = impl

    def unregister_rpc(self, name):
        self.context.rpc_manager.registry.pop(name, None)

    def team_project(self, is_team=True):
        self.register_rpc('projects_is_team_project', lambda **kw: is_team)

    def members(self, *user_ids):
        self.register_rpc('admin_get_users_ids_in_project', lambda **kw: list(user_ids))

    # -- query counting
    @contextlib.contextmanager
    def count_queries(self):
        start = len(self.statements)
        recorded = []
        yield recorded
        recorded.extend(self.statements[start:])

    def truncate(self):
        for project_id in self.projects:
            with self.session(project_id) as s:
                s.query(self.models.FolderAccessOverride).delete()
                s.query(self.models.FolderItem).delete()
                s.query(self.models.EntityFolder).delete()
                s.query(self.models.EntityRow).delete()


_ENV = None


def get_env(projects=(1, 2)):
    """Process-wide singleton: the models bind to one declarative Base, so a second
    environment in the same interpreter would create tables nothing is mapped to."""
    global _ENV  # pylint: disable=W0603
    if _ENV is None:
        _ENV = build_env(projects)
    return _ENV


def build_env(projects=(1, 2)):
    projects = list(projects)
    dsn = os.environ.get('SOCIAL_TEST_PG_DSN')
    flask_stub = _FlaskStub()
    sys.modules['flask'] = flask_stub
    _pylon_stub()

    if dsn:
        engine = create_engine(dsn, future=True)
    else:
        _compile_pg_types_for_sqlite()
        engine = create_engine(
            'sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False}
        )

        @event.listens_for(engine, 'connect')
        def _attach(dbapi_conn, _record):  # pylint: disable=W0612
            cur = dbapi_conn.cursor()
            for project_id in projects:
                cur.execute(f'ATTACH DATABASE \':memory:\' AS "p_{project_id}"')
            cur.close()

    base = declarative_base()
    session_factory = sessionmaker(future=True, expire_on_commit=False)
    env_holder = {}

    # -- tools stub -------------------------------------------------------
    class _AbstractBaseMixin:
        def to_json(self, exclude_fields=None):
            exclude_fields = set(exclude_fields or ())
            return {
                c.name: getattr(self, c.name)
                for c in self.__table__.columns if c.name not in exclude_fields
            }

    def _get_session(project_id=None, **_kw):
        return env_holder['env'].session(project_id)

    def _current_user():
        env = env_holder['env']
        if not env.flask.has_request_context():
            raise RuntimeError('Working outside of request context')
        if env.current_user_id is None:
            return {}
        return {'id': env.current_user_id, 'name': f'user{env.current_user_id}'}

    tools_pkg = types.ModuleType('tools')
    tools_pkg.__path__ = []
    tools_pkg.db = types.SimpleNamespace(Base=base, get_session=_get_session, engine=engine)
    tools_pkg.db_tools = types.SimpleNamespace(AbstractBaseMixin=_AbstractBaseMixin)
    tools_pkg.config = types.SimpleNamespace(
        POSTGRES_TENANT_SCHEMA=TENANT_SCHEMA,
        ADMINISTRATION_MODE='administration',
        DEFAULT_MODE='default',
    )
    tools_pkg.auth = types.SimpleNamespace(
        current_user=_current_user,
        decorators=types.SimpleNamespace(check_api=lambda *a, **k: (lambda f: f)),
        resolve_permissions=lambda **kw: set(),
    )
    tools_pkg.serialize = _load_serialize()
    tools_pkg.rpc_tools = types.SimpleNamespace(
        RpcMixin=type('RpcMixin', (), {'rpc': None}),
        EventManagerMixin=type('EventManagerMixin', (), {}),
    )
    tools_pkg.api_tools = types.SimpleNamespace()
    tools_pkg.this = types.SimpleNamespace()
    tools_pkg.register_openapi = lambda *a, **k: (lambda f: f)
    sys.modules['tools'] = tools_pkg

    # -- import the real plugin code --------------------------------------
    social_pkg = sys.modules.get('social')
    if social_pkg is None or not getattr(social_pkg, '_folder_test_stub', False):
        social_pkg = types.ModuleType('social')
        social_pkg.__path__ = [str(PLUGIN_ROOT)]
        social_pkg._folder_test_stub = True
        sys.modules['social'] = social_pkg

    from social.models.folders import EntityFolder  # noqa: E402  pylint: disable=C0415
    from social.models.folder_items import FolderItem  # noqa: E402  pylint: disable=C0415
    from social.models.folder_access import FolderAccessOverride  # noqa: E402  pylint: disable=C0415
    from social.models.enums.entity import EntityType  # noqa: E402  pylint: disable=C0415
    from social.models.enums.folder_access import (  # noqa: E402  pylint: disable=C0415
        FolderAccessLevel, EffectiveFolderAccess,
    )
    from social.rpc import folder as folder_rpc  # noqa: E402  pylint: disable=C0415
    from social.rpc import folder_access as folder_access_rpc  # noqa: E402  pylint: disable=C0415
    from social.events import folder_cleanup  # noqa: E402  pylint: disable=C0415

    class EntityRow(base):
        """Stand-in for applications/elitea_tools: the outer table a listing query scans.

        The exclusion clause is a correlated subquery against folder_items, so it can only
        be verified against a *different* table - which is what every real caller passes.
        """
        __tablename__ = 'test_entities'
        __table_args__ = {'schema': TENANT_SCHEMA}
        id = Column(Integer, primary_key=True)
        name = Column(String(128))

    models = types.SimpleNamespace(
        EntityRow=EntityRow,
        EntityFolder=EntityFolder,
        FolderItem=FolderItem,
        FolderAccessOverride=FolderAccessOverride,
        EntityType=EntityType,
        FolderAccessLevel=FolderAccessLevel,
        EffectiveFolderAccess=EffectiveFolderAccess,
        folder_rpc=folder_rpc,
        folder_access_rpc=folder_access_rpc,
    )

    # Pylon binds every RPC/event class onto one module instance; mirror that so the
    # cross-class `self.` calls under test resolve the way they do in production.
    class Module(folder_access_rpc.RPC, folder_rpc.RPC, folder_cleanup.Event):
        def __init__(self, context):
            self.context = context

    context = FakeContext()
    module = Module(context)

    env = Env(projects, flask_stub, engine, session_factory, models, module, context)
    env_holder['env'] = env

    @event.listens_for(engine, 'before_cursor_execute')
    def _record(conn, cursor, statement, parameters, ctx, executemany):  # pylint: disable=W0612
        env.statements.append(statement)

    for project_id in projects:
        with engine.begin() as conn:
            base.metadata.create_all(
                conn.execution_options(schema_translate_map={TENANT_SCHEMA: f'p_{project_id}'})
            )
    env.statements.clear()
    return env


def seed_folder(env, project_id, name='Folder', entity_type='agent', owner_id=1, meta=None):
    with env.session(project_id) as s:
        folder = env.models.EntityFolder(
            name=name, entity_type=entity_type, owner_id=owner_id, meta=meta or {}
        )
        s.add(folder)
        s.flush()
        return folder.id


def seed_item(env, project_id, folder_id, entity, entity_id, sort_name=None):
    with env.session(project_id) as s:
        item = env.models.FolderItem(
            folder_id=folder_id, entity=entity, entity_id=entity_id,
            project_id=project_id, owner_id=1,
            sort_name=(sort_name or f'{entity}{entity_id}'),
        )
        s.add(item)
        s.flush()
        return item.id


def seed_override(env, project_id, folder_id, user_id, level, created_by=1):
    with env.session(project_id) as s:
        row = env.models.FolderAccessOverride(
            folder_id=folder_id, user_id=user_id, access_level=level,
            project_id=project_id, created_by=created_by,
        )
        s.add(row)
        s.flush()
        return row.id


def seed_entity(env, project_id, entity_id, name=None):
    """A row in the stand-in entity table a listing query would return."""
    with env.session(project_id) as s:
        row = env.models.EntityRow(id=entity_id, name=name or f'entity{entity_id}')
        s.add(row)
        s.flush()
        return row.id
