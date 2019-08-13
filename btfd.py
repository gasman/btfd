#!/usr/bin/env python

import argparse
import json
import os
import os.path
import re
import shlex
import shutil
import subprocess
import sys

from cached_property import cached_property
from git import Repo
from git.util import RemoteProgress


CANONICAL_URL = 'https://docs.wagtail.io/en/stable/'


class Environment:
    """
    represents a build environment consisting of multiple git checkouts within a root path
    """
    def __init__(self, base_path):
        self.base_path = os.path.abspath(base_path)

    @cached_property
    def master_path(self):
        return os.path.join(self.base_path, 'master')

    @cached_property
    def master_repo(self):
        return Repo(self.master_path)

    @cached_property
    def virtualenv_parent_path(self):
        return os.path.join(self.base_path, 'venv')

    @cached_property
    def html_base_path(self):
        return os.path.join(self.base_path, 'html')

    def branch_name_exists_in_master_repo(self, name):
        return any(head.name == name for head in self.master_repo.heads)

    @cached_property
    def remote_branches(self):
        # find all remote branches matching the format origin/stable/N.N.x
        version_branches = []
        master_branch = None

        for remote_ref in self.master_repo.remote().refs:
            if remote_ref.name == 'origin/master':
                master_branch = MasterBranch(self, remote_ref)
            else:
                match = re.match(r'^origin/stable/(\d+)\.(\d+).x$', remote_ref.name)

                if match:
                    version_branches.append(VersionBranch(self, remote_ref, match.group(1), match.group(2)))

        # sort versions as (major, minor) tuples to ensure semantic ordering (1.10 > 1.2)
        version_branches.sort(key=lambda branch: branch.version)

        if master_branch is None:
            raise Exception('no master branch found')
        return version_branches + [master_branch]

    @cached_property
    def stable_branch(self):
        return self.remote_branches[-2]

    @cached_property
    def master_branch(self):
        return self.remote_branches[-1]

    def update(self, branches=None, command_flags=''):
        print("Pulling from master")
        self.master_repo.remote().pull()

        for branch in self.remote_branches:
            if branches is None:
                # building all branches
                pass
            elif branch.version_string in branches:
                # building this branch
                pass
            elif 'stable' in branches and branch == self.stable_branch:
                # building 'stable', which is an alias to this branch
                pass
            elif 'latest' in branches and branch == self.master_branch:
                # building 'latest', which is an alias to master
                pass
            else:
                # not building this branch
                continue

            print("Updating branch %s" % branch.version_string)
            branch.update(command_flags=command_flags)

        versions_file_name = os.path.join(self.html_base_path, 'versions.js')
        version_list = [
            branch.target_dir_name
            for branch in reversed(self.remote_branches)
            if branch.should_build()
        ]
        version_list.insert(1, 'stable')

        with open(versions_file_name, 'w') as f:
            print("VERSIONS = %s;" % json.dumps(version_list), file=f)


    @staticmethod
    def create(repository_url, path=None):
        if path is None:
            # auto-generate path from the last portion of the git URL
            path = repository_url.split('/')[-1]
            path = re.sub(r'\.git$', '', path)

        env = Environment(path)

        if os.path.exists(env.base_path):
            print("Path %s already exists - skipping initialisation." % env.base_path)
            return env

        os.mkdir(env.base_path)

        print("Cloning %s into %s..." % (repository_url, env.master_path))
        Repo.clone_from(repository_url, env.master_path, progress=PrintProgress())
        print()

        return env


class Branch:
    def __init__(self, env, remote_head):
        self.env = env
        self.remote_head = remote_head

    @cached_property
    def path(self):
        return os.path.join(self.env.base_path, self.version_string)

    @cached_property
    def docs_path(self):
        return os.path.join(self.path, 'docs')

    @cached_property
    def built_html_path(self):
        return os.path.join(self.docs_path, '_build', 'html')

    @cached_property
    def virtualenv_path(self):
        return os.path.join(self.env.virtualenv_parent_path, self.version_string)

    def copy_docs_dir(self, destination):
        if os.path.exists(destination):
            shutil.rmtree(destination, ignore_errors=False)
        shutil.copytree(self.built_html_path, destination)

    def install(self):
        pip_cmd = os.path.join(self.virtualenv_path, 'bin', 'pip')
        subprocess.check_call([pip_cmd, 'install', '-e', self.path + '[docs]'])

    def update(self, command_flags=''):
        if not self.should_build():
            return

        if not os.path.exists(self.virtualenv_path):
            subprocess.check_call(['virtualenv', self.virtualenv_path, '--python=%s' % self.python_version()])

        self.install()

        activate_cmd = os.path.join(self.virtualenv_path, 'bin', 'activate')

        command_flags += (' -A theme_canonical_url=%s' % CANONICAL_URL)
        command_flags += ' -A display_github=1 -A github_user=wagtail -A github_repo=wagtail'
        command_flags += ' -A github_version=master -A conf_py_path=/docs/'
        command_flags += ' -D html_js_files=/versions.js,/version_listing.js'
        command = 'source %s && make -C %s html -e SPHINXOPTS=%s' % (
            shlex.quote(activate_cmd), shlex.quote(self.docs_path), shlex.quote(command_flags)
        )
        subprocess.check_call(command, shell=True)

        os.makedirs(self.env.html_base_path, exist_ok=True)

        html_path = os.path.join(self.env.html_base_path, 'en', self.target_dir_name)
        self.copy_docs_dir(html_path)

        if self == self.env.stable_branch:
            html_path = os.path.join(self.env.html_base_path, 'en', 'stable')
            self.copy_docs_dir(html_path)


class MasterBranch(Branch):
    version_string = 'master'
    target_dir_name = 'latest'

    def should_build(self):
        return True

    def python_version(self):
        return 'python3.6'


class VersionBranch(Branch):
    def __init__(self, env, remote_head, major_version, minor_version):
        super().__init__(env, remote_head)
        self.version = (int(major_version), int(minor_version))

    @property
    def version_string(self):
        return '%d.%d' % self.version

    @property
    def local_name(self):
        return 'stable/%d.%d.x' % self.version

    @property
    def target_dir_name(self):
        return 'v' + self.version_string

    def should_build(self):
        return self.version >= (0, 4)

    def python_version(self):
        return 'python3.6' if self.version >= (1, 10) else 'python2.7'

    def update_repo(self):
        if os.path.exists(self.path):
            # update the existing cloned repo for this version branch
            repo = Repo(self.path)
            print("Updating version %s" % self.version_string)
            repo.remote().pull()
        else:
            # create a clone of the master repo checked out at this branch
            print("Cloning version %s" % self.version_string)
            repo = self.env.master_repo.clone(self.path, branch=self.local_name)

        return repo

    def install(self):
        pip_cmd = os.path.join(self.virtualenv_path, 'bin', 'pip')
        if self.version >= (1, 4):
            subprocess.check_call([pip_cmd, 'install', '-e', self.path + '[docs]'])
        elif self.version >= (1, 0):
            subprocess.check_call([pip_cmd, 'install', '-e', self.path])
            subprocess.check_call([pip_cmd, 'install', '-r', os.path.join(self.path, 'requirements-dev.txt')])
        else:
            subprocess.check_call([pip_cmd, 'install', '-e', self.path])
            subprocess.check_call([pip_cmd, 'install', 'Sphinx<2.0', 'sphinx-rtd-theme'])

    def update(self, command_flags=''):
        # create a local tracking branch for this version if none exists already
        if not self.env.branch_name_exists_in_master_repo(self.local_name):
            local_branch = self.env.master_repo.create_head(self.local_name, self.remote_head)
            local_branch.set_tracking_branch(self.remote_head)

        self.update_repo()

        super().update(command_flags=command_flags)


class PrintProgress(RemoteProgress):
    def update(self, op_code, cur_count, max_count=None, message=''):
        print("\x1b[2K\r" + self._cur_line, end='')


def command_init(args):
    Environment.create(args.repository, args.path)


def command_build(args):
    if args.branch:
        branches = [args.branch]
    else:
        branches = None
    Environment(args.path).update(branches=branches, command_flags="-a")


def command_update(args):
    if args.branch:
        branches = [args.branch]
    else:
        branches = None
    Environment(args.path).update(branches=branches)


parser = argparse.ArgumentParser()
subparsers = parser.add_subparsers()

parser_init = subparsers.add_parser('init', help='Initialise the repository')
parser_init.add_argument('repository', help='URL of repository')
parser_init.add_argument('path', nargs='?', default=None, help='path to clone to')
parser_init.set_defaults(func=command_init)

parser_update = subparsers.add_parser('build', help='Rebuild docs (all files)')
parser_update.add_argument('path', help='path to repository')
parser_update.add_argument('branch', nargs='?', default=None, help='branch to rebuild')
parser_update.set_defaults(func=command_build)

parser_update = subparsers.add_parser('update', help='Update docs (build changed files only)')
parser_update.add_argument('path', help='path to repository')
parser_update.add_argument('branch', nargs='?', default=None, help='branch to update')
parser_update.set_defaults(func=command_update)

args = parser.parse_args()
try:
    command_func = args.func
except AttributeError:
    parser.print_help()
    sys.exit(0)

command_func(args)
