""" Test schema migration

:Author: Arthur Goldberg <Arthur.Goldberg@mssm.edu>
:Date: 2018-11-18
:Copyright: 2018, Karr Lab
:License: MIT
"""

import capturer
import os
import sys
import re
import unittest
import getpass
import inspect
import tempfile
from tempfile import mkdtemp
import shutil
import numpy
import copy
import warnings
from argparse import Namespace
import yaml
from pprint import pprint, pformat
from itertools import chain
import inspect
import cProfile
import pstats
import git
import networkx as nx
from networkx.algorithms.shortest_paths.generic import has_path
import random
import time
from pathlib import Path
import socket

from obj_model.migrate import (MigratorError, MigrateWarning, SchemaModule, Migrator, MigrationController,
    RunMigration, MigrationSpec, SchemaChanges, AutomatedMigration, GitRepo)
import obj_model
from obj_model import (BooleanAttribute, EnumAttribute, FloatAttribute, IntegerAttribute,
    PositiveIntegerAttribute, RegexAttribute, SlugAttribute, StringAttribute, LongStringAttribute,
    UrlAttribute, OneToOneAttribute, ManyToOneAttribute, ManyToManyAttribute, OneToManyAttribute,
    RelatedAttribute, TabularOrientation, migrate, obj_math, get_models)
from wc_utils.workbook.io import read as read_workbook
from wc_utils.util.files import remove_silently
from obj_model.expression import Expression

# todo: move all static methods out of MigrationFixtures
# todo: remove all '# @unittest.skip("speed up testing")'
# todo: combine tricky_package into test_package
# todo: speedup migration and unittests; make smaller test data files

def make_tmp_dirs_n_small_schemas(test_case):
    test_case.fixtures_path = fixtures_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'migrate')
    test_case.tmp_dir = mkdtemp()
    # create tmp dir in 'fixtures/migrate/tmp' so it can be accessed from Docker container's host
    test_case.tmp_model_dir = mkdtemp(dir=os.path.join(test_case.fixtures_path, 'tmp'))
    test_case.existing_defs_path = os.path.join(test_case.fixtures_path, 'small_existing.py')
    test_case.migrated_defs_path = os.path.join(test_case.fixtures_path, 'small_migrated.py')
    test_case.small_bad_related_path = os.path.join(test_case.fixtures_path, 'small_bad_related.py')

def make_wc_lang_migration_fixtures(test_case):
    # set up wc_lang migration testing fixtures
    test_case.wc_lang_fixtures_path = os.path.join(test_case.fixtures_path, 'wc_lang_e0c1912', 'wc_lang')
    test_case.wc_lang_schema_existing = os.path.join(test_case.wc_lang_fixtures_path, 'core.py')
    test_case.wc_lang_schema_modified = os.path.join(test_case.wc_lang_fixtures_path, 'core_modified.py')
    test_case.wc_lang_model_copy = copy_file_to_tmp(test_case, 'example-wc_lang-model.xlsx')
    test_case.wc_lang_no_model_attrs = copy_file_to_tmp(test_case, 'example-wc_lang-model.xlsx')
    test_case.tricky_package_fixtures_path = os.path.join(test_case.fixtures_path, 'tricky_package')
    test_case.tricky_package_schema = os.path.join(test_case.tricky_package_fixtures_path, 'test_module.py')

def copy_file_to_tmp(test_case, name):
    # copy file 'name' to a new dir in the tmp dir and return its pathname
    # 'name' may either be an absolute pathname, or the name of a file in fixtures
    basename = name
    if os.path.isabs(name):
        basename = os.path.basename(name)
    tmp_filename = os.path.join(mkdtemp(dir=test_case.tmp_model_dir), basename)
    if os.path.isabs(name):
        shutil.copy(name, tmp_filename)
    else:
        shutil.copy(os.path.join(test_case.fixtures_path, name), tmp_filename)
    return tmp_filename

def temp_pathname(testcase, name):
    # create a pathname for a file called name in new temp dir, which will be discarded by tearDown()
    return os.path.join(mkdtemp(dir=testcase.tmp_model_dir), name)

def make_migrators_in_memory(test_case):

    ### create migrator with renaming that doesn't use models in files
    test_case.migrator_for_error_tests = migrator_for_error_tests = Migrator()

    ### these classes contain migration errors for validation tests ###
    ### existing models
    class RelatedObj(obj_model.Model):
        id = SlugAttribute()
    test_case.RelatedObj = RelatedObj

    class TestExisting(obj_model.Model):
        id = SlugAttribute()
        attr_a = StringAttribute()
        unmigrated_attr = StringAttribute()
        extra_attr_1 = obj_math.NumpyArrayAttribute()
        other_attr = StringAttribute()
    test_case.TestExisting = TestExisting

    class TestExisting2(obj_model.Model):
        related = OneToOneAttribute(RelatedObj, related_name='test')

    class TestNotMigrated(obj_model.Model):
        id_2 = SlugAttribute()

    migrator_for_error_tests.existing_defs = {
        'RelatedObj': RelatedObj,
        'TestExisting': TestExisting,
        'TestExisting2': TestExisting2,
        'TestNotMigrated': TestNotMigrated}

    ### migrated models
    class NewRelatedObj(obj_model.Model):
        id = SlugAttribute()
    test_case.NewRelatedObj = NewRelatedObj

    class TestMigrated(obj_model.Model):
        id = SlugAttribute()
        attr_b = IntegerAttribute()
        migrated_attr = BooleanAttribute()
        extra_attr_2 = obj_math.NumpyArrayAttribute()
        other_attr = StringAttribute(unique=True)

    class TestMigrated2(obj_model.Model):
        related = OneToOneAttribute(RelatedObj, related_name='not_test')

    migrator_for_error_tests.migrated_defs = {
        'NewRelatedObj': NewRelatedObj,
        'TestMigrated': TestMigrated,
        'TestMigrated2': TestMigrated2}

    ### renaming maps
    migrator_for_error_tests.renamed_models = [
        ('RelatedObj', 'NewRelatedObj'),
        ('TestExisting', 'TestMigrated'),
        ('TestExisting2', 'TestMigrated2')]
    migrator_for_error_tests.renamed_attributes = [
        (('TestExisting', 'attr_a'), ('TestMigrated', 'attr_b')),
        (('TestExisting', 'extra_attr_1'), ('TestMigrated', 'extra_attr_2'))]

    try:
        # ignore MigratorError exception which is tested later
        migrator_for_error_tests.prepare()
    except MigratorError:
        pass

    test_case.migrator_for_error_tests_2 = migrator_for_error_tests_2 = Migrator()
    migrator_for_error_tests_2.existing_defs = migrator_for_error_tests.existing_defs
    migrator_for_error_tests_2.migrated_defs = migrator_for_error_tests.migrated_defs
    ### renaming maps
    migrator_for_error_tests_2.renamed_models = [
        ('TestExisting', 'TestMigrated'),
        ('TestExisting2', 'TestMigrated2')]
    migrator_for_error_tests_2.renamed_attributes = migrator_for_error_tests.renamed_attributes
    try:
        # ignore errors -- they're tested in TestMigration.test_get_inconsistencies
        migrator_for_error_tests_2.prepare()
    except MigratorError:
        pass

    # create migrator with renaming that doesn't use models in files and doesn't have errors
    # existing models
    class GoodRelatedCls(obj_model.Model):
        id = SlugAttribute()
        num = IntegerAttribute()
    test_case.GoodRelatedCls = GoodRelatedCls

    class GoodExisting(obj_model.Model):
        id = SlugAttribute()
        attr_a = StringAttribute() # renamed to attr_b
        unmigrated_attr = StringAttribute()
        np_array = obj_math.NumpyArrayAttribute()
        related = OneToOneAttribute(GoodRelatedCls, related_name='test')
    test_case.GoodExisting = GoodExisting

    class GoodNotMigrated(obj_model.Model):
        id_2 = SlugAttribute()
    test_case.GoodNotMigrated = GoodNotMigrated

    # migrated models
    class GoodMigrated(obj_model.Model):
        id = SlugAttribute()
        attr_b = StringAttribute()
        np_array = obj_math.NumpyArrayAttribute()
        related = OneToOneAttribute(RelatedObj, related_name='test_2')
    test_case.GoodMigrated = GoodMigrated

    test_case.good_migrator = good_migrator = Migrator()
    good_migrator.existing_defs = {
        'GoodRelatedCls': GoodRelatedCls,
        'GoodExisting': GoodExisting,
        'GoodNotMigrated': GoodNotMigrated}
    good_migrator.migrated_defs = {
        'GoodMigrated': GoodMigrated}
    good_migrator.renamed_models = [('GoodExisting', 'GoodMigrated')]
    good_migrator.renamed_attributes = [
        (('GoodExisting', 'attr_a'), ('GoodMigrated', 'attr_b'))]
    good_migrator._validate_renamed_models()
    good_migrator._validate_renamed_attrs()


class MigrationFixtures(unittest.TestCase):
    """ Reused fixture set up and tear down
    """

    def setUp(self):
        make_tmp_dirs_n_small_schemas(self)
        self.migrator = Migrator(self.existing_defs_path, self.migrated_defs_path)
        self.migrator._load_defs_from_files()

        self.no_change_migrator = Migrator(self.existing_defs_path, self.existing_defs_path)
        self.no_change_migrator.prepare()

        # copy test models to tmp dir
        self.example_existing_model_copy = copy_file_to_tmp(self, 'example_existing_model.xlsx')
        self.example_existing_rt_model_copy = copy_file_to_tmp(self, 'example_existing_model_rt.xlsx')
        self.example_migrated_model = os.path.join(self.tmp_model_dir, 'example_migrated_model.xlsx')

        dst = os.path.join(self.tmp_model_dir, 'tsv_example')
        self.tsv_dir = shutil.copytree(os.path.join(self.fixtures_path, 'tsv_example'), dst)
        self.tsv_test_model = 'test-*.tsv'
        self.example_existing_model_tsv = os.path.join(self.tsv_dir, self.tsv_test_model)
        # put each tsv in a separate dir so globs don't match erroneously
        self.existing_2_migrated_migrated_tsv_file = os.path.join(mkdtemp(dir=self.tmp_model_dir), self.tsv_test_model)
        self.round_trip_migrated_tsv_file = os.path.join(mkdtemp(dir=self.tmp_model_dir), self.tsv_test_model)

        self.config_file = os.path.join(self.fixtures_path, 'config_rt_migrations.yaml')
        self.bad_migrations_config = os.path.join(self.fixtures_path, 'config_example_bad_migrations.yaml')

        make_migrators_in_memory(self)

        # set up round-trip schema fixtures
        self.existing_rt_model_defs_path = os.path.join(self.fixtures_path, 'small_existing_rt.py')
        self.migrated_rt_model_defs_path = os.path.join(self.fixtures_path, 'small_migrated_rt.py')
        # provide existing -> migrated renaming for the round-trip tests
        self.existing_2_migrated_renamed_models = [('Test', 'MigratedTest')]
        self.existing_2_migrated_renamed_attributes = [
            (('Test', 'existing_attr'), ('MigratedTest', 'migrated_attr')),
            (('Property', 'value'), ('Property', 'migrated_value')),
            (('Subtest', 'references'), ('Subtest', 'migrated_references'))]

        make_wc_lang_migration_fixtures(self)

        # set up expressions testing fixtures
        self.wc_lang_no_change_migrator = Migrator(self.wc_lang_schema_existing,
            self.wc_lang_schema_existing)
        self.wc_lang_changes_migrator = Migrator(self.wc_lang_schema_existing,
            self.wc_lang_schema_modified, renamed_models=[('Parameter', 'ParameterRenamed')])
        self.no_change_migrator_model = self.set_up_fun_expr_fixtures(
            self.wc_lang_no_change_migrator, 'Parameter', 'Parameter')
        self.changes_migrator_model = \
            self.set_up_fun_expr_fixtures(self.wc_lang_changes_migrator, 'Parameter', 'ParameterRenamed')

        # since MigrationSpec specifies a sequence of migrations, embed renamings in lists
        self.migration_spec = MigrationSpec('name',
            existing_files=[self.example_existing_rt_model_copy],
            schema_files=[self.existing_rt_model_defs_path, self.migrated_rt_model_defs_path],
            seq_of_renamed_models=[self.existing_2_migrated_renamed_models],
            seq_of_renamed_attributes=[self.existing_2_migrated_renamed_attributes])

        # files to delete that are not in a temp directory
        self.files_to_delete = set()

    def set_up_fun_expr_fixtures(self, migrator, existing_param_class, migrated_param_class):
        migrator.prepare()
        Model = migrator.existing_defs['Model']
        # define models in FunctionExpression.valid_used_models
        Function = migrator.existing_defs['Function']
        Observable = migrator.existing_defs['Observable']
        ParameterClass = migrator.existing_defs[existing_param_class]
        objects = {model: {} for model in [ParameterClass, Function, Observable]}
        model = Model(id='test_model', version='0.0.0')
        param = model.parameters.create(id='param_1')
        objects[ParameterClass]['param_1'] = param
        fun_1 = Expression.make_obj(model, Function, 'fun_1', 'log10(10)', objects)
        objects[Function]['fun_1'] = fun_1
        Expression.make_obj(model, Function, 'fun_2', 'param_1 + 2* Function.fun_1()', objects)
        Expression.make_obj(model, Function, 'disambiguated_fun', 'Parameter.param_1 + 2* Function.fun_1()',
            objects)
        return model

    @staticmethod
    def rm_tmp_dirs(test_case):
        shutil.rmtree(test_case.tmp_dir)
        shutil.rmtree(test_case.tmp_model_dir)

    def tearDown(self):
        MigrationFixtures.rm_tmp_dirs(self)
        for file in self.files_to_delete:
            remove_silently(file)

    @staticmethod
    def invert_renaming(renaming):
        # invert a list of renamed_models or renamed_attributes
        inverted_renaming = []
        for entry in renaming:
            existing, migrated = entry
            inverted_renaming.append((migrated, existing))
        return inverted_renaming

    def assert_differing_workbooks(self, existing_model_file, migrated_model_file):
        self.assert_equal_workbooks(existing_model_file, migrated_model_file, equal=False)

    def assert_equal_workbooks(self, existing_model_file, migrated_model_file, equal=True):
        # test whether a pair of model files are identical, or not identical if equal=False
        existing_workbook = read_workbook(existing_model_file)
        migrated_workbook = read_workbook(migrated_model_file)
        if equal:
            if not existing_workbook == migrated_workbook:
                # for debugging
                print("differences between existing_model_file '{}' and migrated_model_file '{}'".format(
                    existing_model_file, migrated_model_file))
                print(existing_workbook.difference(migrated_workbook))
            self.assertEqual(existing_workbook, migrated_workbook)
        else:
            self.assertNotEqual(existing_workbook, migrated_workbook)


# @unittest.skip("speed up testing")
class TestSchemaModule(unittest.TestCase):

    def setUp(self):
        make_tmp_dirs_n_small_schemas(self)
        make_wc_lang_migration_fixtures(self)

        self.test_package = os.path.join(self.fixtures_path, 'test_package')
        self.test_module = os.path.join(self.test_package, 'test_module.py')
        self.code = os.path.join(self.test_package, 'pkg_dir', 'code.py')

        # files to delete that are not in a temp directory
        self.files_to_delete = set()

    def tearDown(self):
        MigrationFixtures.rm_tmp_dirs(self)
        for file in self.files_to_delete:
            remove_silently(file)

    def test_parse_module_path(self):
        parse_module_path = SchemaModule.parse_module_path

        # exceptions
        not_a_python_file = os.path.join(self.tmp_dir, 'not_a_python_file.x')
        with self.assertRaisesRegex(MigratorError, "'.+' is not a Python source file name"):
            parse_module_path(not_a_python_file)
        no_such_file = os.path.join(self.tmp_dir, 'no_such_file.py')
        with self.assertRaisesRegex(MigratorError, "'.+' is not a file"):
            parse_module_path(no_such_file)
        not_a_file = mkdtemp(suffix='.py', dir=self.tmp_dir)
        with self.assertRaisesRegex(MigratorError, "'.+' is not a file"):
            parse_module_path(not_a_file)

        # module that's not in a package
        expected_dir = self.fixtures_path
        expected_package = None
        expected_module = 'small_existing'
        self.assertEqual(parse_module_path(self.existing_defs_path),
            (expected_dir, expected_package, expected_module))

        # module in package
        expected_dir = self.fixtures_path
        expected_package = 'test_package'
        expected_module = 'test_package.test_module'
        self.assertEqual(parse_module_path(self.test_module),
            (expected_dir, expected_package, expected_module))

        try:
            # test at /
            # if files cannot be written to / these tests fail silently
            module_in_root = os.path.join('/', os.path.basename(self.existing_defs_path))
            # ensure that module_in_root is removed
            self.files_to_delete.add(module_in_root)
            shutil.copy(self.existing_defs_path, module_in_root)
            expected_dir = '/'
            expected_package = None
            expected_module = 'small_existing'
            self.assertEqual(parse_module_path(module_in_root),
                (expected_dir, expected_package, expected_module))

            # package in /
            self.files_to_delete.add('/__init__.py')
            src_dst_copy_pairs = [
                (os.path.join(self.test_package, '__init__.py'), '/'),
                (os.path.join(self.test_package, '__init__.py'), '/tmp/'),
                (self.existing_defs_path, '/tmp')
            ]
            for src, dst in src_dst_copy_pairs:
                shutil.copy(src, dst)
            module_in_pkg_in_root = os.path.join('/', 'tmp', os.path.basename(self.existing_defs_path))
            expected_dir = '/'
            expected_package = 'tmp'
            expected_module = 'tmp.small_existing'
            self.assertEqual(parse_module_path(module_in_pkg_in_root),
                (expected_dir, expected_package, expected_module))

        except PermissionError:
            pass

    def check_imported_module(self, schema_module, module_name, module):
        """ Check that an imported module has the right models and relationships between them
        """
        self.assertEqual(module_name, module.__name__)

        expected_models = {
            'small_existing': {'Test', 'DeletedModel', 'Property', 'Subtest', 'Reference'},
            'test_package.test_module': {'Foo', 'Test', 'Reference'},
            'test_package.pkg_dir.code': {'Foo'},
        }

        expected_relationships = {
            'small_existing': [
                (('Property', 'test'), ('Test', 'property')),
                (('Subtest', 'test'), ('Test', 'subtests')),
                (('Subtest', 'references'), ('Reference', 'subtests'))
            ],
            'test_package.test_module': [
                (('Test', 'references'), ('Reference', 'tests')),
            ],
            'test_package.pkg_dir.code': [],
        }

        model_defs = schema_module._get_model_defs(module)
        self.assertEqual(expected_models[module_name], set(model_defs))
        for left, right in expected_relationships[module_name]:
            left_model, left_attr = left
            right_model, right_attr = right
            left_related = getattr(model_defs[left_model], left_attr).related_class
            self.assertEqual(left_related, model_defs[right_model],
                "left_related: {}, model_defs[right_model]: {}".format(id(left_related), id(model_defs[right_model])))
            right_related = model_defs[right_model].Meta.related_attributes[right_attr].related_class
            self.assertEqual(left_related, right_related)

    def multiple_import_tests_of_test_package(self, test_package_dir):
        test_module = os.path.join(test_package_dir, 'test_module.py')

        # import module in a package
        sm = SchemaModule(test_module)
        module = sm.import_module_for_migration()
        self.check_imported_module(sm, 'test_package.test_module', module)
        self.check_related_attributes(sm)

        # import module two dirs down in a package
        code = os.path.join(test_package_dir, 'pkg_dir', 'code.py')
        sm = SchemaModule(code)
        module = sm.import_module_for_migration()
        self.check_imported_module(sm, 'test_package.pkg_dir.code', module)
        self.check_related_attributes(sm)

    def test_munging(self):

        class A(obj_model.Model):
            id = SlugAttribute()

            class Meta(obj_model.Model.Meta):
                attribute_order = ('id',)

        name_a = A.__name__
        munged_name_a = SchemaModule._munge_model_name(A)
        self.assertTrue(munged_name_a.startswith(name_a))
        self.assertTrue(munged_name_a.endswith(SchemaModule.MUNGED_MODEL_NAME_SUFFIX))

        A.__name__ = munged_name_a
        self.assertTrue(SchemaModule._model_name_is_munged(A))
        self.assertEqual(SchemaModule._unmunge_model_name(A), name_a)
        A.__name__ = SchemaModule._unmunge_model_name(A)
        self.assertFalse(SchemaModule._model_name_is_munged(A))
        with self.assertRaisesRegex(MigratorError, r"\w+ isn't munged"):
            SchemaModule._unmunge_model_name(A)

        SchemaModule._munge_all_model_names()
        for model in get_models():
            self.assertTrue(SchemaModule._model_name_is_munged(model))
        SchemaModule._unmunge_all_munged_model_names()
        for model in get_models():
            self.assertFalse(SchemaModule._model_name_is_munged(model))

    def check_related_attributes(self, schema_module):
        # ensure that all RelatedAttributes point to Models contained within a module
        module = schema_module.import_module_for_migration()
        model_defs = schema_module._get_model_defs(module)
        model_names = set(model_defs)
        models = set(model_defs.values())

        for model_name, model in model_defs.items():
            for attr_name, local_attr in model.Meta.local_attributes.items():

                if isinstance(local_attr.attr, RelatedAttribute):
                    related_class = local_attr.related_class
                    self.assertIn(related_class.__name__, model_names,
                        "{}.{} references a {}, but it's not a model name in module {}".format(
                            model_name, attr_name, related_class.__name__, module.__name__))
                    self.assertEqual(related_class, model_defs[related_class.__name__],
                        "{}.{} references a {}, but it's not the model in module {}: {} != {}".format(
                            model_name, attr_name, related_class.__name__, module.__name__,
                            id(related_class), id(model_defs[related_class.__name__])))

    def test_import_module_for_migration(self):

        # import self-contained module
        sm = SchemaModule(self.existing_defs_path)
        module = sm.import_module_for_migration()
        self.assertIn(sm.module_path, SchemaModule.MODULES)
        self.assertEqual(module, SchemaModule.MODULES[sm.module_path])
        self.check_imported_module(sm, 'small_existing', module)
        self.check_related_attributes(sm)

        # importing self.existing_defs_path again returns same module from cache
        self.assertEqual(module, sm.import_module_for_migration())

        # import copy of self-contained module in another dir
        copy_of_small_existing = copy_file_to_tmp(self, 'small_existing.py')
        sm = SchemaModule(copy_of_small_existing)
        module = sm.import_module_for_migration()
        self.check_imported_module(sm, 'small_existing', module)
        self.check_related_attributes(sm)

        # test import from a package
        self.multiple_import_tests_of_test_package(self.test_package)

        # put package in new dir that's not on sys.path
        test_package_copy = temp_pathname(self, 'test_package')
        shutil.copytree(self.test_package, test_package_copy)
        self.multiple_import_tests_of_test_package(test_package_copy)

        # import a module with a syntax bug
        bad_module = os.path.join(self.tmp_dir, 'bad_module.py')
        f = open(bad_module, "w")
        f.write('bad python')
        f.close()
        sm = SchemaModule(bad_module)
        with self.assertRaisesRegex(MigratorError, "cannot be imported and exec'ed"):
            sm.import_module_for_migration()

        # import existing wc_lang
        sm = SchemaModule(self.wc_lang_schema_existing)
        self.check_related_attributes(sm)

        # import modified wc_lang
        sm = SchemaModule(self.wc_lang_schema_modified)
        self.check_related_attributes(sm)

        # test a copy of wc_lang
        wc_lang_copy = temp_pathname(self, 'wc_lang')
        shutil.copytree(self.wc_lang_fixtures_path, wc_lang_copy)
        for wc_lang_schema in ['core.py', 'core_modified.py']:
            path = os.path.join(wc_lang_copy, wc_lang_schema)
            sm = SchemaModule(path)
            self.check_related_attributes(sm)

        # test _check_imported_models errors exception
        sm = SchemaModule(self.small_bad_related_path)
        with self.assertRaisesRegex(MigratorError,
            r"\w+\.\w+ references a \w+, but it's not the model in module \w+"):
            sm.import_module_for_migration()

    def test_check_imported_models(self):
        for good_schema_path in [self.existing_defs_path, self.migrated_defs_path, self.wc_lang_schema_existing,
            self.wc_lang_schema_modified]:
            sm = SchemaModule(good_schema_path)
            self.assertEqual(sm._check_imported_models(), [])

    def test_get_model_defs(self):
        sm = SchemaModule(self.existing_defs_path)
        module = sm.import_module_for_migration()
        models = sm._get_model_defs(module)
        self.assertEqual(set(models), {'Test', 'DeletedModel', 'Property', 'Subtest', 'Reference'})
        self.assertEqual(models['Test'].__name__, 'Test')

        # test detection of a module with no Models
        empty_module = os.path.join(self.tmp_dir, 'empty_module.py')
        f = open(empty_module, "w")
        f.write('# a module with no Models')
        f.close()
        sm = SchemaModule(empty_module)
        with self.assertRaisesRegex(MigratorError, r"No subclasses of obj_model\.Model found in '\S+'"):
            sm.import_module_for_migration()

    def test_str(self):
        sm = SchemaModule(self.existing_defs_path)
        for attr in ['module_path', 'abs_module_path', 'module_name']:
            self.assertIn(attr, str(sm))
        self.assertIn(self.existing_defs_path, str(sm))

    def test_run(self):
        sm = SchemaModule(self.existing_defs_path)
        models = sm.run()
        self.assertEqual(set(models), {'Test', 'DeletedModel', 'Property', 'Subtest', 'Reference'})


# @unittest.skip("speed up testing")
class TestMigrator(MigrationFixtures):

    def setUp(self):
        super().setUp()

    def tearDown(self):
        super().tearDown()

    def test_validate_transformations(self):
        migrator = Migrator()
        self.assertEqual(Migrator._validate_transformations(migrator.transformations), [])

        def a_callable(): pass
        migrator = Migrator(transformations=dict.fromkeys(Migrator.SUPPORTED_TRANSFORMATIONS, a_callable))
        self.assertEqual(Migrator._validate_transformations(migrator.transformations), [])

        migrator = Migrator(transformations=3)
        self.assertIn("transformations should be a dict",
            Migrator._validate_transformations(migrator.transformations)[0])

        migrator = Migrator(transformations={'FOO':3, Migrator.PREPARE_EXISTING_MODELS:2})
        self.assertRegex(Migrator._validate_transformations(migrator.transformations)[0],
            "names of transformations .+ aren't a subset of the supported transformations")

        migrator = Migrator(transformations=dict.fromkeys(Migrator.SUPPORTED_TRANSFORMATIONS, 3))
        errors = Migrator._validate_transformations(migrator.transformations)
        for error in errors:
            self.assertRegex(error, r"value for transformation '.+' is a\(n\) '.+', which isn't callable")

    def test_validate_renamed_models(self):
        migrator_for_error_tests = self.migrator_for_error_tests
        self.assertEqual(migrator_for_error_tests._validate_renamed_models(), [])
        self.assertEqual(migrator_for_error_tests.models_map,
            {'TestExisting': 'TestMigrated', 'RelatedObj': 'NewRelatedObj', 'TestExisting2': 'TestMigrated2'})

        # test errors
        migrator_for_error_tests.renamed_models = [('NotExisting', 'TestMigrated')]
        self.assertIn('in renamed models not an existing model',
            migrator_for_error_tests._validate_renamed_models()[0])
        self.assertEqual(migrator_for_error_tests.models_map, {})

        migrator_for_error_tests.renamed_models = [('TestExisting', 'NotMigrated')]
        self.assertIn('in renamed models not a migrated model',
            migrator_for_error_tests._validate_renamed_models()[0])

        migrator_for_error_tests.renamed_models = [
            ('TestExisting', 'TestMigrated'),
            ('TestExisting', 'TestMigrated')]
        errors = migrator_for_error_tests._validate_renamed_models()
        self.assertIn('duplicated existing models in renamed models:', errors[0])
        self.assertIn('duplicated migrated models in renamed models:', errors[1])

    def test_validate_renamed_attrs(self):
        migrator_for_error_tests = self.migrator_for_error_tests

        self.assertEqual(migrator_for_error_tests._validate_renamed_attrs(), [])
        self.assertEqual(migrator_for_error_tests.renamed_attributes_map,
            dict(migrator_for_error_tests.renamed_attributes))

        # test errors
        for renamed_attributes in [
            [(('NotExisting', 'attr_a'), ('TestMigrated', 'attr_b'))],
            [(('TestExisting', 'no_such_attr'), ('TestMigrated', 'attr_b'))]]:
            migrator_for_error_tests.renamed_attributes = renamed_attributes
            self.assertIn('in renamed attributes not an existing model.attribute',
                migrator_for_error_tests._validate_renamed_attrs()[0])
        self.assertEqual(migrator_for_error_tests.renamed_attributes_map, {})

        for renamed_attributes in [
            [(('TestExisting', 'attr_a'), ('NotMigrated', 'attr_b'))],
            [(('TestExisting', 'attr_a'), ('TestMigrated', 'no_such_attr'))]]:
            migrator_for_error_tests.renamed_attributes = renamed_attributes
            self.assertIn('in renamed attributes not a migrated model.attribute',
                migrator_for_error_tests._validate_renamed_attrs()[0])

        for renamed_attributes in [
            [(('NotExisting', 'attr_a'), ('TestMigrated', 'attr_b'))],
            [(('TestExisting', 'attr_a'), ('NotMigrated', 'attr_b'))]]:
            migrator_for_error_tests.renamed_attributes = renamed_attributes
            self.assertRegex(migrator_for_error_tests._validate_renamed_attrs()[1],
                "renamed attribute '.*' not consistent with renamed models")

        migrator_for_error_tests.renamed_attributes = [
            (('TestExisting', 'attr_a'), ('TestMigrated', 'attr_b')),
            (('TestExisting', 'attr_a'), ('TestMigrated', 'attr_b'))]
        self.assertIn('duplicated existing attributes in renamed attributes:',
            migrator_for_error_tests._validate_renamed_attrs()[0])
        self.assertIn('duplicated migrated attributes in renamed attributes:',
            migrator_for_error_tests._validate_renamed_attrs()[1])

    def test_get_mapped_attribute(self):
        migrator_for_error_tests = self.migrator_for_error_tests

        self.assertEqual(migrator_for_error_tests._get_mapped_attribute('TestExisting', 'attr_a'),
            ('TestMigrated', 'attr_b'))
        self.assertEqual(migrator_for_error_tests._get_mapped_attribute(
            self.TestExisting, self.TestExisting.Meta.attributes['id']), ('TestMigrated', 'id'))
        self.assertEqual(migrator_for_error_tests._get_mapped_attribute('TestExisting', 'no_attr'),
            (None, None))
        self.assertEqual(migrator_for_error_tests._get_mapped_attribute('NotExisting', 'id'), (None, None))
        self.assertEqual(migrator_for_error_tests._get_mapped_attribute('RelatedObj', 'id'), ('NewRelatedObj', 'id'))
        self.assertEqual(migrator_for_error_tests._get_mapped_attribute('RelatedObj', 'no_attr'), (None, None))

    def test_load_defs_from_files(self):
        migrator = Migrator(self.existing_defs_path, self.migrated_defs_path)
        migrator._load_defs_from_files()
        self.assertEqual(set(migrator.existing_defs), {'Test', 'DeletedModel', 'Property', 'Subtest', 'Reference'})
        self.assertEqual(set(migrator.migrated_defs), {'Test', 'NewModel', 'Property', 'Subtest', 'Reference'})

    def test_get_migrated_copy_attr_name(self):
        self.assertTrue(self.migrator._get_migrated_copy_attr_name().startswith(
            Migrator.MIGRATED_COPY_ATTR_PREFIX))

    def test_get_inconsistencies(self):
        migrator_for_error_tests = self.migrator_for_error_tests

        inconsistencies = migrator_for_error_tests._get_inconsistencies('NotExistingModel', 'NotMigratedModel')
        self.assertRegex(inconsistencies[0], "existing model .* not found in")
        self.assertRegex(inconsistencies[1], "migrated model .* corresponding to existing model .* not found in")

        class A(object): pass
        migrator_for_error_tests.existing_defs['A'] = A
        migrator_for_error_tests.models_map['A'] = 'X'
        inconsistencies = migrator_for_error_tests._get_inconsistencies('A', 'NewRelatedObj')
        self.assertRegex(inconsistencies[0], "type of existing model '.*' doesn't equal type of migrated model '.*'")
        self.assertRegex(inconsistencies[1],
            "models map says '.*' migrates to '.*', but _get_inconsistencies parameters say '.*' migrates to '.*'")
        A.__name__ = 'foo'
        self.NewRelatedObj.__name__ = 'foo'
        inconsistencies = migrator_for_error_tests._get_inconsistencies('A', 'NewRelatedObj')
        self.assertRegex(inconsistencies[1],
            "name of existing model class '.+' not equal to its name in the models map '.+'")
        self.assertRegex(inconsistencies[2],
            "name of migrated model class '.+' not equal to its name in the models map '.+'")
        # clean up
        del migrator_for_error_tests.existing_defs['A']
        del migrator_for_error_tests.models_map['A']
        A.__name__ = 'A'
        self.NewRelatedObj.__name__ = 'NewRelatedObj'

        inconsistencies = migrator_for_error_tests._get_inconsistencies('TestExisting', 'TestMigrated')
        self.assertRegex(inconsistencies[0],
            r"existing attribute .+\..+ type .+ differs from its migrated attribute .+\..+ type .+")

        inconsistencies = migrator_for_error_tests._get_inconsistencies('TestExisting2', 'TestMigrated2')
        self.assertRegex(inconsistencies[0],
            r".+\..+\..+ is '.+', which differs from the migrated value of .+\..+\..+, which is '.+'")
        self.assertRegex(inconsistencies[1],
            r".+\..+\..+ is '.+', which migrates to '.+', but it differs from .+\..+\..+, which is '.+'")

        inconsistencies = self.migrator_for_error_tests_2._get_inconsistencies('TestExisting2', 'TestMigrated2')
        self.assertRegex(inconsistencies[1],
            r"existing model '.+' is not migrated, but is referenced by migrated attribute .+\..+")

    def test_get_model_order(self):
        migrator = self.migrator
        migrator.prepare()
        existing_model_order = migrator._get_existing_model_order(self.example_existing_model_copy)
        migrated_model_order = migrator._migrate_model_order(existing_model_order)
        expected_model_order = [migrator.migrated_defs[model]
            for model in ['Test', 'Property', 'Subtest', 'Reference', 'NewModel']]
        self.assertEqual(migrated_model_order, expected_model_order)
        class NoSuchModel(obj_model.Model): pass
        with self.assertRaisesRegex(MigratorError, "model 'NoSuchModel' not found in the model map"):
            migrator._migrate_model_order([NoSuchModel])

        # test ambiguous_sheet_names
        class FirstUnambiguousModel(obj_model.Model): pass

        class SecondUnambiguousModel(obj_model.Model): pass

        # models with ambiguous sheet names
        class TestModel(obj_model.Model): pass

        class TestModels(obj_model.Model): pass

        class TestModels3(obj_model.Model):
            class Meta(obj_model.Model.Meta):
                verbose_name = 'TestModel'

        class RenamedModel(obj_model.Model): pass

        class NewModel(obj_model.Model): pass

        migrator_2 = Migrator('', '')
        migrated_models = dict(
            TestModel=TestModel,
            TestModels=TestModels,
            TestModels3=TestModels3,
            FirstUnambiguousModel=FirstUnambiguousModel)
        migrator_2.existing_defs = copy.deepcopy(migrated_models)
        migrator_2.existing_defs['SecondUnambiguousModel'] = SecondUnambiguousModel

        migrator_2.migrated_defs = copy.deepcopy(migrated_models)
        migrator_2.migrated_defs['RenamedModel'] = RenamedModel
        migrator_2.migrated_defs['NewModel'] = NewModel
        migrator_2.models_map = dict(
            FirstUnambiguousModel='FirstUnambiguousModel',
            TestModel='TestModel',
            TestModels='TestModels',
            TestModels3='TestModels3',
            SecondUnambiguousModel='RenamedModel'
        )
        example_ambiguous_sheets = os.path.join(self.fixtures_path, 'example_ambiguous_sheets.xlsx')
        expected_order = ['FirstUnambiguousModel', 'RenamedModel', 'TestModel', 'TestModels', 'TestModels3', 'NewModel']
        with self.assertWarnsRegex(MigrateWarning,
            "The following sheets cannot be unambiguously mapped to models:"):
            existing_model_order = migrator_2._get_existing_model_order(example_ambiguous_sheets)

        migrated_model_order = migrator_2._migrate_model_order(existing_model_order)
        self.assertEqual([m.__name__ for m in migrated_model_order], expected_order)

    def test_prepare(self):
        migrator = self.migrator
        migrator.prepare()
        self.assertEqual(migrator.deleted_models, {'DeletedModel'})

        migrator.renamed_models = [('Test', 'NoSuchModel')]
        with self.assertRaisesRegex(MigratorError, "'.*' in renamed models not a migrated model"):
            migrator.prepare()
        migrator.renamed_models = []

        migrator.renamed_attributes = [(('Test', 'name'), ('Test', 'no_such_name'))]
        with self.assertRaisesRegex(MigratorError, "'.*' in renamed attributes not a migrated model.attribute"):
            migrator.prepare()
        migrator.renamed_attributes = []

        # triggering inconsistencies in prepare() requires inconsistent model definitions on disk
        inconsistent_migrated_model_defs_path = os.path.join(self.fixtures_path, 'small_migrated_inconsistent.py')
        inconsistent_migrator = Migrator(self.existing_defs_path, inconsistent_migrated_model_defs_path)
        inconsistent_migrator._load_defs_from_files()
        with self.assertRaisesRegex(MigratorError,
            r"existing attribute .+\..+ type .+ differs from its migrated attribute .+\..+ type .+"):
            inconsistent_migrator.prepare()

    def test_migrate_model(self):
        good_migrator = self.good_migrator
        good_migrator._migrated_copy_attr_name = good_migrator._get_migrated_copy_attr_name()

        # create good model(s) and migrate them
        grc_1 = self.GoodRelatedCls(id='grc_1', num=3)
        id = 'id_1'
        attr_a_b = 'string attr'
        np_array_val = numpy.array([1, 2])
        good_existing_1 = self.GoodExisting(
            id=id,
            attr_a=attr_a_b,
            unmigrated_attr='hi',
            np_array=np_array_val,
            related=grc_1
        )
        migrated_model = self.good_migrator._migrate_model(good_existing_1, self.GoodExisting, self.GoodMigrated)
        self.assertEqual(migrated_model.id, id)
        self.assertEqual(migrated_model.attr_b, attr_a_b)
        numpy.testing.assert_equal(migrated_model.np_array, np_array_val)

        id = None
        good_existing_2 = self.GoodExisting(
            id=id,
            attr_a=attr_a_b,
            np_array=np_array_val
        )
        migrated_model = self.good_migrator._migrate_model(good_existing_2, self.GoodExisting, self.GoodMigrated)
        self.assertEqual(migrated_model.id, id)
        self.assertEqual(migrated_model.attr_b, attr_a_b)
        numpy.testing.assert_equal(migrated_model.np_array, np_array_val)

    def test_migrate_expression(self):
        migrators = [self.wc_lang_no_change_migrator, self.wc_lang_changes_migrator]
        models = [self.no_change_migrator_model, self.changes_migrator_model]
        for migrator, model in zip(migrators, models):
            for fun in model.functions:
                if migrator == self.wc_lang_changes_migrator and fun.id == 'disambiguated_fun':
                    original_expr = fun.expression.expression
                    expected_expr = original_expr.replace('Parameter', 'ParameterRenamed')
                    wc_lang_expr = fun.expression._parsed_expression
                    self.assertEqual(migrator._migrate_expression(wc_lang_expr), expected_expr)
                else:
                    wc_lang_expr = fun.expression._parsed_expression
                    original_expr = fun.expression.expression
                    self.assertEqual(migrator._migrate_expression(wc_lang_expr), original_expr)

    def test_migrate_analyzed_expr(self):
        migrators = [self.wc_lang_no_change_migrator, self.wc_lang_changes_migrator]
        models = [self.no_change_migrator_model, self.changes_migrator_model]
        for migrator, model in zip(migrators, models):
            existing_non_expr_models = [model] + model.parameters + model.functions
            existing_function_expr_models = [fun.expression for fun in model.functions]
            all_existing_models = existing_non_expr_models + existing_function_expr_models
            migrated_models = migrator.migrate(all_existing_models)
            for existing_model, migrated_model in zip(all_existing_models, migrated_models):
                # objects that aren't expressions didn't need migrating
                if existing_model in existing_non_expr_models:
                    self.assertFalse(hasattr(migrated_model, Migrator.PARSED_EXPR))
                else:
                    self.assertTrue(hasattr(migrated_model, Migrator.PARSED_EXPR))
                    existing_expr = getattr(existing_model, Migrator.PARSED_EXPR)
                    migrated_expr = getattr(migrated_model, Migrator.PARSED_EXPR)
                    # for self.wc_lang_no_change_migrator, WcLangExpressions should be identical
                    # except for their objects
                    if migrator == self.wc_lang_no_change_migrator:
                        for attr in ['model_cls', 'attr', 'expression', '_py_tokens', 'errors']:
                            self.assertEqual(getattr(existing_expr, attr), getattr(migrated_expr, attr))
                    if migrator == self.changes_migrator_model:
                        for wc_token in migrated_expr._obj_model_tokens:
                            if hasattr(wc_token, 'model_type'):
                                self.assertTrue(getattr(wc_token, 'model_type') in
                                    self.changes_migrator_model.migrated_defs.values())
            duped_migrated_params = [migrated_models[1]]*2
            with self.assertRaisesRegex(MigratorError,
                "model type 'Parameter.*' has duplicated id: '.+'"):
                migrator._migrate_all_analyzed_exprs(zip(['ignored']*2, duped_migrated_params))

            if migrator == self.wc_lang_no_change_migrator:
                last_existing_fun_expr = all_existing_models[-1]
                last_existing_fun_expr._parsed_expression.expression = \
                    last_existing_fun_expr._parsed_expression.expression + ':'
                with self.assertRaisesRegex(MigratorError, "bad token"):
                    migrator._migrate_all_analyzed_exprs(list(zip(all_existing_models, migrated_models)))

    def test_deep_migrate_and_connect_models(self):
        # test both _deep_migrate and _connect_models because they need a similar test state
        migrator = self.migrator
        migrator.prepare()
        existing_defs = migrator.existing_defs

        # define model instances in the migrator.existing_defs schema
        test_id = 'test_id'
        ExistingTest = existing_defs['Test']
        test = ExistingTest(id=test_id, existing_attr='existing_attr')

        deleted_model = existing_defs['DeletedModel'](id='id')

        property_id = 'property_id'
        property_value = 7
        ExistingProperty = existing_defs['Property']
        property = ExistingProperty(id=property_id,
            test=None,
            value=property_value)

        ExistingReference = existing_defs['Reference']
        references = []
        num_references = 4
        for n in range(num_references):
            references.append(
                ExistingReference(
                    id="reference_id_{}".format(n),
                    value="reference_value_{}".format(n)))

        ExistingSubtest = existing_defs['Subtest']
        subtests = []
        num_subtests = 3
        for n in range(num_subtests):
            subtests.append(
                ExistingSubtest(id="subtest_{}".format(n),
                    test=test,
                    references=references[n:n + 2]))

        existing_models = []
        existing_models.append(test)
        existing_models.append(deleted_model)
        existing_models.append(property)
        existing_models.extend(references)
        existing_models.extend(subtests)

        # define model instances in the migrated migrator.migrated_defs schema
        migrated_defs = migrator.migrated_defs
        expected_migrated_models = []

        MigratedTest = migrated_defs['Test']
        migrated_attr_default = MigratedTest.Meta.attributes['migrated_attr'].default
        expected_migrated_models.append(
            MigratedTest(id=test_id, migrated_attr=migrated_attr_default))

        MigratedProperty = migrated_defs['Property']
        expected_migrated_models.append(
            MigratedProperty(id=property_id, value=property_value))

        MigratedReference = migrated_defs['Reference']
        for n in range(num_references):
            expected_migrated_models.append(
                MigratedReference(
                    id="reference_id_{}".format(n),
                    value="reference_value_{}".format(n)))

        MigratedSubtest = migrated_defs['Subtest']
        for n in range(num_subtests):
            expected_migrated_models.append(
                MigratedSubtest(id="subtest_{}".format(n)))

        all_models = migrator._deep_migrate(existing_models)

        migrated_models = [migrated_model for _, migrated_model in all_models]
        self.assertEqual(len(migrated_models), len(expected_migrated_models))
        for migrated_model, expected_migrated_model in zip(migrated_models, expected_migrated_models):
            self.assertTrue(migrated_model._is_equal_attributes(expected_migrated_model))

        expected_migrated_models_2 = []
        migrated_test = MigratedTest(id=test_id, migrated_attr=migrated_attr_default)
        expected_migrated_models_2.append(migrated_test)
        expected_migrated_models_2.append(
            MigratedProperty(id=property_id, value=property_value, test=None))
        migrated_references = []
        for n in range(num_references):
            migrated_references.append(
                MigratedReference(
                    id="reference_id_{}".format(n),
                    value="reference_value_{}".format(n)))
        expected_migrated_models_2.extend(migrated_references)
        migrated_subtests = []
        for n in range(num_subtests):
            migrated_subtests.append(
                MigratedSubtest(id="subtest_{}".format(n),
                    test=migrated_test,
                    references=migrated_references[n:n + 2]))
        expected_migrated_models_2.extend(migrated_subtests)

        migrator._connect_models(all_models)

        self.assertEqual(len(migrated_models), len(expected_migrated_models_2))
        for migrated_model, expected_migrated_model in zip(migrated_models, expected_migrated_models_2):
            self.assertTrue(migrated_model.is_equal(expected_migrated_model))

    @staticmethod
    def read_model_file(model_file, models):
        reader = obj_model.io.Reader.get_reader(model_file)()
        return reader.run(model_file, models=models, ignore_sheet_order=True)

    def compare_model(self, model_cls, models, existing_file, migrated_file):
        # compare model_cls in existing_file against model_cls in migrated_file
        # existing_file and migrated_file must use the same models
        existing_wc_model = self.read_model_file(existing_file, models)
        migrated_wc_model = self.read_model_file(migrated_file, models)
        # this follows and compares all refs reachable from model_cls in existing_wc_model and migrated_wc_model
        if 1 < len(existing_wc_model[model_cls]) or 1 < len(migrated_wc_model[model_cls]):
            warnings.warn("might compare unequal models in lists of multiple models")
        existing_model = existing_wc_model[model_cls][0]
        migrated_model = migrated_wc_model[model_cls][0]
        self.assertTrue(existing_model.is_equal(migrated_model))

    def test_path_of_migrated_file(self):
        path_of_migrated_file = Migrator.path_of_migrated_file
        tmp_file = temp_pathname(self, 'model.xlsx')
        tmp_dir = os.path.dirname(tmp_file)
        self.assertEqual(tmp_file, path_of_migrated_file(tmp_file, migrate_in_place=True))
        standard_migrated_filename = os.path.join(tmp_dir, 'model' + Migrator.MIGRATE_SUFFIX + '.xlsx')
        self.assertEqual(standard_migrated_filename, path_of_migrated_file(tmp_file))
        migrate_suffix = '_MIGRATED'
        expected_migrated_filename = os.path.join(tmp_dir, 'model' + migrate_suffix + '.xlsx')
        self.assertEqual(expected_migrated_filename, path_of_migrated_file(tmp_file, migrate_suffix=migrate_suffix))

    def test_write_migrated_file_exception(self):
        tmp_file = temp_pathname(self, 'model.xlsx')
        tmp_dir = os.path.dirname(tmp_file)
        standard_migrated_filename = os.path.join(tmp_dir, 'model' + Migrator.MIGRATE_SUFFIX + '.xlsx')
        open(standard_migrated_filename, 'a')
        with self.assertRaisesRegex(MigratorError, "migrated file '.*' already exists"):
            self.no_change_migrator.write_migrated_file(None, None, tmp_file)

    def test_migrate_without_changes(self):
        no_change_migrator = self.no_change_migrator
        no_change_migrator.full_migrate(self.example_existing_model_copy, migrated_file=self.example_migrated_model)
        ExistingTest = no_change_migrator.existing_defs['Test']
        models = list(no_change_migrator.existing_defs.values())
        # this compares all Models in self.example_existing_model_copy and self.example_migrated_model because it follows the refs from Test
        self.compare_model(ExistingTest, models, self.example_existing_model_copy, self.example_migrated_model)
        self.assert_equal_workbooks(self.example_existing_model_copy, self.example_migrated_model)

        test_suffix = '_MIGRATED_FILE'
        migrated_filename = no_change_migrator.full_migrate(self.example_existing_model_copy, migrate_suffix=test_suffix)
        root, _ = os.path.splitext(self.example_existing_model_copy)
        self.assertEqual(migrated_filename, "{}{}.xlsx".format(root, test_suffix))

    def test_transformations_in_full_migrate(self):
        # make PREPARE_EXISTING_MODELS & MODIFY_MIGRATED_MODELS transformations that invert each other
        def prepare_existing_models(migrator, existing_models):
            # increment the value of Property models
            for existing_model in existing_models:
                if isinstance(existing_model, migrator.existing_defs['Property']):
                    existing_model.value += +1

        def modify_migrated_models(migrator, migrated_models):
            # decrement the value of Property models
            for migrated_model in migrated_models:
                if isinstance(migrated_model, migrator.existing_defs['Property']):
                    migrated_model.value += -1

        transformations = {
            Migrator.PREPARE_EXISTING_MODELS: prepare_existing_models,
            Migrator.MODIFY_MIGRATED_MODELS: modify_migrated_models
        }
        migrator = Migrator(self.existing_defs_path, self.existing_defs_path, transformations=transformations)
        migrator.prepare()
        migrated_file = migrator.full_migrate(self.example_existing_model_copy)

        # test that inverted transformations make no changes
        self.assert_equal_workbooks(self.example_existing_model_copy, migrated_file)

    def test_full_migrate(self):

        # test round-trip existing -> migrated -> existing
        # use schemas without deleted or migrated models so the starting and ending model files are identical
        # but include model and attr renaming so that existing != migrated

        # make existing -> migrated migrator
        existing_2_migrated_migrator = Migrator(self.existing_rt_model_defs_path, self.migrated_rt_model_defs_path,
            renamed_models=self.existing_2_migrated_renamed_models,
            renamed_attributes=self.existing_2_migrated_renamed_attributes)
        existing_2_migrated_migrator.prepare()

        # make migrated -> existing migrator
        migrated_2_existing_migrator = Migrator(self.migrated_rt_model_defs_path, self.existing_rt_model_defs_path,
            renamed_models=self.invert_renaming(self.existing_2_migrated_renamed_models),
            renamed_attributes=self.invert_renaming(self.existing_2_migrated_renamed_attributes))
        migrated_2_existing_migrator.prepare()

        # round trip test of model in tsv file
        # todo: fix
        '''
        existing_2_migrated_migrator.full_migrate(self.example_existing_model_tsv,
            migrated_file=self.existing_2_migrated_migrated_tsv_file)
        migrated_2_existing_migrator.full_migrate(self.existing_2_migrated_migrated_tsv_file,
            migrated_file=self.round_trip_migrated_tsv_file)
        self.assert_equal_workbooks(self.example_existing_model_tsv, self.round_trip_migrated_tsv_file)
        '''

        # round trip test of model in xlsx file
        tmp_existing_2_migrated_xlsx_file = os.path.join(self.tmp_model_dir, 'existing_2_migrated_xlsx_file.xlsx')
        existing_2_migrated_migrator.full_migrate(self.example_existing_rt_model_copy,
            migrated_file=tmp_existing_2_migrated_xlsx_file)
        round_trip_migrated_xlsx_file = migrated_2_existing_migrator.full_migrate(tmp_existing_2_migrated_xlsx_file)
        self.assert_equal_workbooks(self.example_existing_rt_model_copy, round_trip_migrated_xlsx_file)

    def run_check_model_test(self, model, model_def, attr_name, default_value):
        # test _check_model() by setting an attribute to its default
        model_copy = model.copy()
        setattr(model_copy, attr_name, default_value)
        self.assertIn("'{}' lack(s) '{}'".format(model_def.__name__, attr_name),
            self.good_migrator._check_model(model_copy, model_def)[0])
        return model_copy

    def test_check_model_and_models(self):

        good_related = self.GoodRelatedCls(
            id='id_1',
            num=123)
        good_existing = self.GoodExisting(
            id='id_2',
            attr_a='hi mom',
            unmigrated_attr='x',
            np_array=numpy.array([1, 2]),
            related=good_related
        )
        all_models = [good_related, good_existing]
        self.assertEqual([], self.good_migrator._check_model(good_related, self.GoodRelatedCls))
        all_models.append(self.run_check_model_test(good_related, self.GoodRelatedCls, 'id', ''))
        all_models.append(self.run_check_model_test(good_related, self.GoodRelatedCls, 'num', None))

        self.assertEqual([], self.good_migrator._check_model(good_existing, self.GoodExisting))
        all_models.append(self.run_check_model_test(good_existing, self.GoodExisting, 'np_array', None))
        all_models.append(self.run_check_model_test(good_existing, self.GoodExisting, 'related', None))
        all_models.append(self.run_check_model_test(good_existing, self.GoodExisting, 'related', None))

        inconsistencies = self.good_migrator._check_models(all_models)
        self.assertEqual(len(inconsistencies), 4)
        self.assertEqual(len([problem for problem in inconsistencies if problem.startswith('1')]), 3)
        self.assertEqual(len([problem for problem in inconsistencies if problem.startswith('2')]), 1)

    def test_migrate_in_place(self):
        self.migrator.prepare()
        # migrate to example_migrated_model
        example_migrated_model = temp_pathname(self, 'example_migrated_model.xlsx')
        self.migrator.full_migrate(self.example_existing_model_copy, migrated_file=example_migrated_model)
        # migrate to self.example_existing_model_copy
        self.migrator.full_migrate(self.example_existing_model_copy, migrate_in_place=True)

        # validate
        self.assert_equal_workbooks(example_migrated_model, self.example_existing_model_copy)

    def test_exceptions(self):
        bad_module = os.path.join(self.tmp_dir, 'bad_module.py')
        f = open(bad_module, "w")
        f.write('bad python')
        f.close()
        migrator = Migrator(bad_module, self.migrated_defs_path)
        with self.assertRaisesRegex(MigratorError, "cannot be imported and exec'ed"):
            migrator._load_defs_from_files()

    def test_generate_wc_lang_migrator(self):
        migrator = Migrator.generate_wc_lang_migrator()
        self.assertIsInstance(migrator, Migrator)
        self.assertTrue(callable(migrator.transformations[Migrator.PREPARE_EXISTING_MODELS]))

        same_defs_migrator = Migrator.generate_wc_lang_migrator(existing_defs_file=self.wc_lang_schema_existing,
            migrated_defs_file=self.wc_lang_schema_existing)
        same_defs_migrator.prepare()
        # migrate self.wc_lang_no_model_attrs twice with the generate_wc_lang_migrator
        # the 1st migration adds model attributes, & the 2nd tests that they exist
        wc_lang_model_with_model_attrs = same_defs_migrator.full_migrate(self.wc_lang_no_model_attrs)
        self.assert_differing_workbooks(self.wc_lang_no_model_attrs, wc_lang_model_with_model_attrs)
        migrated_file = same_defs_migrator.full_migrate(wc_lang_model_with_model_attrs)
        self.assert_equal_workbooks(wc_lang_model_with_model_attrs, migrated_file)

        bad_kwargs = dict(existing_defs_file='existing_defs.py', migrated_defs_file='migrated_defs.py',
            transformations='foo')
        with self.assertRaisesRegex(MigratorError, "'transformations' entry not allowed in kwargs:\\n.+"):
            Migrator.generate_wc_lang_migrator(**bad_kwargs)

        # raise exception for num models != 1 by creating PREPARE_EXISTING_MODELS that deletes the model
        current_prepare_existing_models_fun = same_defs_migrator.transformations[Migrator.PREPARE_EXISTING_MODELS]
        def delete_model_and_call_current(migrator, existing_models):
            model_cls = migrator.existing_defs['Model']
            existing_models = [model for model in existing_models if model.__class__ != model_cls]
            current_prepare_existing_models_fun(migrator, existing_models)
        same_defs_migrator.transformations[Migrator.PREPARE_EXISTING_MODELS] = delete_model_and_call_current
        with self.assertRaisesRegex(MigratorError,
            "existing models must have 1 Model instance, but \\d are present"):
            same_defs_migrator.full_migrate(self.wc_lang_no_model_attrs)

    def test_run(self):
        migrated_files = self.no_change_migrator.run([self.example_existing_model_copy])
        self.assert_equal_workbooks(self.example_existing_model_copy, migrated_files[0])

    def test_str(self):
        self.wc_lang_changes_migrator.prepare()
        str_value = str(self.wc_lang_changes_migrator)
        for attr in Migrator.SCALAR_ATTRS + Migrator.COLLECTIONS_ATTRS:
            self.assertIn(attr, str_value)
        for map_name in ['existing_defs', 'migrated_defs', 'models_map']:
            migrator_map = getattr(self.wc_lang_changes_migrator, map_name)
            for key in migrator_map:
                self.assertIn(key, str_value)

        empty_migrator = Migrator()
        str_value = str(empty_migrator)
        for attr in Migrator.SCALAR_ATTRS:
            self.assertNotRegex(str_value, '^' + attr + '$')


# @unittest.skip("speed up testing")
class TestMigrationSpec(MigrationFixtures):

    def setUp(self):
        super().setUp()

    def tearDown(self):
        super().tearDown()

    def test_prepare(self):
        try:
            self.migration_spec.prepare()
        except MigratorError:
            self.fail("prepare() raised MigratorError unexpectedly.")

        setattr(self.migration_spec, 'disallowed_attr', 'bad')
        with self.assertRaises(MigratorError):
            self.migration_spec.prepare()

    def test_load(self):
        temp_bad_config_example = os.path.join(self.tmp_dir, 'bad_config_example.yaml')
        with open(temp_bad_config_example, 'w') as file:
            file.write(u'migration:\n')
            file.write(u'    obj_defs: [small_migrated_rt.py, small_existing_rt.py]\n')
        with self.assertRaisesRegex(MigratorError, re.escape("disallowed attribute(s) found: {'obj_defs'}")):
            MigrationSpec.load(temp_bad_config_example)

        migration_specs = MigrationSpec.load(self.config_file)
        self.assertIn('migration_with_renaming', migration_specs)

    def test_get_migrations_config(self):
        migration_specs = MigrationSpec.get_migrations_config(self.config_file)
        self.assertIn('migration_with_renaming', migration_specs)

        with self.assertRaisesRegex(MigratorError, "could not read migration config file: "):
            MigrationSpec.get_migrations_config(os.path.join(self.fixtures_path, 'no_file.yaml'))

        # test detecting bad yaml
        bad_yaml = os.path.join(self.tmp_dir, 'bad_yaml.yaml')
        f = open(bad_yaml, "w")
        f.write("unbalanced brackets: ][")
        f.close()
        with self.assertRaisesRegex(MigratorError, r"could not parse YAML migration config file: '\S+'"):
            MigrationSpec.get_migrations_config(bad_yaml)

    def test_validate(self):
        self.assertFalse(self.migration_spec.validate())
        md = copy.deepcopy(self.migration_spec)
        setattr(md, 'disallowed_attr', 'bad')
        self.assertEqual(md.validate(), ["disallowed attribute(s) found: {'disallowed_attr'}"])

        for attr in MigrationSpec._REQUIRED_ATTRS:
            md = copy.deepcopy(self.migration_spec)
            setattr(md, attr, None)
            self.assertEqual(md.validate(), ["missing required attribute '{}'".format(attr)])
            delattr(md, attr)
            self.assertEqual(md.validate(), ["missing required attribute '{}'".format(attr)])

        md = copy.deepcopy(self.migration_spec)
        md.schema_files = []
        self.assertEqual(md.validate(),
            ["schema_files must contain at least 2 model definitions, but it has only 0"])

        for renaming_list in MigrationSpec._CHANGES_LISTS:
            md = copy.deepcopy(self.migration_spec)
            setattr(md, renaming_list, [[], []])
            error = md.validate()[0]
            self.assertRegex(error,
                r"{} must have 1 .+ 1 migration.+ schema_files, but it has \d".format(renaming_list))

        for renaming_list in MigrationSpec._CHANGES_LISTS:
            md = copy.deepcopy(self.migration_spec)
            setattr(md, renaming_list, None)
            self.assertFalse(md.validate())

        for renaming_list in MigrationSpec._CHANGES_LISTS:
            md = copy.deepcopy(self.migration_spec)
            setattr(md, renaming_list, [None])
            self.assertEqual(md.validate(), [])

        bad_renamed_models_examples = [3, [('foo')], [('foo', 1)], [(1, 'bar')]]
        for bad_renamed_models in bad_renamed_models_examples:
            md = copy.deepcopy(self.migration_spec)
            md.seq_of_renamed_models = [bad_renamed_models]
            error = md.validate()[0]
            self.assertTrue(error.startswith(
                "seq_of_renamed_models must be None, or a list of lists of pairs of strs"))

        bad_renamed_attributes_examples = [
            [[('A', 'att1'), ('B', 'att2', 'extra')]],
            [[('A', 'att1'), ('B')]],
            [[(1, 'att1'), ('B', 'att2')]],
            [[('A', 2), ('B', 'att2')]],
            [3],
            ]
        for bad_renamed_attributes in bad_renamed_attributes_examples:
            md = copy.deepcopy(self.migration_spec)
            md.seq_of_renamed_attributes = [bad_renamed_attributes]
            error = md.validate()[0]
            self.assertTrue(error.startswith(
                "seq_of_renamed_attributes must be None, or a list of lists of pairs of pairs of strs"))

        md = copy.deepcopy(self.migration_spec)
        md.existing_files = []
        error = md.validate()[0]
        self.assertEqual(error, "at least one existing file must be specified")

        md = copy.deepcopy(self.migration_spec)
        md.migrated_files = []
        error = md.validate()[0]
        self.assertRegex(error, r"existing_files and migrated_files must .+ but they have \d and \d entries, .+")

        md.migrated_files = ['file_1', 'file_2']
        error = md.validate()[0]
        self.assertRegex(error, r"existing_files and migrated_files must .+ but they have \d and \d entries, .+")

        md = copy.deepcopy(self.migration_spec)
        md.migrator = 'foo'
        error = md.validate()[0]
        self.assertRegex(error, r"'migrator' must be an element of \{.+\}")

    def test_standardize(self):
        md = MigrationSpec('name', schema_files=['f1.py', 'f2.py'])
        md.standardize()
        for renaming in MigrationSpec._CHANGES_LISTS:
            self.assertEqual(getattr(md, renaming), [None])
        for attr in ['existing_files', 'migrated_files']:
            self.assertEqual(getattr(md, attr), None)

        migration_specs = MigrationSpec.get_migrations_config(self.config_file)

        md = migration_specs['simple_migration']
        migrations_config_file_dir = os.path.dirname(md.migrations_config_file)
        md.standardize()
        for renaming in MigrationSpec._CHANGES_LISTS:
            self.assertEqual(len(getattr(md, renaming)), len(md.schema_files) - 1)
            self.assertEqual(getattr(md, renaming), [None])
        for file_list in ['existing_files', 'schema_files']:
            for file in getattr(md, file_list):
                self.assertEqual(os.path.dirname(file), migrations_config_file_dir)

        md = migration_specs['migration_with_renaming']
        md.standardize()
        expected_seq_of_renamed_models = [[['Test', 'MigratedTest']], [['MigratedTest', 'Test']]]
        self.assertEqual(md.seq_of_renamed_models, expected_seq_of_renamed_models)
        expected_1st_renamed_attributes = [
            (('Test', 'existing_attr'), ('MigratedTest', 'migrated_attr')),
            (('Property', 'value'), ('Property', 'migrated_value')),
            (('Subtest', 'references'), ('Subtest', 'migrated_references'))
        ]
        self.assertEqual(md.seq_of_renamed_attributes[0], expected_1st_renamed_attributes)

        migration_specs = MigrationSpec.get_migrations_config(self.bad_migrations_config)
        md = migration_specs['migration_with_empty_renaming_n_migrated_files']
        md.standardize()
        self.assertEqual(md.seq_of_renamed_attributes[1], None)
        self.assertEqual(os.path.dirname(md.migrated_files[0]), migrations_config_file_dir)

    def test_expected_migrated_files(self):
        self.assertEqual(self.migration_spec.expected_migrated_files(),
            [Migrator.path_of_migrated_file(self.migration_spec.existing_files[0])])
        md = copy.deepcopy(self.migration_spec)
        tmp_file = temp_pathname(self, 'model_new.xlsx')
        md.migrated_files = [tmp_file]
        self.assertEqual(md.expected_migrated_files(), [tmp_file])

    def test_str(self):
        migration_specs = MigrationSpec.get_migrations_config(self.config_file)
        name = 'migration_with_renaming'
        migration_spec = migration_specs[name]
        migration_spec_str = str(migration_spec)
        self.assertIn(name, migration_spec_str)
        self.assertIn(str(migration_spec.schema_files), migration_spec_str)


# @unittest.skip("speed up testing")
class TestMigrationController(MigrationFixtures):

    def setUp(self):
        super().setUp()

    def tearDown(self):
        super().tearDown()

    def test_migrate_over_schema_sequence(self):
        bad_migration_spec = copy.deepcopy(self.migration_spec)
        del bad_migration_spec.migrator
        with self.assertRaises(MigratorError):
            MigrationController.migrate_over_schema_sequence(bad_migration_spec)

        # round-trip test: existing -> migrated -> migrated -> existing
        schema_files = [self.existing_rt_model_defs_path, self.migrated_rt_model_defs_path,
            self.migrated_rt_model_defs_path, self.existing_rt_model_defs_path]
        migrated_2_existing_renamed_models = self.invert_renaming(self.existing_2_migrated_renamed_models)
        migrated_2_existing_renamed_attributes = self.invert_renaming(self.existing_2_migrated_renamed_attributes)
        seq_of_renamed_models = [self.existing_2_migrated_renamed_models, [], migrated_2_existing_renamed_models]
        seq_of_renamed_attributes = [self.existing_2_migrated_renamed_attributes, [], migrated_2_existing_renamed_attributes]

        migrated_filename = temp_pathname(self, 'example_existing_model_rt_migrated.xlsx')
        migration_spec = MigrationSpec('name',
            existing_files=[self.example_existing_rt_model_copy],
            schema_files=schema_files,
            seq_of_renamed_models=seq_of_renamed_models,
            seq_of_renamed_attributes=seq_of_renamed_attributes,
            migrated_files=[migrated_filename])
        migration_spec.prepare()
        _, migrated_filenames = MigrationController.migrate_over_schema_sequence(migration_spec)
        self.assert_equal_workbooks(self.example_existing_rt_model_copy, migrated_filenames[0])

        self.migration_spec.prepare()
        with self.assertWarnsRegex(UserWarning,
            r"\d+ instance\(s\) of existing model '\S+' lack\(s\) '\S+' non-default value"):
            MigrationController.migrate_over_schema_sequence(self.migration_spec)

    def put_tmp_migrated_file_in_migration_spec(self, migration_spec, name):
        migrated_filename = temp_pathname(self, name)
        migration_spec.migrated_files = [migrated_filename]
        return migrated_filename

    def test_migrate_from_spec(self):
        migration_specs = MigrationSpec.load(self.config_file)

        migration_spec = migration_specs['simple_migration']
        tmp_migrated_filename = self.put_tmp_migrated_file_in_migration_spec(migration_spec, 'migration.xlsx')
        migrated_filenames = MigrationController.migrate_from_spec(migration_spec)
        self.assertEqual(tmp_migrated_filename, migrated_filenames[0])
        self.assert_equal_workbooks(migration_spec.existing_files[0], migrated_filenames[0])

        migration_spec = migration_specs['migration_with_renaming']
        self.put_tmp_migrated_file_in_migration_spec(migration_spec, 'round_trip_migrated_xlsx_file.xlsx')
        round_trip_migrated_xlsx_files = MigrationController.migrate_from_spec(migration_spec)
        self.assert_equal_workbooks(migration_spec.existing_files[0], round_trip_migrated_xlsx_files[0])

        migration_spec = migration_specs['wc_lang_migration']
        self.put_tmp_migrated_file_in_migration_spec(migration_spec, 'example-wc_lang-model_migrated.xlsx')
        round_trip_migrated_wc_lang_files = MigrationController.migrate_from_spec(migration_spec)
        self.assert_equal_workbooks(migration_spec.existing_files[0], round_trip_migrated_wc_lang_files[0])

    def test_migrate_from_config(self):
        # these are round-trip migrations

        # Prepare to remove the migrated_files so they do not contaminate tests/fixtures/migrate.
        # An alternative but more complex approach would be to copy the YAML config file into
        # a temp dir along with the files and directories (packages) it references.
        for migration_spec in MigrationSpec.load(self.config_file).values():
            for expected_migrated_file in migration_spec.expected_migrated_files():
                self.files_to_delete.add(expected_migrated_file)

        results = MigrationController.migrate_from_config(self.config_file)
        for migration_spec, migrated_files in results:
            self.assert_equal_workbooks(migration_spec.existing_files[0], migrated_files[0])

    @unittest.skip("optional performance test")
    def test_migrate_from_config_performance(self):
        # test performance
        for migration_spec in MigrationSpec.load(self.config_file).values():
            for expected_migrated_file in migration_spec.expected_migrated_files():
                self.files_to_delete.add(expected_migrated_file)

        out_file = temp_pathname(self, "profile_out.out")
        locals = {'self':self, 'MigrationController':MigrationController}
        cProfile.runctx('results = MigrationController.migrate_from_config(self.config_file)', {},
            locals, filename=out_file)
        profile = pstats.Stats(out_file)
        print("Profile for 'MigrationController.migrate_from_config(self.config_file)'")
        profile.strip_dirs().sort_stats('cumulative').print_stats(20)

    def test_wc_lang_migration(self):
        # round-trip migrate through changed schema

        # Process for testing a round-trip migration of a wc_lang model that lacks 'model' attributes
        # 1: create model file with 'model' attributes by migrating to tmp file w generate_wc_lang_migrator
        # 2: use the tmp migrated file in a round-trip migration with migrations that invert each other
        fully_instantiated_wc_lang_model = temp_pathname(self, 'fully_instantiated_wc_lang_model.xlsx')
        fully_instantiate_migration = MigrationSpec(
            "1: create fully instantiated model with 'model' attributes: migrate model from existing wc_lang core to itself",
            migrator='wc_lang',
            existing_files=[self.wc_lang_model_copy],
            schema_files=[self.wc_lang_schema_existing, self.wc_lang_schema_existing],
            migrated_files=[fully_instantiated_wc_lang_model])
        fully_instantiate_migration.prepare()
        MigrationController.migrate_over_schema_sequence(fully_instantiate_migration)

        rt_through_changes_migration = MigrationSpec(
            "2: round trip migration with migrations that invert each other",
            existing_files=[fully_instantiated_wc_lang_model],
            schema_files=[self.wc_lang_schema_existing, self.wc_lang_schema_modified,
                self.wc_lang_schema_existing],
            seq_of_renamed_models=[[('Parameter', 'ParameterRenamed')], [('ParameterRenamed', 'Parameter')]])
        rt_through_changes_migration.prepare()
        _, rt_through_changes_wc_lang_models = \
            MigrationController.migrate_over_schema_sequence(rt_through_changes_migration)
        # validate round trip
        self.assert_equal_workbooks(fully_instantiated_wc_lang_model, rt_through_changes_wc_lang_models[0])


def internet_connected():
    # return True if the internet (actually www.google.com) is connected, false otherwise
    try:
        # connect to the host -- tells us if the host is actually reachable
        socket.create_connection(("www.google.com", 80))
        return True
    except OSError:
        pass
    return False


class AutoMigrationFixtures(unittest.TestCase):

    @classmethod
    def make_tmp_dir(cls):
        return mkdtemp(dir=cls.tmp_dir)

    @classmethod
    def setUpClass(cls):
        cls.tmp_dir = mkdtemp()
        cls.test_repo_url = 'https://github.com/KarrLab/test_repo'
        # get these repos once for the TestCase to speed up tests
        cls.git_repo = GitRepo(cls.test_repo_url)
        cls.known_hash = 'ab34419496756675b6e8499e0948e697256f2698'
        cls.known_hash_ba1f9d3 = 'ba1f9d33a3e18a74f79f41903e7e88e118134d5f'
        cls.test_repo_clean_url = 'https://github.com/KarrLab/test_repo_clean'
        cls.git_test_repo_clean = GitRepo(cls.test_repo_clean_url)

        cls.totally_empty_git_repo = GitRepo()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp_dir)
        # remove the GitRepo so that its temp_dirs get deleted
        del cls.git_repo

    def setUp(self):
        # create empty repo containing a commit and a migrations directory
        repo_dir = self.make_tmp_dir()
        repo = git.Repo.init(repo_dir)
        empty_file = os.path.join(repo_dir, 'file')
        open(empty_file, 'wb').close()
        repo.index.add([empty_file])
        repo.index.commit("initial commit")
        self.empty_git_repo = GitRepo(repo_dir)
        Path(self.empty_git_repo.migrations_dir()).mkdir()


@unittest.skipUnless(internet_connected(), "Internet not connected")
class TestSchemaChanges(AutoMigrationFixtures):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.schema_changes = SchemaChanges(self.git_repo)
        self.test_data = dict(
            commit_hash='a'*40,
            renamed_models=[('Foo', 'FooNew')],
            renamed_attributes=[('Foo', 'Attr'), ('FooNew', 'AttrNew')],
            transformations_file=''
        )
        self.empty_schema_changes = SchemaChanges(self.empty_git_repo)
        self.empty_migrations_dir = self.empty_schema_changes.git_repo.migrations_dir()

    def test_get_date_timestamp(self):
        timestamp = SchemaChanges.get_date_timestamp()
        # good for 81 years:
        self.assertTrue(timestamp.startswith('20'))
        self.assertEqual(len(timestamp), 19)

    def test_all_schema_changes_files(self):
        files = SchemaChanges.all_schema_changes_files(self.git_repo.migrations_dir())
        self.assertEqual(len(files), 6)
        an_expected_file = os.path.join(self.git_repo.migrations_dir(),
            'schema_changes_2019-02-13-14-05-42_ba1f9d3.yaml')
        self.assertTrue(an_expected_file in files)

        with self.assertRaisesRegex(MigratorError, r"no schema changes files in '\S+'"):
            SchemaChanges.all_schema_changes_files(self.empty_git_repo.migrations_dir())

    def test_all_schema_changes_with_commits(self):
        all_schema_changes_with_commits = SchemaChanges.all_schema_changes_with_commits
        errors, schema_changes = all_schema_changes_with_commits(self.git_repo)
        self.assertEqual(len(errors), 5)
        self.assertEqual(len(schema_changes), 1)
        self.assertEqual(schema_changes[0].schema_changes_file,
            SchemaChanges.find_file(self.git_repo, self.known_hash_ba1f9d3))

    def test_find_file(self):
        schema_changes_file = SchemaChanges.find_file(self.git_repo, self.known_hash_ba1f9d3)
        self.assertEqual(os.path.basename(schema_changes_file),
            'schema_changes_2019-02-13-14-05-42_ba1f9d3.yaml')

        with self.assertRaisesRegex(MigratorError, r"no schema changes file in '.+' for hash \S+"):
            SchemaChanges.find_file(self.git_repo, 'not_a_hash_not_a_hash_not_a_hash_not_a_h')

        migrations_dir = self.git_repo.migrations_dir()
        self.schema_changes.make_template(migrations_dir)
        time.sleep(2)
        self.schema_changes.make_template(migrations_dir)
        with self.assertRaisesRegex(MigratorError,
            r"multiple schema changes files in '.+' for hash \S+"):
            SchemaChanges.find_file(self.git_repo, self.schema_changes.get_hash())

        with self.assertRaisesRegex(MigratorError,
            r"hash prefix in schema changes filename '.+' inconsistent with hash in file: '\S+'"):
            SchemaChanges.find_file(self.git_repo, 'a'*40)

        with self.assertRaisesRegex(MigratorError,
            "the hash in '.+', which is '.+', isn't the hash of a commit"):
            SchemaChanges.find_file(self.git_repo, 'abcdefabcdefabcdefabcdefabcdefabcdefabcd')

    def test_generate_filename(self):
        filename = self.schema_changes.generate_filename()
        self.assertTrue(filename.endswith('.yaml'))
        self.assertTrue(2 <= len(filename.split('_')))

    def test_make_template(self):
        pathname = self.empty_schema_changes.make_template(self.empty_migrations_dir)
        data = yaml.load(open(pathname, 'r'))
        for attr in ['renamed_models', 'renamed_attributes']:
            self.assertEqual(data[attr], [])
        for attr in ['commit_hash', 'transformations_file']:
            self.assertIsInstance(data[attr], str)

        # quickly create another, which will likely have the same timestamp
        with self.assertRaisesRegex(MigratorError, "schema changes file '.+' already exists"):
            self.empty_schema_changes.make_template(self.empty_migrations_dir)

    def test_import_transformations(self):
        find_file = SchemaChanges.find_file
        schema_changes_file = find_file(self.git_repo, self.known_hash_ba1f9d3)
        schema_changes = SchemaChanges.generate_instance(schema_changes_file)
        transformations = schema_changes.import_transformations()
        self.assertIsInstance(transformations, dict)
        self.assertEqual(transformations['PREPARE_EXISTING_MODELS'], transformations['MODIFY_MIGRATED_MODELS'])

        schema_changes_file = os.path.join(self.git_repo.migrations_dir(),
            'schema_changes_no-transformations-file_aaaaaaa.yaml')
        schema_changes = SchemaChanges.generate_instance(schema_changes_file)
        transformations = schema_changes.import_transformations()
        self.assertTrue(transformations is None)

        schema_changes_file = os.path.join(self.git_repo.migrations_dir(),
            'schema_changes_bad-transformations_ccccccc.yaml')
        schema_changes = SchemaChanges.generate_instance(schema_changes_file)
        with self.assertRaisesRegex(MigratorError, "'.+' does not have a 'transformations' attribute"):
            schema_changes.import_transformations()

        schema_changes_file = os.path.join(self.git_repo.migrations_dir(),
            'schema_changes_bad-transformations_bbbbbbb.yaml')
        schema_changes = SchemaChanges.generate_instance(schema_changes_file)
        with self.assertRaisesRegex(MigratorError, "transformations should be a dict, but it is a.+"):
            schema_changes.import_transformations()

    def test_load(self):
        schema_changes_file = SchemaChanges.find_file(self.git_repo, self.known_hash_ba1f9d3)
        schema_changes = SchemaChanges.load(schema_changes_file)
        expected_schema_changes = dict(
            commit_hash=self.known_hash_ba1f9d3,
            renamed_attributes=[],
            renamed_models=[['Test', 'TestNew']],
            schema_changes_file=schema_changes_file,
            transformations_file='transformations_ba1f9d3.py'
        )
        self.assertEqual(schema_changes, expected_schema_changes)

        no_such_file = 'no such file'
        with self.assertRaisesRegex(MigratorError, "could not read schema changes file: '.+'"):
            SchemaChanges.load(no_such_file)

        # detect bad yaml
        temp_dir = tempfile.TemporaryDirectory()
        bad_yaml = os.path.join(temp_dir.name, 'bad_yaml.yaml')
        with open(bad_yaml, "w") as f:
            f.write("unbalanced brackets: ][")
        with self.assertRaisesRegex(MigratorError,
            r"could not parse YAML schema changes file: '\S+':"):
            SchemaChanges.load(bad_yaml)

        with open(bad_yaml, "w") as f:
            f.write("wrong_attr: []")
        with self.assertRaisesRegex(MigratorError,
            r"schema changes file must have a dict with the attributes in \S+._CHANGES_FILE_ATTRS: .+"):
            SchemaChanges.load(bad_yaml)

        # make the hash too short
        self.test_data['commit_hash'] = 'a'
        with open(bad_yaml, "w") as f:
            f.write(yaml.dump(self.test_data))
        with self.assertRaisesRegex(MigratorError,
            "schema changes file '.+' does not have a proper hash"):
            SchemaChanges.load(bad_yaml)

        pathname = self.empty_schema_changes.make_template(self.empty_migrations_dir)
        with self.assertRaisesRegex(MigratorError,
            r"schema changes file is empty \(an unmodified template\): '.+'"):
            SchemaChanges.load(pathname)

    def test_generate_instance(self):
        temp_dir = tempfile.TemporaryDirectory()
        good_yaml = os.path.join(temp_dir.name, 'good_yaml.yaml')
        with open(good_yaml, "w") as f:
            f.write(yaml.dump(self.test_data))
        schema_changes = SchemaChanges.generate_instance(good_yaml)
        for attr in SchemaChanges._CHANGES_FILE_ATTRS:
            self.assertEqual(getattr(schema_changes, attr), self.test_data[attr])

    def test_str(self):
        for attr in SchemaChanges._ATTRIBUTES:
            self.assertIn(attr, str(self.schema_changes))
    '''
    # todo: wait until I decide what to do about comparing GitRepos
    def test_eq(self):
        self.assertTrue(self.schema_changes != 1)
        schema_changes_copy = copy.deepcopy(self.schema_changes)
        self.assertEqual(self.schema_changes, schema_changes_copy)
        schema_changes_copy.commit_hash += '_end'
        self.assertTrue(self.schema_changes != schema_changes_copy)
    '''

@unittest.skipUnless(internet_connected(), "Internet not connected")
class TestGitRepo(AutoMigrationFixtures):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

    def setUp(self):
        self.repo_root = self.git_repo.repo_dir
        self.no_such_hash = 'ab34419496756675b6e8499e0948e697256f2699'

    def test_init(self):
        self.assertIsInstance(self.totally_empty_git_repo, GitRepo)
        self.assertIsInstance(self.git_repo.repo, git.Repo)
        self.assertEqual(self.repo_root, self.git_repo.repo_dir)
        git_repo = GitRepo(self.git_repo.repo_dir)
        self.assertIsInstance(git_repo.repo, git.Repo)
        with self.assertRaisesRegex(MigratorError, "instantiating a git.Repo from directory '.+' failed"):
            GitRepo(self.tmp_dir)

    def test_get_temp_dir(self):
        self.assertTrue(os.path.isdir(self.totally_empty_git_repo.get_temp_dir()))

        # check that TemporaryDirectory is destroyed when a GitRepo is destroyed
        def make_git_repo():
            temp_git_repo = GitRepo()
            temp_git_repo.clone_repo_from_url(self.test_repo_url)
            return [dir.name for dir in temp_git_repo.temp_dirs]
        dirs = make_git_repo()
        self.assertTrue(len(dirs))
        for d in dirs:
            self.assertFalse(os.path.isdir(d))

    def test_clone_repo_from_url(self):
        repo, dir = self.totally_empty_git_repo.clone_repo_from_url(self.test_repo_url)
        self.assertIsInstance(repo, git.Repo)
        self.assertTrue(os.path.isdir(os.path.join(dir, '.git')))
        repo, dir = self.totally_empty_git_repo.clone_repo_from_url(self.test_repo_url, directory=self.make_tmp_dir())
        self.assertTrue(os.path.isdir(os.path.join(dir, '.git')))

        bad_dir = '/asdfdsf/no such dir'
        with self.assertRaisesRegex(MigratorError, "'.+' is not a directory"):
            self.totally_empty_git_repo.clone_repo_from_url(self.test_repo_url, directory=bad_dir)

        bad_url = 'http://www.ibm.com/nothing_here'
        with self.assertRaisesRegex(MigratorError, "repo cannot be cloned from '.+'"):
            self.totally_empty_git_repo.clone_repo_from_url(bad_url)

    def test_migrations_dir(self):
        self.assertTrue(os.path.isdir(self.git_repo.migrations_dir()))
        self.assertEqual(os.path.basename(self.git_repo.migrations_dir()),
            AutomatedMigration._MIGRATIONS_DIRECTORY)

    def test_repo_name(self):
        self.assertEqual(self.git_repo.repo_name(), 'test_repo')
        self.assertEqual(self.totally_empty_git_repo.repo_name(), GitRepo._NAME_UNKNOWN)
        tmp_git_repo = GitRepo(self.git_repo.repo_dir)
        self.assertIsInstance(tmp_git_repo.repo_name(), str)

    def test_latest_commit(self):
        self.assertIsInstance(self.git_repo.latest_commit(), git.objects.commit.Commit)

    def test_latest_hash(self):
        # todo: test with a frozen repo whose hash is known
        commit_hash = self.git_repo.latest_hash()
        self.assertIsInstance(commit_hash, str)
        self.assertEqual(len(commit_hash), 40)

    def test_get_commit(self):
        commit = self.git_repo.get_commit(self.known_hash)
        self.assertIsInstance(commit, git.objects.commit.Commit)
        self.assertTrue(self.git_repo.get_commit(self.no_such_hash) is None)

    def test_commits_as_graph(self):
        commit_DAG = self.git_repo.commits_as_graph()
        self.assertIsInstance(commit_DAG, nx.classes.digraph.DiGraph)

    def test_get_hash(self):
        # todo: test with a frozen repo whose hash is known
        commit_hash = GitRepo.get_hash(self.git_repo.latest_commit())
        self.assertIsInstance(commit_hash, str)
        self.assertEqual(len(commit_hash), 40)

    def test_checkout_commit(self):
        self.git_repo.checkout_commit(self.git_repo.latest_commit())
        self.assertEqual(str(self.git_repo.repo.head.commit), self.git_repo.latest_commit().hexsha)
        self.git_repo.checkout_commit(self.known_hash)
        self.assertEqual(self.git_repo.repo.head.commit.hexsha, self.known_hash)

        with self.assertRaisesRegex(MigratorError, r"checkout of '\S+' to commit '\S+' failed"):
            self.git_repo.checkout_commit(self.no_such_hash)

    def check_dependency(self, sequence, DAG):
        # check that sequence satisfies "any nodes u, v with a path u -> ... -> v in the DAG appear in
        # the same order in the sequence"
        sequence.reverse()
        for i in range(len(sequence)):
            u = sequence[i]
            for j in range(i+1, len(sequence)):
                v = sequence[j]
                if has_path(DAG, v, u):
                    self.fail("{} @ {} precedes {} @ {} in sequence, but DAG "
                        "has a path {} -> {}".format(u, i, v, j, v, u))

    def test_commit_seq_with_schema_changes(self):
        totally_empty_git_repo = self.totally_empty_git_repo
        # to simplify initial tests of commit_seq_with_schema_changes use integers, rather than commits
        single_path_edges = [(2, 1), (3, 2), (4, 3), (5, 4)]
        totally_empty_git_repo.commit_DAG = nx.DiGraph(single_path_edges)
        sequence = totally_empty_git_repo.commit_seq_with_schema_changes([4, 1, 2])
        only_possible_sequence = [1, 2, 4]
        self.assertEqual(sequence, only_possible_sequence)

        multi_path_edges = [(2, 1), (3, 2), (7, 3), (8, 7), (4, 2), (6, 4), (5, 4), (6, 5), (7, 6)]
        totally_empty_git_repo.commit_DAG = nx.DiGraph(multi_path_edges)
        n_tests = 20
        for _ in range(n_tests):
            first = 1
            stop = 9
            population = range(first, stop)
            commits_to_migrate = random.sample(population, random.choice(range(2, stop - first + 1)))
            sequence = totally_empty_git_repo.commit_seq_with_schema_changes(commits_to_migrate)
            self.check_dependency(sequence, totally_empty_git_repo.commit_DAG)

        # create a topological sort of 5 test_repo commits
        self.git_repo.commit_DAG = self.git_repo.commits_as_graph()
        commits_to_migrate = random.sample(self.git_repo.commit_DAG.nodes, 5)
        sequence = self.git_repo.commit_seq_with_schema_changes(commits_to_migrate)
        self.check_dependency(sequence, self.git_repo.commit_DAG)


@unittest.skipUnless(internet_connected(), "Internet not connected")
class TestAutomatedMigration(AutoMigrationFixtures):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

    def setUp(self):
        self.clean_automated_migration = AutomatedMigration(
            **dict(data_repo_location=self.test_repo_clean_url,
                data_config_file_basename='automated_migration_config-test_repo_clean.yaml'))
        self.test_repo_clean_fixtures = self.clean_automated_migration.data_git_repo.fixtures_dir()
        self.buggy_automated_migration = AutomatedMigration(
            **dict(data_repo_location=self.test_repo_url,
                data_config_file_basename='automated_migration_config-test_repo.yaml'))

        self.fixtures_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'migrate')
        self.wc_lang_model = os.path.join(self.fixtures_path, 'example-wc_lang-model.xlsx')

    def test_make_template_config_file(self):
        path = AutomatedMigration.make_template_config_file(self.git_repo, 'test_repo_clean')

        # check the file at path
        data = yaml.load(open(path, 'r'))
        for name, config_attr in AutomatedMigration._CONFIG_ATTRIBUTES.items():
            if name == 'migrator':
                self.assertEqual(data[name], MigrationSpec.DEFAULT_MIGRATOR)
                continue
            attr_type, _, _ = config_attr
            if attr_type == 'list':
                self.assertEqual(data[name], [])
            elif attr_type == 'str':
                self.assertEqual(data[name], '')

        with self.assertRaisesRegex(MigratorError,
            "automated migration configuration file '.+' already exists"):
            AutomatedMigration.make_template_config_file(self.git_repo, 'test_repo_clean')

        remove_silently(path)

    def test_load_config_file(self):

        # read config file with initialized values
        pathname = os.path.join(self.git_test_repo_clean.migrations_dir(),
            'automated_migration_config-test_repo_clean.yaml')
        automated_migration_config = AutomatedMigration.load_config_file(pathname)
        expected_automated_migration_config = dict(
            files_to_migrate=['../tests/fixtures//empty_data_file_2.xlsx', '../tests/fixtures//empty_data_file_1.xlsx'],
            migrator='wc_lang',
            schema_file='../test_repo_clean/core.py',
            schema_repo_url='https://github.com/KarrLab/test_repo_clean'
        )
        self.assertEqual(automated_migration_config, expected_automated_migration_config)

        # test errors
        with self.assertRaisesRegex(MigratorError, "could not read automated migration config file: .+"):
            AutomatedMigration.load_config_file('no such file')

        bad_yaml = os.path.join(self.tmp_dir, 'bad_yaml.yaml')
        f = open(bad_yaml, "w")
        f.write("unbalanced brackets: ][")
        f.close()
        with self.assertRaisesRegex(MigratorError, r"could not parse YAML automated migration config file: '\S+'"):
            AutomatedMigration.load_config_file(bad_yaml)

        # make a config file that's missing an attribute
        saved_config_attributes = AutomatedMigration._CONFIG_ATTRIBUTES.copy()
        del AutomatedMigration._CONFIG_ATTRIBUTES['files_to_migrate']
        config_file = AutomatedMigration.make_template_config_file(self.git_repo, 'test_schema_repo')
        # restore the attribute
        AutomatedMigration._CONFIG_ATTRIBUTES = saved_config_attributes
        with self.assertRaisesRegex(MigratorError, "automated migration config file must have a dict "
            "with the attributes in AutomatedMigration._CONFIG_ATTRIBUTES: .+"):
            AutomatedMigration.load_config_file(config_file)
        remove_silently(config_file)

        config_file = AutomatedMigration.make_template_config_file(self.git_repo, 'test_schema_repo')
        with self.assertRaisesRegex(MigratorError,
            "all attributes in an automated migration config file must be initialized, but they are:.+"):
            AutomatedMigration.load_config_file(config_file)
        remove_silently(config_file)

    def test_init(self):
        config_basename = 'automated_migration_config-test_repo_clean.yaml'
        automated_migration = AutomatedMigration(
            **dict(data_repo_location=self.test_repo_clean_url, data_config_file_basename=config_basename))
        self.assertEqual(automated_migration.data_repo_location, self.test_repo_clean_url)
        self.assertEqual(automated_migration.data_config_file_basename, config_basename)
        self.assertEqual(automated_migration.data_git_repo.repo_name(), 'test_repo_clean')
        self.assertIsInstance(automated_migration.data_config, dict)
        self.assertEqual(automated_migration.schema_git_repo.repo_name(), 'test_repo_clean')

        with self.assertRaisesRegex(MigratorError, "initialization of AutomatedMigration must provide "
            "AutomatedMigration._REQUIRED_ATTRIBUTES (.+) but these are missing: \{'data_config_file_basename'\}"):
            AutomatedMigration(**dict(data_repo_location=self.test_repo_clean_url))

    def test_validate(self):
        automated_migration = self.clean_automated_migration

        expected_files_to_migrate = []
        for f in ['../tests/fixtures//empty_data_file_2.xlsx', '../tests/fixtures//empty_data_file_1.xlsx']:
            expected_files_to_migrate.append(os.path.normpath(
                os.path.join(automated_migration.data_git_repo.migrations_dir(), f)))
        automated_migration.validate()
        self.assertEqual(expected_files_to_migrate, automated_migration.data_config['files_to_migrate'])
        self.assertEqual(automated_migration.data_config['schema_repo_url'],
            'https://github.com/KarrLab/test_repo_clean')
        loaded_schema_changes = automated_migration.loaded_schema_changes
        self.assertEqual(len(loaded_schema_changes), 1)
        self.assertIsInstance(loaded_schema_changes[0], SchemaChanges)

        # test errors
        os.rename(  # create an error in all_schema_changes_with_commits()
            os.path.join(automated_migration.schema_git_repo.migrations_dir(),
                'schema_changes_2019-02-13-14-05-42_ba1f9d3.yaml'),
            os.path.join(automated_migration.schema_git_repo.migrations_dir(),
                'schema_changes_2019-02-13-14-05-42_badhash.yaml'))
        with self.assertRaises(MigratorError):
            automated_migration.validate()

        remove_silently(expected_files_to_migrate[0])   # delete a file to migrate
        with self.assertRaisesRegex(MigratorError,
            "file to migrate '.+', with full path '.+', doesn't exist"):
            automated_migration.validate()

    def test_get_name(self):
        self.assertIn('automated-migration:test_repo_clean:test_repo_clean:',
            self.clean_automated_migration.get_name())

        self.clean_automated_migration.data_git_repo = None
        with self.assertRaisesRegex(MigratorError,
            re.escape("To run get_name() data_git_repo and schema_git_repo must be initialized")):
            self.clean_automated_migration.get_name()

    def test_get_data_file_git_commit_hash(self):
        self.clean_automated_migration.validate()
        test_file = os.path.join(self.test_repo_clean_fixtures, 'data_file.xlsx')
        git_commit_hash = self.clean_automated_migration.get_data_file_git_commit_hash(test_file)
        self.assertEqual(git_commit_hash, '7fc7603c9901980930ab519260010757adc56f27')

        # test errors
        with self.assertRaisesRegex(MigratorError, "schema '.+' does not have a _GIT_METADATA attribute"):
            self.buggy_automated_migration.get_data_file_git_commit_hash('no_file')
        automated_migration_w_bad_data_file = AutomatedMigration(
            **dict(data_repo_location=self.test_repo_url,
                data_config_file_basename='automated_migration_config-test_repo_good_schema.yaml'))
        test_repo_fixtures = automated_migration_w_bad_data_file.data_git_repo.fixtures_dir()
        test_file = os.path.join(test_repo_fixtures, 'bad_data_file.xlsx')
        with self.assertRaisesRegex(MigratorError, "data file '.*' must contain exactly one instance of .*"):
            automated_migration_w_bad_data_file.get_data_file_git_commit_hash(test_file)

    def test_get_seqs_of_schema_changes(self):
        self.clean_automated_migration.validate()
        migration_spec_args = {}
        self.clean_automated_migration.get_seqs_of_schema_changes(migration_spec_args)
        for attr in ['seq_of_renamed_models', 'seq_of_renamed_attributes']:
            self.assertEqual(len(migration_spec_args[attr]), 1)
        self.assertEqual(os.path.basename(migration_spec_args['schema_files'][0]),
            'schema_changes_2019-02-13-14-05-42_ba1f9d3.yaml')
        self.assertEqual(migration_spec_args['seq_of_renamed_models'], [[['Test', 'TestNew']]])
        self.assertEqual(migration_spec_args['seq_of_renamed_attributes'], [[]])
        self.assertEqual(migration_spec_args['seq_of_transformations'], ['transformations_ba1f9d3.py'])

    def test_generate_migration_spec(self):
        self.clean_automated_migration.validate()
        migration_spec = self.clean_automated_migration.generate_migration_spec()
        self.assertEqual([os.path.basename(f) for f in migration_spec.existing_files],
            ['empty_data_file_2.xlsx', 'empty_data_file_1.xlsx'])
        self.assertEqual(migration_spec.migrator, Migrator.generate_wc_lang_migrator)

    def test_clone_schema_repos(self):
        pass

    def test_get_schema(self):
        pass

    def test_migrate(self):
        pass

    def test_prepare(self):
        pass

    def test_(self):
        pass


# @unittest.skip("speed up testing")
class TestRunMigration(MigrationFixtures):

    def setUp(self):
        super().setUp()

    def tearDown(self):
        super().tearDown()

    def test_parse_args(self):
        cl = "{}".format(self.config_file)
        args = RunMigration.parse_args(cli_args=cl.split())
        self.assertEqual(args.migrations_config_file, self.config_file)

    def test_main(self):
        for warnings in [True, False]:
            # Prepare to remove the migrated_files if the test fails
            for migration_spec in MigrationSpec.load(self.config_file).values():
                for expected_migrated_file in migration_spec.expected_migrated_files():
                    self.files_to_delete.add(expected_migrated_file)

            args = Namespace(migrations_config_file=self.config_file, warnings=warnings)
            with capturer.CaptureOutput(relay=False) as capture_output:
                results = RunMigration.main(args)
                for migration_disc, migrated_filenames in results:
                    self.assertIn(migration_disc.name, capture_output.get_text())
                    for migrated_file in migrated_filenames:
                        self.assertIn(migrated_file, capture_output.get_text())

            for migration_disc, migrated_filenames in results:
                self.assertIsInstance(migration_disc, MigrationSpec)
                for migrated_file in migrated_filenames:
                    self.assertTrue(os.path.isfile(migrated_file))

            # remove the migrated files so they do not contaminate tests/fixtures/migrate
            for _, migrated_filenames in results:
                for migrated_file in migrated_filenames:
                    remove_silently(migrated_file)
