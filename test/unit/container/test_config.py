import shutil
import tempfile
from os import path
import unittest
import os
import yaml
import json

from container.config import AnsibleContainerConfig
from container.exceptions import AnsibleContainerConfigException


class TestAnsibleContainerConfig(unittest.TestCase):

    '''
    This test class creates a temporary folder with only "main.yml"
    written out. This tests passses if AnsibleContainerNotInitializedException
    is correctly raised due to a missing 'container.yml' file.
    '''

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.ansible_dir = path.join(self.test_dir, "ansible")
        os.mkdir(self.ansible_dir)
        # Create container.yml.
        container_text = (
            u"version: '1'\n"
            u"defaults:\n"
            u"    web_image: apache:latest\n"
            u"    web_ports: ['8080:80']\n"
            u"    debug: 0\n"
            u"    foo: bar\n"
            u"    db_service:\n"
            u"      image: 'postgres:9.5.4'\n"
            u"services:\n"
            u"    web:\n"
            u"        image: {{ web_image }}\n"
            u"        ports: {{ web_ports }}\n"
            u"        command: ['sleep', '1d']\n"
            u"        foo: {{ foo }}\n"
            u"        dev_overrides:\n"
            u"            environment: ['DEBUG={{ debug }}']\n"
            u"    db: {{ db_service }}\n"
            u"registries: {}\n"
        )
        with open(os.path.join(self.ansible_dir, 'container.yml'), 'w') as fs:
            fs.write(container_text)
        var_data = {
            u"debug": 1,
            u"web_ports": [u"8000:8000"],
            u"web_image": u"python:2.7",
            u"foo": u"baz",
            u"db_service": {
                u"image": u"python:2.7",
                u"command": u"sleep 10",
                u"expose": [5432],
                u"environment": {
                    u"POSTGRES_DB_NAME": u"foobar",
                    u"POSTGRES_USER": u"admin",
                    u"POSTGRES_PASSWORD": u"admin"
                }
            }
        }
        # Create var file devel.yml
        with open(os.path.join(self.ansible_dir, 'devel.yml'), 'w') as fs:
            yaml.safe_dump(var_data, fs, default_flow_style=False, indent=2)
        # create var file devel.txt
        with open(os.path.join(self.ansible_dir, 'devel.txt'), 'w') as fs:
            fs.write(json.dumps(var_data))
        self.config = AnsibleContainerConfig(self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_should_instantiate(self):
        self.assertEqual(len(self.config._config['services'].keys()), 2, 'Failed to load container.yml')

    def test_should_remove_defaults_section(self):
        self.assertEqual(self.config._config.get('defaults', None), None, 'Failed to remove defaults.')

    def test_should_parse_defaults(self):
        defaults = self.config._get_defaults()
        self.assertEqual(defaults['foo'], 'bar')
        self.assertEqual(defaults['debug'], 0)
        self.assertEqual(defaults['web_image'], 'apache:latest')

    def test_should_parse_yaml_file(self):
        new_vars = self.config._get_variables_from_file('devel.yml')
        self.assertEqual(new_vars['debug'], 1, 'Failed to parse devel.yml - checked debug')
        self.assertEqual(new_vars['web_image'], "python:2.7", "Failed to parse devel.yml - web_image")

    def test_should_parse_json_file(self):
        new_vars = self.config._get_variables_from_file('devel.txt')
        self.assertEqual(new_vars['debug'], 1, 'Failed to parse devel.txt - checked debug')
        self.assertEqual(new_vars['web_image'], "python:2.7", "Failed to parse devel.txt - web_image")

    def test_should_raise_file_not_found_error(self):
        with self.assertRaises(AnsibleContainerConfigException) as exc:
            self.config._get_variables_from_file('foo')
        self.assertIn('Unable to locate', exc.exception.args[0])

    def test_should_read_environment_vars(self):
        os.environ.update({u'AC_DEBUG': '2'})
        new_vars = self.config._get_environment_variables()
        self.assertDictContainsSubset({u'debug': '2'}, new_vars)

    def test_should_give_precedence_to_env_vars(self):
        # If an environment var exists, it should get precedence.
        os.environ.update({u'AC_FOO': 'cats'})
        self.config.var_file = 'devel.yml'
        self.config.set_env('prod')
        self.assertEqual(self.config._config['services']['web']['foo'], 'cats')

    def test_should_give_precedence_to_file_vars(self):
        # If no environment var, then var defined in var_file should get precedence.
        if os.environ.get('AC_FOO'):
            del os.environ['AC_FOO']
        self.config.var_file = 'devel.yml'
        self.config.set_env('prod')
        self.assertEqual(self.config._config['services']['web']['foo'], 'baz')

    def test_should_give_precedence_to_default_vars(self):
        # If no environment var and no var_file, then the default value should be used.
        if os.environ.get('AC_FOO'):
            del os.environ['AC_FOO']
        self.config.var_file = None
        self.config.set_env('prod')
        self.assertEqual(self.config._config['services']['web']['foo'], 'bar')


