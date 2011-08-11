#!/usr/bin/env python

__author__ = 'Adam R. Smith'
__license__ = 'Apache 2.0'

from anode.base import obj_types

import datetime
import fnmatch
import os
import re
import sys
import argparse

import yaml

templates = {
      'file':
'''#!/usr/bin/env python

from zope.interface import Interface

{classes}
'''
    , 'class':
'''class {name}(Interface):
{methods}
'''
    , 'method':
'''
    def {name}(self, {args}):
        pass
'''
    , 'arg': '{name}={val}'
}

description = 'Anode utility for generating interfaces from object definitions (and vice versa).'
parser = argparse.ArgumentParser(description=description)
parser.add_argument('action', type=str, default='generate', choices=['generate'], help='Which action to perform.')
args = parser.parse_args()

if os.getcwd().endswith('scripts'):
    sys.exit('This script needs to be run from the anode root.')

if args.action == 'generate':
    interface_dir = 'interface'
    if not os.path.exists(interface_dir):
        os.makedirs(interface_dir)

    # Clear old generated files
    files = os.listdir(interface_dir)
    for file in fnmatch.filter(files, '*.py') + fnmatch.filter(files, '*.pyc'):
        os.unlink(os.path.join(interface_dir, file))

    open(os.path.join(interface_dir, '__init__.py'), 'w').close()

    # Generate the new definitions, for now giving each yaml file its own python service
    file_re = re.compile('(obj)/(.*)[.](yml)')
    files = obj_types.source_files
    files.remove('obj/ion.yml')
    for yaml_file in files:
        interface_file, count = file_re.subn(r'interface/\2.py', yaml_file)
        if not count: continue

        parent_dir = os.path.dirname(interface_file)
        if not os.path.exists(parent_dir):
            os.makedirs(parent_dir)

        methods = []
        yaml_text = open(yaml_file, 'r').read()
        defs = yaml.load_all(yaml_text)
        for def_set in defs:
            for name,_def in def_set.iteritems():
                # TODO: Handle more than one definition version for the same object type
                
                args = []
                for key,val in _def.iteritems():
                    if isinstance(val, basestring):
                        val = "'%s'" % (val)
                    elif isinstance(val, datetime.datetime):
                        # TODO: generate the datetime code
                        val = "'%s'" % (val)
                    args.append(templates['arg'].format(name=key, val=val))
                args_str = ', '.join(args)

                methods.append(templates['method'].format(name=name, args=args_str))

        methods_str = '\n\n'.join(methods)
        _class = templates['class'].format(name=name, methods=methods_str)
        
        interface_contents = templates['file'].format(classes=_class)
        open(interface_file, 'w').write(interface_contents)


