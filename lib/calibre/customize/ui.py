__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import os, shutil, traceback, functools, sys
from collections import defaultdict
from itertools import chain, repeat

from calibre.customize import (CatalogPlugin, FileTypePlugin, PluginNotFound,
                              MetadataReaderPlugin, MetadataWriterPlugin,
                              InterfaceActionBase as InterfaceAction,
                              PreferencesPlugin, platform, InvalidPlugin,
                              StoreBase as Store, EditBookToolPlugin,
                              LibraryClosedPlugin, PluginInstallationType)
from calibre.customize.conversion import InputFormatPlugin, OutputFormatPlugin
from calibre.customize.profiles import InputProfile, OutputProfile
from calibre.customize.builtins import plugins as builtin_plugins
from calibre.ebooks.metadata import MetaInformation
from calibre.utils.config import (make_config_dir, Config, ConfigProxy,
                                 plugin_dir, OptionParser)
from calibre.constants import numeric_version, ismacos
from polyglot.builtins import iteritems, itervalues

builtin_names = frozenset(p.name for p in builtin_plugins)
BLACKLISTED_PLUGINS = frozenset({'Marvin XD', 'iOS reader applications'})


def zip_value(iterable, value):
    return zip(iterable, repeat(value))


class NameConflict(ValueError):
    pass


def _config():
    c = Config('customize')
    c.add_opt('plugins', default={}, help=_('Installed plugins'))
    c.add_opt('filetype_mapping', default={}, help=_('Mapping for filetype plugins'))
    c.add_opt('plugin_customization', default={}, help=_('Local plugin customization'))
    c.add_opt('disabled_plugins', default=set(), help=_('Disabled plugins'))
    c.add_opt('enabled_plugins', default=set(), help=_('Enabled plugins'))

    return ConfigProxy(c)


config = _config()


def find_plugin(name):
    for plugin in _initialized_plugins:
        if plugin.name == name:
            return plugin


# Enable/disable plugins {{{


def disable_plugin(plugin_or_name):
    x = getattr(plugin_or_name, 'name', plugin_or_name)
    plugin = find_plugin(x)
    if not plugin.can_be_disabled:
        raise ValueError('Plugin %s cannot be disabled'%x)
    dp = config['disabled_plugins']
    dp.add(x)
    config['disabled_plugins'] = dp
    ep = config['enabled_plugins']
    if x in ep:
        ep.remove(x)
    config['enabled_plugins'] = ep


def enable_plugin(plugin_or_name):
    x = getattr(plugin_or_name, 'name', plugin_or_name)
    dp = config['disabled_plugins']
    if x in dp:
        dp.remove(x)
    config['disabled_plugins'] = dp
    ep = config['enabled_plugins']
    ep.add(x)
    config['enabled_plugins'] = ep


def restore_plugin_state_to_default(plugin_or_name):
    x = getattr(plugin_or_name, 'name', plugin_or_name)
    dp = config['disabled_plugins']
    if x in dp:
        dp.remove(x)
    config['disabled_plugins'] = dp
    ep = config['enabled_plugins']
    if x in ep:
        ep.remove(x)
    config['enabled_plugins'] = ep


default_disabled_plugins = {
    'Overdrive', 'Douban Books', 'OZON.ru', 'Edelweiss', 'Google Images', 'Big Book Search',
}


def is_disabled(plugin):
    if plugin.name in config['enabled_plugins']:
        return False
    return plugin.name in config['disabled_plugins'] or \
            plugin.name in default_disabled_plugins
# }}}

# File type plugins {{{


_on_import           = {}
_on_postimport       = {}
_on_postconvert      = {}
_on_postdelete       = {}
_on_preprocess       = {}
_on_postprocess      = {}
_on_postadd          = []


def reread_filetype_plugins():
    global _on_import, _on_postimport, _on_postconvert, _on_postdelete, _on_preprocess, _on_postprocess, _on_postadd
    _on_import           = defaultdict(list)
    _on_postimport       = defaultdict(list)
    _on_postconvert      = defaultdict(list)
    _on_postdelete       = defaultdict(list)
    _on_preprocess       = defaultdict(list)
    _on_postprocess      = defaultdict(list)
    _on_postadd          = []

    for plugin in _initialized_plugins:
        if isinstance(plugin, FileTypePlugin):
            if ismacos and plugin.name == 'DeDRM' and plugin.version < (10, 0, 3):
                print(f'Blacklisting the {plugin.name} plugin as it is too old and causes crashes', file=sys.stderr)
                continue
            for ft in plugin.file_types:
                if plugin.on_import:
                    _on_import[ft].append(plugin)
                if plugin.on_postimport:
                    _on_postimport[ft].append(plugin)
                    _on_postadd.append(plugin)
                if plugin.on_postconvert:
                    _on_postconvert[ft].append(plugin)
                if plugin.on_postdelete:
                    _on_postdelete[ft].append(plugin)
                if plugin.on_preprocess:
                    _on_preprocess[ft].append(plugin)
                if plugin.on_postprocess:
                    _on_postprocess[ft].append(plugin)


def plugins_for_ft(ft, occasion):
    op = {
        'import':_on_import, 'preprocess':_on_preprocess, 'postprocess':_on_postprocess, 'postimport':_on_postimport,
        'postconvert':_on_postconvert, 'postdelete':_on_postdelete,
    }[occasion]
    for p in chain(op.get(ft, ()), op.get('*', ())):
        if not is_disabled(p):
            yield p


def _run_filetype_plugins(path_to_file, ft=None, occasion='preprocess'):
    customization = config['plugin_customization']
    if ft is None:
        ft = os.path.splitext(path_to_file)[-1].lower().replace('.', '')
    nfp = path_to_file
    for plugin in plugins_for_ft(ft, occasion):
        plugin.site_customization = customization.get(plugin.name, '')
        oo, oe = sys.stdout, sys.stderr  # Some file type plugins out there override the output streams with buggy implementations
        with plugin:
            try:
                plugin.original_path_to_file = path_to_file
            except Exception:
                pass
            try:
                nfp = plugin.run(nfp) or nfp
            except:
                print('Running file type plugin %s failed with traceback:'%plugin.name, file=oe)
                traceback.print_exc(file=oe)
        sys.stdout, sys.stderr = oo, oe
    def x(j):
        return os.path.normpath(os.path.normcase(j))
    if occasion == 'postprocess' and x(nfp) != x(path_to_file):
        shutil.copyfile(nfp, path_to_file)
        nfp = path_to_file
    return nfp


run_plugins_on_import      = functools.partial(_run_filetype_plugins, occasion='import')
run_plugins_on_preprocess  = functools.partial(_run_filetype_plugins, occasion='preprocess')
run_plugins_on_postprocess = functools.partial(_run_filetype_plugins, occasion='postprocess')


def run_plugins_on_postimport(db, book_id, fmt):
    customization = config['plugin_customization']
    fmt = fmt.lower()
    for plugin in plugins_for_ft(fmt, 'postimport'):
        plugin.site_customization = customization.get(plugin.name, '')
        with plugin:
            try:
                plugin.postimport(book_id, fmt, db)
            except Exception:
                print(f'Running file type plugin {plugin.name} failed with traceback:', file=sys.stderr)
                traceback.print_exc()


def run_plugins_on_postconvert(db, book_id, fmt):
    customization = config['plugin_customization']
    fmt = fmt.lower()
    for plugin in plugins_for_ft(fmt, 'postconvert'):
        plugin.site_customization = customization.get(plugin.name, '')
        with plugin:
            try:
                plugin.postconvert(book_id, fmt, db)
            except Exception:
                print(f'Running file type plugin {plugin.name} failed with traceback:', file=sys.stderr)
                traceback.print_exc()


def run_plugins_on_postdelete(db, book_id, fmt):
    customization = config['plugin_customization']
    fmt = fmt.lower()
    for plugin in plugins_for_ft(fmt, 'postdelete'):
        plugin.site_customization = customization.get(plugin.name, '')
        with plugin:
            try:
                plugin.postdelete(book_id, fmt, db)
            except Exception:
                print(f'Running file type plugin {plugin.name} failed with traceback:', file=sys.stderr)
                traceback.print_exc()


def run_plugins_on_postadd(db, book_id, fmt_map):
    customization = config['plugin_customization']
    for plugin in _on_postadd:
        if is_disabled(plugin):
            continue
        plugin.site_customization = customization.get(plugin.name, '')
        with plugin:
            try:
                plugin.postadd(book_id, fmt_map, db)
            except Exception:
                print(f'Running file type plugin {plugin.name} failed with traceback:', file=sys.stderr)
                traceback.print_exc()

# }}}

# Plugin customization {{{


def customize_plugin(plugin, custom):
    d = config['plugin_customization']
    d[plugin.name] = custom.strip()
    config['plugin_customization'] = d


def plugin_customization(plugin):
    return config['plugin_customization'].get(plugin.name, '')

# }}}

# Input/Output profiles {{{


def input_profiles():
    for plugin in _initialized_plugins:
        if isinstance(plugin, InputProfile):
            yield plugin


def output_profiles():
    for plugin in _initialized_plugins:
        if isinstance(plugin, OutputProfile):
            yield plugin
# }}}

# Interface Actions # {{{


def interface_actions():
    customization = config['plugin_customization']
    for plugin in _initialized_plugins:
        if isinstance(plugin, InterfaceAction):
            if not is_disabled(plugin):
                plugin.site_customization = customization.get(plugin.name, '')
                yield plugin
# }}}

# Preferences Plugins # {{{


def preferences_plugins():
    customization = config['plugin_customization']
    for plugin in _initialized_plugins:
        if isinstance(plugin, PreferencesPlugin):
            if not is_disabled(plugin):
                plugin.site_customization = customization.get(plugin.name, '')
                yield plugin
# }}}

# Library Closed Plugins # {{{


def available_library_closed_plugins():
    customization = config['plugin_customization']
    for plugin in _initialized_plugins:
        if isinstance(plugin, LibraryClosedPlugin):
            if not is_disabled(plugin):
                plugin.site_customization = customization.get(plugin.name, '')
                yield plugin


def has_library_closed_plugins():
    for plugin in _initialized_plugins:
        if isinstance(plugin, LibraryClosedPlugin):
            if not is_disabled(plugin):
                return True
    return False
# }}}

# Store Plugins # {{{


def store_plugins():
    customization = config['plugin_customization']
    for plugin in _initialized_plugins:
        if isinstance(plugin, Store):
            plugin.site_customization = customization.get(plugin.name, '')
            yield plugin


def available_store_plugins():
    for plugin in store_plugins():
        if not is_disabled(plugin):
            yield plugin


def stores():
    stores = set()
    for plugin in store_plugins():
        stores.add(plugin.name)
    return stores


def available_stores():
    stores = set()
    for plugin in available_store_plugins():
        stores.add(plugin.name)
    return stores

# }}}

# Metadata read/write {{{


_metadata_readers = {}
_metadata_writers = {}


def reread_metadata_plugins():
    global _metadata_readers
    global _metadata_writers
    _metadata_readers = defaultdict(list)
    _metadata_writers = defaultdict(list)
    for plugin in _initialized_plugins:
        if isinstance(plugin, MetadataReaderPlugin):
            for ft in plugin.file_types:
                _metadata_readers[ft].append(plugin)
        elif isinstance(plugin, MetadataWriterPlugin):
            for ft in plugin.file_types:
                _metadata_writers[ft].append(plugin)

    # Ensure the following metadata plugin preference is used:
    # external > system > builtin
    def key(plugin):
        order = sys.maxsize if plugin.installation_type is None else plugin.installation_type
        return order, plugin.name

    for group in (_metadata_readers, _metadata_writers):
        for plugins in itervalues(group):
            if len(plugins) > 1:
                plugins.sort(key=key)


def metadata_readers():
    ans = set()
    for plugins in _metadata_readers.values():
        for plugin in plugins:
            ans.add(plugin)
    return ans


def metadata_writers():
    ans = set()
    for plugins in _metadata_writers.values():
        for plugin in plugins:
            ans.add(plugin)
    return ans


class QuickMetadata:

    def __init__(self):
        self.quick = False

    def __enter__(self):
        self.quick = True

    def __exit__(self, *args):
        self.quick = False


quick_metadata = QuickMetadata()


class ApplyNullMetadata:

    def __init__(self):
        self.apply_null = False

    def __enter__(self):
        self.apply_null = True

    def __exit__(self, *args):
        self.apply_null = False


apply_null_metadata = ApplyNullMetadata()


class ForceIdentifiers:

    def __init__(self):
        self.force_identifiers = False

    def __enter__(self):
        self.force_identifiers = True

    def __exit__(self, *args):
        self.force_identifiers = False


force_identifiers = ForceIdentifiers()


def get_file_type_metadata(stream, ftype):
    mi = MetaInformation(None, None)

    ftype = ftype.lower().strip()
    if ftype in _metadata_readers:
        for plugin in _metadata_readers[ftype]:
            if not is_disabled(plugin):
                with plugin:
                    try:
                        plugin.quick = quick_metadata.quick
                        if hasattr(stream, 'seek'):
                            stream.seek(0)
                        mi = plugin.get_metadata(stream, ftype.lower().strip())
                        break
                    except:
                        traceback.print_exc()
                        continue
    return mi


def set_file_type_metadata(stream, mi, ftype, report_error=None):
    ftype = ftype.lower().strip()
    if ftype in _metadata_writers:
        customization = config['plugin_customization']
        for plugin in _metadata_writers[ftype]:
            if not is_disabled(plugin):
                with plugin:
                    try:
                        plugin.apply_null = apply_null_metadata.apply_null
                        plugin.force_identifiers = force_identifiers.force_identifiers
                        plugin.site_customization = customization.get(plugin.name, '')
                        plugin.set_metadata(stream, mi, ftype.lower().strip())
                        break
                    except:
                        if report_error is None:
                            from calibre import prints
                            prints('Failed to set metadata for the', ftype.upper(), 'format of:', getattr(mi, 'title', ''), file=sys.stderr)
                            traceback.print_exc()
                        else:
                            report_error(mi, ftype, traceback.format_exc())


def can_set_metadata(ftype):
    ftype = ftype.lower().strip()
    for plugin in _metadata_writers.get(ftype, ()):
        if not is_disabled(plugin):
            return True
    return False

# }}}

# Input/Output format plugins {{{

def input_format_plugins():
    for plugin in _initialized_plugins:
        if isinstance(plugin, InputFormatPlugin):
            yield plugin


def plugin_for_input_format(fmt):
    customization = config['plugin_customization']
    for plugin in input_format_plugins():
        if fmt.lower() in plugin.file_types:
            plugin.site_customization = customization.get(plugin.name, None)
            return plugin


def all_input_formats():
    formats = set()
    for plugin in input_format_plugins():
        for format in plugin.file_types:
            formats.add(format)
    return formats


def available_input_formats():
    formats = set()
    for plugin in input_format_plugins():
        if not is_disabled(plugin):
            for format in plugin.file_types:
                formats.add(format)
    formats.add('zip'), formats.add('rar')
    return formats


def output_format_plugins():
    for plugin in _initialized_plugins:
        if isinstance(plugin, OutputFormatPlugin):
            yield plugin


def plugin_for_output_format(fmt):
    customization = config['plugin_customization']
    for plugin in output_format_plugins():
        if fmt.lower() == plugin.file_type:
            plugin.site_customization = customization.get(plugin.name, None)
            return plugin


def available_output_formats():
    formats = set()
    for plugin in output_format_plugins():
        if not is_disabled(plugin):
            formats.add(plugin.file_type)
    return formats

# }}}

# Catalog plugins {{{


def catalog_plugins():
    for plugin in _initialized_plugins:
        if isinstance(plugin, CatalogPlugin):
            yield plugin


def available_catalog_formats():
    formats = set()
    for plugin in catalog_plugins():
        if not is_disabled(plugin):
            for format in plugin.file_types:
                formats.add(format)
    return formats


def plugin_for_catalog_format(fmt):
    for plugin in catalog_plugins():
        if fmt.lower() in plugin.file_types:
            return plugin

# }}}

# Device plugins {{{


def device_plugins(include_disabled=False):
    return


def disabled_device_plugins():
    return

# Metadata sources2 {{{


def metadata_plugins(capabilities):
    capabilities = frozenset(capabilities)
    for plugin in all_metadata_plugins():
        if plugin.capabilities.intersection(capabilities) and \
                not is_disabled(plugin):
            yield plugin


def all_metadata_plugins():
    return


def patch_metadata_plugins(possibly_updated_plugins):
    return
# }}}

# Editor plugins {{{


def all_edit_book_tool_plugins():
    for plugin in _initialized_plugins:
        if isinstance(plugin, EditBookToolPlugin):
            yield plugin
# }}}

# Initialize plugins {{{


_initialized_plugins = []


def initialize_plugin(plugin, path_to_zip_file, installation_type):
    try:
        p = plugin(path_to_zip_file)
        p.installation_type = installation_type
        p.initialize()
        return p
    except Exception:
        print('Failed to initialize plugin:', plugin.name, plugin.version)
        tb = traceback.format_exc()
        raise InvalidPlugin((_('Initialization of plugin %s failed with traceback:')
                            %tb) + '\n'+tb)


def has_external_plugins():
    'True if there are updateable (ZIP file based) plugins'
    return bool(config['plugins'])


@functools.lru_cache(maxsize=2)
def get_system_plugins():
    return {}


def initialize_plugins(perf=False):
    global _initialized_plugins
    _initialized_plugins = []
    system_plugins = get_system_plugins().copy()
    conflicts = {name for name in config['plugins'] if name in
            builtin_names or name in system_plugins}
    for p in conflicts:
        remove_plugin(p)
    system_conflicts = [name for name in system_plugins if name in
            builtin_names]
    for p in system_conflicts:
        system_plugins.pop(p, None)
    external_plugins = config['plugins'].copy()
    for name in BLACKLISTED_PLUGINS:
        external_plugins.pop(name, None)
        system_plugins.pop(name, None)
    ostdout, ostderr = sys.stdout, sys.stderr
    if perf:
        from collections import defaultdict
        import time
        times = defaultdict(int)

    for zfp, installation_type in chain(
            zip_value(external_plugins.items(), PluginInstallationType.EXTERNAL),
            zip_value(system_plugins.items(), PluginInstallationType.SYSTEM),
            zip_value(builtin_plugins, PluginInstallationType.BUILTIN),
            ):
        try:
            if not isinstance(zfp, type):
                # We have a plugin name
                pname, path = zfp
                zfp = os.path.join(plugin_dir, pname+'.zip')
                if not os.path.exists(zfp):
                    zfp = path
            try:
                plugin = load_plugin(zfp) if not isinstance(zfp, type) else zfp
            except PluginNotFound:
                continue
            if perf:
                st = time.time()
            plugin = initialize_plugin(
                    plugin,
                    None if isinstance(zfp, type) else zfp, installation_type,
            )
            if perf:
                times[plugin.name] = time.time() - st
            _initialized_plugins.append(plugin)
        except:
            print('Failed to initialize plugin:', repr(zfp), file=sys.stderr)
    # Prevent a custom plugin from overriding stdout/stderr as this breaks
    # ipython
    sys.stdout, sys.stderr = ostdout, ostderr
    if perf:
        for x in sorted(times, key=lambda x: times[x]):
            print('%50s: %.3f'%(x, times[x]))
    _initialized_plugins.sort(key=lambda x: x.priority, reverse=True)
    reread_filetype_plugins()
    reread_metadata_plugins()


initialize_plugins()


def initialized_plugins():
    yield from _initialized_plugins

def option_parser():
    parser = OptionParser(usage=_('''\
    %prog options

    Customize calibre by loading external plugins.
    '''))
    parser.add_option('-a', '--add-plugin', default=None,
                      help=_('Add a plugin by specifying the path to the ZIP file containing it.'))
    parser.add_option('-b', '--build-plugin', default=None,
            help=_('For plugin developers: Path to the folder where you are'
                ' developing the plugin. This command will automatically zip '
                'up the plugin and update it in calibre.'))
    parser.add_option('-r', '--remove-plugin', default=None,
                      help=_('Remove a custom plugin by name. Has no effect on builtin plugins'))
    parser.add_option('--customize-plugin', default=None,
                      help=_('Customize plugin. Specify name of plugin and customization string separated by a comma.'))
    parser.add_option('-l', '--list-plugins', default=False, action='store_true',
                      help=_('List all installed plugins'))
    parser.add_option('--enable-plugin', default=None,
                      help=_('Enable the named plugin'))
    parser.add_option('--disable-plugin', default=None,
                      help=_('Disable the named plugin'))
    return parser

