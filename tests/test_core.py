""" Test core data model functionality.

:Author: Jonathan Karr <karr@mssm.edu>
:Author: Arthur Goldberg <Arthur.Goldberg@mssm.edu>
:Date: 2016-11-23
:Copyright: 2016-2017, Karr Lab
:License: MIT
"""

from contextlib import contextmanager
from datetime import date, time, datetime
from itertools import chain
from obj_model import core
from obj_model.core import excel_col_name
import enum
import gc
import collections
import copy
import math
import re
import resource
import six
import sys
import unittest


class Order(enum.Enum):
    root = 1
    leaf = 2


class Root(core.Model):
    label = core.StringAttribute(
        verbose_name='Label', max_length=255, primary=True, unique=True)

    class Meta(core.Model.Meta):
        pass


class Leaf(core.Model):
    root = core.ManyToOneAttribute(Root, verbose_name='Root',
                                   related_name='leaves', verbose_related_name='Leaves', min_related=1)
    id = core.RegexAttribute(verbose_name='ID', min_length=1, max_length=63,
                             pattern=r'^[a-z][a-z0-9_]*$', flags=re.I, primary=True)
    name = core.StringAttribute(verbose_name='Name', max_length=255)

    class Meta(core.Model.Meta):
        verbose_name = 'Leaf'
        verbose_name_plural = 'Leaves'
        attribute_order = ('id', )


class UnrootedLeaf(Leaf):
    name = core.StringAttribute(verbose_name='Name', max_length=10)

    root2 = core.ManyToOneAttribute(
        Root, min_related=0, verbose_name='Root', related_name='leaves2')
    id2 = core.RegexAttribute(verbose_name='ID', min_length=1, max_length=63,
                              pattern=r'^[a-z][a-z0-9_]*$', flags=re.I)
    name2 = core.StringAttribute(
        verbose_name='Name', min_length=2, max_length=3)
    float2 = core.FloatAttribute(verbose_name='Float', min=2., max=3.)
    float3 = core.FloatAttribute(verbose_name='Float', min=2., nan=False)
    enum2 = core.EnumAttribute(Order, verbose_name='Enum')
    enum3 = core.EnumAttribute(
        Order, verbose_name='Enum', default=Order['leaf'])
    multi_word_name = core.StringAttribute()


class Leaf3(UnrootedLeaf):

    class Meta(core.Model.Meta):
        attribute_order = ('id2', 'name2', )


class Grandparent(core.Model):
    id = core.StringAttribute(max_length=1, primary=True, unique=True)
    val = core.StringAttribute()


class Parent(core.Model):
    id = core.StringAttribute(max_length=2, primary=True, unique=True)
    val = core.StringAttribute()
    grandparent = core.ManyToOneAttribute(
        Grandparent, related_name='children', min_related=1)


class Child(core.Model):
    id = core.StringAttribute(primary=True)
    val = core.StringAttribute()
    parent = core.ManyToOneAttribute(
        Parent, related_name='children', min_related=1)


class UniqueRoot(Root):
    label = core.SlugAttribute(verbose_name='Label')
    url = core.UrlAttribute()
    int_attr = core.IntegerAttribute()
    pos_int_attr = core.PositiveIntegerAttribute()

    class Meta(core.Model.Meta):
        pass


class DateRoot(core.Model):
    date = core.DateAttribute(none=True)
    time = core.TimeAttribute(none=True)
    datetime = core.DateTimeAttribute(none=True)


class NotNoneDateRoot(core.Model):
    date = core.DateAttribute(none=False)
    time = core.TimeAttribute(none=False)
    datetime = core.DateTimeAttribute(none=False)


class OneToOneRoot(core.Model):
    id = core.SlugAttribute(verbose_name='ID')


class OneToOneLeaf(core.Model):
    root = core.OneToOneAttribute(
        OneToOneRoot, related_name='leaf', min_related=1)


class ManyToOneRoot(core.Model):
    id = core.SlugAttribute(verbose_name='ID')


class ManyToOneLeaf(core.Model):
    id = core.SlugAttribute(verbose_name='ID')
    root = core.ManyToOneAttribute(
        ManyToOneRoot, related_name='leaves', min_related=1)


class OneToManyRoot(core.Model):
    id = core.SlugAttribute(verbose_name='ID')


class OneToManyLeaf(core.Model):
    id = core.SlugAttribute(verbose_name='ID')
    roots = core.OneToManyAttribute(
        OneToManyRoot, related_name='leaf', min_related_rev=1)


class ManyToManyRoot(core.Model):
    id = core.SlugAttribute(verbose_name='ID')


class ManyToManyLeaf(core.Model):
    id = core.SlugAttribute(verbose_name='ID')
    roots = core.ManyToManyAttribute(ManyToManyRoot, related_name='leaves')


class UniqueTogetherRoot(core.Model):
    val0 = core.StringAttribute(unique=True)
    val1 = core.StringAttribute(unique=False)
    val2 = core.StringAttribute(unique=False)

    class Meta(core.Model.Meta):
        unique_together = (('val1', 'val2'),)


class InlineRoot(core.Model):

    class Meta(core.Model.Meta):
        tabular_orientation = core.TabularOrientation.inline


class Example0(core.Model):
    int_attr = core.IntegerAttribute()

    class Meta(core.Model.Meta):
        indexed_attrs_tuples = (('int_attr',), )


class Example1(core.Model):
    str_attr = core.StringAttribute()
    int_attr = core.IntegerAttribute()
    int_attr2 = core.IntegerAttribute()
    test0 = core.OneToOneAttribute(Example0, related_name='test1')
    test0s = core.OneToManyAttribute(Example0, related_name='test1_1tm')

    class Meta(core.Model.Meta):
        indexed_attrs_tuples = (
            ('str_attr',), ('int_attr', 'int_attr2'), ('test0',))


class Example2(core.Model):
    id = core.IntegerAttribute()


class TestCore(unittest.TestCase):

    def test_get_models(self):
        models = set((
            Root, Leaf, UnrootedLeaf, Leaf3, Grandparent, Parent, Child,
            UniqueRoot, DateRoot, NotNoneDateRoot, OneToOneRoot, OneToOneLeaf,
            ManyToOneRoot, ManyToOneLeaf, OneToManyRoot, OneToManyLeaf, ManyToManyRoot, ManyToManyLeaf,
            UniqueTogetherRoot, InlineRoot, Example0, Example1, Example2
        ))
        self.assertEqual(
            set(core.get_models(module=sys.modules[__name__])), models)
        self.assertEqual(models.difference(core.get_models()), set())

        models.remove(InlineRoot)
        self.assertEqual(
            set(core.get_models(module=sys.modules[__name__], inline=False)), models)
        self.assertEqual(models.difference(
            core.get_models(inline=False)), set())

    def test_get_model(self):
        self.assertEqual(core.get_model('Root'), None)
        self.assertEqual(core.get_model(
            'Root', module=sys.modules[__name__]), Root)
        self.assertEqual(core.get_model(Root.__module__ + '.Root'), Root)

    def test_verbose_name(self):
        self.assertEqual(Root.Meta.verbose_name, 'Root')
        self.assertEqual(Root.Meta.verbose_name_plural, 'Roots')

        self.assertEqual(Leaf.Meta.verbose_name, 'Leaf')
        self.assertEqual(Leaf.Meta.verbose_name_plural, 'Leaves')

        self.assertEqual(UnrootedLeaf.Meta.verbose_name, 'Unrooted leaf')
        self.assertEqual(
            UnrootedLeaf.Meta.verbose_name_plural, 'Unrooted leaves')

        self.assertEqual(Leaf3.Meta.verbose_name, 'Leaf3')
        self.assertEqual(Leaf3.Meta.verbose_name_plural, 'Leaf3s')

        self.assertEqual(UnrootedLeaf.Meta.attributes[
                         'multi_word_name'].verbose_name, 'Multi word name')

    def test_meta_attributes(self):
        self.assertEqual(set(Root.Meta.attributes.keys()), set(('label', )))
        self.assertEqual(set(Leaf.Meta.attributes.keys()),
                         set(('root', 'id', 'name', )))

    def test_meta_related_attributes(self):
        self.assertEqual(set(Root.Meta.related_attributes.keys()),
                         set(('leaves', 'leaves2', )))
        self.assertEqual(set(Leaf.Meta.related_attributes.keys()), set())

    def test_attributes(self):
        root = Root()
        leaf = Leaf()

        self.assertEqual(set(vars(root).keys()), set(
            ('_source', 'label', 'leaves', 'leaves2')))
        self.assertEqual(set(vars(leaf).keys()), set(
            ('_source', 'root', 'id', 'name')))

    def test_attribute_order(self):
        self.assertEqual(set(Root.Meta.attribute_order),
                         set(Root.Meta.attributes.keys()))
        self.assertEqual(set(Leaf.Meta.attribute_order),
                         set(Leaf.Meta.attributes.keys()))
        self.assertEqual(set(UnrootedLeaf.Meta.attribute_order),
                         set(UnrootedLeaf.Meta.attributes.keys()))
        self.assertEqual(set(Leaf3.Meta.attribute_order),
                         set(Leaf3.Meta.attributes.keys()))

        self.assertEqual(Root.Meta.attribute_order, ('label', ))
        self.assertEqual(Leaf.Meta.attribute_order, ('id', 'name', 'root'))
        self.assertEqual(UnrootedLeaf.Meta.attribute_order, (
            'id', 'name', 'root',
            'enum2', 'enum3', 'float2', 'float3', 'id2', 'multi_word_name', 'name2', 'root2', ))
        self.assertEqual(Leaf3.Meta.attribute_order, (
            'id2', 'name2',
            'enum2', 'enum3', 'float2', 'float3', 'id', 'multi_word_name', 'name', 'root', 'root2', ))

    def test_set(self):
        leaf = Leaf(id='leaf_1', name='Leaf 1')
        self.assertEqual(leaf.id, 'leaf_1')
        self.assertEqual(leaf.name, 'Leaf 1')

        leaf.id = 'leaf_2'
        leaf.name = 'Leaf 2'
        self.assertEqual(leaf.id, 'leaf_2')
        self.assertEqual(leaf.name, 'Leaf 2')

    def test_memory_use(self):
        ''' Not a test; rather a measurement of the memory use by schema objects for monitoring '''
        root = Root(label='root')
        n = 100
        iter = 0
        n_leaves = 0
        while n <= 10000:
            start_RAM = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            for i in range(n):
                Leaf(root=root, id=str(i), name="leaf_{}_{}".format(iter, i))
            print("{} {} objects: {} KB/obj".format(n, 'Leaf',
                                                    (resource.getrusage(resource.RUSAGE_SELF).ru_maxrss - start_RAM) / n))
            n_leaves += n
            self.assertEqual(len(set(root.leaves)), n_leaves)
            iter += 1
            n *= 4

    def test_set_related(self):
        root1 = Root(label='root1')
        root2 = Root(label='root2')

        leaf1 = Leaf(id='leaf1')
        leaf2 = Leaf(id='leaf2')
        leaf3 = Leaf(id='leaf3')
        self.assertEqual(leaf1.root, None)
        self.assertEqual(leaf2.root, None)
        self.assertEqual(leaf3.root, None)

        leaf1.root = root1
        leaf2.root = root1
        leaf3.root = root2
        self.assertEqual(leaf1.root, root1)
        self.assertEqual(leaf2.root, root1)
        self.assertEqual(leaf3.root, root2)
        self.assertEqual(set(root1.leaves), set((leaf1, leaf2)))
        self.assertEqual(root2.leaves, [leaf3])

        leaf2.root = root2
        leaf3.root = root1
        self.assertEqual(leaf1.root, root1)
        self.assertEqual(leaf2.root, root2)
        self.assertEqual(leaf3.root, root1)
        self.assertEqual(set(root1.leaves), set((leaf1, leaf3, )))
        self.assertEqual(root2.leaves, [leaf2])

        leaf4 = Leaf(root=root1)
        self.assertEqual(leaf4.root, root1)
        self.assertEqual(set(root1.leaves), set((leaf1, leaf3, leaf4)))

    def test_get_related(self):
        g0 = Grandparent(id='root-0')
        p0 = [
            Parent(grandparent=g0, id='node-0-0'),
            Parent(grandparent=g0, id='node-0-1'),
        ]
        c0 = [
            Child(parent=p0[0], id='leaf-0-0-0'),
            Child(parent=p0[0], id='leaf-0-0-1'),
            Child(parent=p0[1], id='leaf-0-1-0'),
            Child(parent=p0[1], id='leaf-0-1-1'),
        ]

        g1 = Grandparent(id='root-1')
        p1 = [
            Parent(grandparent=g1, id='node-1-0'),
            Parent(grandparent=g1, id='node-1-1'),
        ]
        c1 = [
            Child(parent=p1[0], id='leaf-1-0-0'),
            Child(parent=p1[0], id='leaf-1-0-1'),
            Child(parent=p1[1], id='leaf-1-1-0'),
            Child(parent=p1[1], id='leaf-1-1-1'),
        ]

        self.assertEqual(set(g0.get_related()), set((g0,)) | set(p0) | set(c0))
        self.assertEqual(set(p0[0].get_related()),
                         set((g0,)) | set(p0) | set(c0))
        self.assertEqual(set(c0[0].get_related()),
                         set((g0,)) | set(p0) | set(c0))

        self.assertEqual(set(g1.get_related()), set((g1,)) | set(p1) | set(c1))
        self.assertEqual(set(p1[0].get_related()),
                         set((g1,)) | set(p1) | set(c1))
        self.assertEqual(set(c1[0].get_related()),
                         set((g1,)) | set(p1) | set(c1))

    def test_equal(self):
        root1 = Root(label='a')
        root2 = Root(label='b')

        leaf1 = Leaf(root=root1, id='a', name='ab')
        leaf2 = Leaf(root=root1, id='a', name='ab')
        leaf3 = Leaf(root=root1, id='b', name='ab')
        leaf4 = Leaf(root=root2, id='b', name='ab')

        self.assertFalse(leaf1 is leaf2)
        self.assertFalse(leaf1 is leaf3)
        self.assertFalse(leaf2 is leaf3)

        self.assertTrue(leaf1.is_equal(leaf2))
        self.assertFalse(leaf1.is_equal(leaf3))
        self.assertFalse(leaf3.is_equal(leaf4))

    def test_hash(self):
        self.assertEqual(len([Root()]), 1)
        self.assertEqual(len([Leaf(), Leaf()]), 2)
        self.assertEqual(len([UnrootedLeaf(), UnrootedLeaf()]), 2)
        self.assertEqual(len([Leaf3(), Leaf3(), Leaf3()]), 3)

    def test___str__(self):
        root = Root(label='test label')
        self.assertEqual(str(root), '<{}.{}: {}>'.format(
            Root.__module__, 'Root', root.label))

    def test_literal_attribute_serialize(self):
        class TestModel(core.Model):
            id = core.LiteralAttribute()

        value = 'str'
        self.assertEqual(TestModel.Meta.attributes['id'].serialize(value), value)

    def test_validate_attributes(self):
        class TestParent(core.Model):
            id = core.StringAttribute(primary=True)
            children = core.OneToManyAttribute(
                'TestChild', related_name='parent')
        class TestChild(core.Model):
            id = core.StringAttribute(primary=True)

        children = [TestChild()]
        parent = TestParent(children=[TestChild()])

    def test_validate_attributes_errors(self):
        with self.assertRaises(ValueError) as context:
            class Test1(core.Model):
                name = core.StringAttribute()
                class Meta(core.Model.Meta):
                    attribute_order = (1,)
        self.assertIn('must contain attribute names', str(context.exception))

        bad_name = 'ERROR'
        with self.assertRaises(ValueError) as context:
            class Test1(core.Model):
                name = core.StringAttribute()
                class Meta(core.Model.Meta):
                    attribute_order = (bad_name,)
        self.assertIn("'{}' not found in attributes of".format(
            bad_name), str(context.exception))

        with self.assertRaises(ValueError) as context:
            class Test1(core.Model):
                name = core.StringAttribute()
                class Meta(core.Model.Meta):
                    unique_together = 'hello'
        self.assertIn("must be a tuple, not", str(context.exception))

        with self.assertRaises(ValueError) as context:
            class Test1(core.Model):
                name = core.StringAttribute()
                class Meta(core.Model.Meta):
                    unique_together = ('hello', 2)
        self.assertIn("must be a tuple of tuples, not", str(context.exception))

        with self.assertRaises(ValueError) as context:
            class Test1(core.Model):
                name = core.StringAttribute()
                class Meta(core.Model.Meta):
                    unique_together = ((3,), ('var', 'woops!'),)
        self.assertIn("must be a tuple of tuples of strings, not",
                      str(context.exception))

        with self.assertRaises(ValueError) as context:
            class Test1(core.Model):
                name = core.StringAttribute()
                var = core.IntegerAttribute()
                class Meta(core.Model.Meta):
                    unique_together = (('name',), ('var', 'woops!'),)
        self.assertIn("must be a tuple of tuples of attribute names",
                      str(context.exception))

        with self.assertRaises(ValueError) as context:
            class Test1(core.Model):
                name = core.StringAttribute()
                var = core.IntegerAttribute()
                class Meta(core.Model.Meta):
                    unique_together = (('name', 'var', 'name', ),)
        self.assertIn("cannot repeat attribute names in any tuple",
                      str(context.exception))

        with self.assertRaises(ValueError) as context:
            class Test1(core.Model):
                name = core.StringAttribute()
                var = core.IntegerAttribute()
                class Meta(core.Model.Meta):
                    unique_together = (('var', 'name',), ('name', 'var', ), )
        self.assertIn("unique_together cannot contain identical attribute sets", str(
            context.exception))

        test_tuples = (('b_name', 'a_name',), ('c_name', 'b_name', ), )
        class Test1(core.Model):
            a_name = core.StringAttribute()
            b_name = core.IntegerAttribute()
            c_name = core.IntegerAttribute()
            class Meta(core.Model.Meta):
                unique_together = test_tuples
        for a_tuple in test_tuples:
            self.assertIn(tuple(sorted(a_tuple)), Test1.Meta.unique_together)

    def test_validate_attribute(self):
        root = Root()
        root.clean()
        self.assertIn('value for primary attribute cannot be empty',
                      root.validate().attributes[0].messages[0])

        leaf = Leaf()
        self.assertEqual(
            set((x.attribute.name for x in leaf.validate().attributes)), set(('id', 'root',)))

        leaf.id = 'a'
        self.assertEqual(
            set((x.attribute.name for x in leaf.validate().attributes)), set(('root',)))

        leaf.name = 1
        self.assertEqual(set(
            (x.attribute.name for x in leaf.validate().attributes)), set(('name', 'root',)))

        leaf.name = 'b'
        self.assertEqual(
            set((x.attribute.name for x in leaf.validate().attributes)), set(('root',)))

        leaf.root = root
        self.assertEqual(leaf.validate(), None)
        self.assertIn('value for primary attribute cannot be empty',
                      root.validate().attributes[0].messages[0])

        unrooted_leaf = UnrootedLeaf(root=root, id='a', id2='b', name2='ab', float2=2.4,
                                     float3=2.4, enum2=Order['root'], enum3=Order['leaf'])
        self.assertEqual(unrooted_leaf.validate(), None)

    def test_enum_attribute(self):
        class TestEnum(enum.Enum):
            val0 = 0

        with self.assertRaisesRegexp(ValueError, 'must be a subclass of `Enum`'):
            core.EnumAttribute(int)

        with self.assertRaisesRegexp(ValueError, 'Default must be `None` or an instance of `enum_class`'):
            core.EnumAttribute(TestEnum, default=0)

        attr = core.EnumAttribute(TestEnum)
        self.assertEqual(attr.serialize(TestEnum.val0), 'val0')

    def test_boolean_attribute(self):
        with self.assertRaisesRegexp(ValueError, '`default` must be `None` or an instance of `bool`'):
            core.BooleanAttribute(default=0)

        attr = core.BooleanAttribute()

        self.assertEqual(attr.clean(''), (None, None))
        self.assertEqual(attr.clean('true'), (True, None))
        self.assertEqual(attr.clean('false'), (False, None))
        self.assertEqual(attr.clean(float('nan')), (None, None))
        self.assertEqual(attr.clean(1.), (True, None))
        self.assertEqual(attr.clean(0.), (False, None))
        self.assertEqual(attr.clean(None), (None, None))
        self.assertEqual(attr.clean([])[0], None)
        self.assertNotEqual(attr.clean([])[1], None)

        self.assertEqual(attr.validate(None, None), None)
        self.assertEqual(attr.validate(None, False), None)
        self.assertEqual(attr.validate(None, True), None)
        self.assertNotEqual(attr.validate(None, 1.), None)

    def test_float_attribute(self):
        with self.assertRaisesRegexp(ValueError, '`max` must be at least `min`'):
            core.FloatAttribute(min=10., max=1.)

        attr = core.FloatAttribute()
        self.assertTrue(math.isnan(attr.clean('')[0]))
        self.assertEqual(attr.clean('')[1], None)

        self.assertEqual(attr.serialize(float('nan')), None)

    def test_integer_attribute(self):
        attr = core.IntegerAttribute(default=1.)
        self.assertIsInstance(attr.default, int)
        self.assertEqual(attr.default, 1)

        with self.assertRaisesRegexp(ValueError, '`max` must be at least `min`'):
            core.IntegerAttribute(min=10, max=1)

        attr = core.IntegerAttribute(min=5)
        self.assertEqual(attr.validate(None, 5), None)
        self.assertEqual(attr.validate(None, 6), None)
        self.assertEqual(attr.validate(None, None), None)
        self.assertNotEqual(attr.validate(None, 4), None)

        attr = core.IntegerAttribute(max=5)
        self.assertEqual(attr.validate(None, 4), None)
        self.assertEqual(attr.validate(None, 5), None)
        self.assertEqual(attr.validate(None, None), None)
        self.assertNotEqual(attr.validate(None, 6), None)

        attr = core.IntegerAttribute()
        self.assertEqual(attr.serialize(None), None)
        self.assertEqual(attr.serialize(1.), 1.)
        self.assertEqual(attr.serialize(1), 1.)

    def test_string_attribute(self):
        with self.assertRaisesRegexp(ValueError, '`min_length` must be a non-negative integer'):
            core.StringAttribute(min_length=-1)

        with self.assertRaisesRegexp(ValueError, '`max_length` must be at least `min_length` or `None`'):
            core.StringAttribute(max_length=-1)

        with self.assertRaisesRegexp(ValueError, '`default` must be a string'):
            core.StringAttribute(default=None)

        attr = core.StringAttribute()
        self.assertEqual(attr.clean(None), ('', None))
        self.assertEqual(attr.clean(''), ('', None))
        self.assertEqual(attr.clean(1), ('1', None))

    def test_validate_string_attribute(self):
        leaf = UnrootedLeaf()

        leaf.name2 = 'a'
        self.assertIn(
            'name2', [x.attribute.name for x in leaf.validate().attributes])

        leaf.name2 = 'abcd'
        self.assertIn(
            'name2', [x.attribute.name for x in leaf.validate().attributes])

        leaf.name2 = 'ab'
        self.assertNotIn(
            'name2', [x.attribute.name for x in leaf.validate().attributes])

    def test_validate_regex_attribute(self):
        leaf = Leaf()

        leaf.id = ''
        self.assertIn(
            'id', [x.attribute.name for x in leaf.validate().attributes])

        leaf.id = '1'
        self.assertIn(
            'id', [x.attribute.name for x in leaf.validate().attributes])

        leaf.id = 'a-'
        self.assertIn(
            'id', [x.attribute.name for x in leaf.validate().attributes])

        leaf.id = 'a_'
        self.assertNotIn(
            'id', [x.attribute.name for x in leaf.validate().attributes])

    def test_validate_slug_attribute(self):
        root = UniqueRoot(label='root-0')
        self.assertIn(
            'label', [x.attribute.name for x in root.validate().attributes])

        root.label = 'root_0'
        self.assertEqual(root.validate(), None)

    def test_validate_url_attribute(self):
        root = UniqueRoot(url='root-0')
        self.assertIn(
            'url', [x.attribute.name for x in root.validate().attributes])

        root.url = 'http://www.test.com'
        self.assertNotIn(
            'url', [x.attribute.name for x in root.validate().attributes])

    def test_validate_float_attribute(self):
        leaf = UnrootedLeaf()

        # max=3.
        leaf.float2 = 'a'
        leaf.clean()
        self.assertIn(
            'float2', [x.attribute.name for x in leaf.validate().attributes])

        leaf.float2 = 1
        leaf.clean()
        self.assertIn(
            'float2', [x.attribute.name for x in leaf.validate().attributes])

        leaf.float2 = 4
        leaf.clean()
        self.assertIn(
            'float2', [x.attribute.name for x in leaf.validate().attributes])

        leaf.float2 = 3
        leaf.clean()
        self.assertNotIn(
            'float2', [x.attribute.name for x in leaf.validate().attributes])

        leaf.float2 = 3.
        leaf.clean()
        self.assertNotIn(
            'float2', [x.attribute.name for x in leaf.validate().attributes])

        leaf.float2 = 2.
        leaf.clean()
        self.assertNotIn(
            'float2', [x.attribute.name for x in leaf.validate().attributes])

        leaf.float2 = 2.5
        leaf.clean()
        self.assertNotIn(
            'float2', [x.attribute.name for x in leaf.validate().attributes])

        leaf.float2 = float('nan')
        leaf.clean()
        self.assertNotIn(
            'float2', [x.attribute.name for x in leaf.validate().attributes])

        # max=nan
        leaf.float3 = 2.5
        leaf.clean()
        self.assertNotIn(
            'float3', [x.attribute.name for x in leaf.validate().attributes])

        leaf.float3 = float('nan')
        leaf.clean()
        self.assertIn(
            'float3', [x.attribute.name for x in leaf.validate().attributes])

    def test_validate_int_attribute(self):
        root = UniqueRoot(int_attr='1.0.')
        root.clean()
        self.assertIn(
            'int_attr', [x.attribute.name for x in root.validate().attributes])

        root.int_attr = '1.5'
        root.clean()
        self.assertIn(
            'int_attr', [x.attribute.name for x in root.validate().attributes])

        root.int_attr = 1.5
        root.clean()
        self.assertIn(
            'int_attr', [x.attribute.name for x in root.validate().attributes])

        root.int_attr = '1.'
        root.clean()
        self.assertNotIn(
            'int_attr', [x.attribute.name for x in root.validate().attributes])

        root.int_attr = 1.
        root.clean()
        self.assertNotIn(
            'int_attr', [x.attribute.name for x in root.validate().attributes])

        root.int_attr = 1
        root.clean()
        self.assertNotIn(
            'int_attr', [x.attribute.name for x in root.validate().attributes])

        root.int_attr = None
        root.clean()
        self.assertNotIn(
            'int_attr', [x.attribute.name for x in root.validate().attributes])

    def test_validate_pos_int_attribute(self):
        root = UniqueRoot(pos_int_attr='0.')
        root.clean()
        self.assertIn('pos_int_attr', [
                      x.attribute.name for x in root.validate().attributes])

        root.pos_int_attr = 1.5
        root.clean()
        self.assertIn('pos_int_attr', [
                      x.attribute.name for x in root.validate().attributes])

        root.pos_int_attr = -1
        root.clean()
        self.assertIn('pos_int_attr', [
                      x.attribute.name for x in root.validate().attributes])

        root.pos_int_attr = 0
        root.clean()
        self.assertIn('pos_int_attr', [
                      x.attribute.name for x in root.validate().attributes])

        root.pos_int_attr = 1.
        root.clean()
        self.assertNotIn('pos_int_attr', [
                         x.attribute.name for x in root.validate().attributes])

        root.pos_int_attr = 1
        root.clean()
        self.assertNotIn('pos_int_attr', [
                         x.attribute.name for x in root.validate().attributes])

        root.pos_int_attr = None
        root.clean()
        self.assertNotIn('pos_int_attr', [
                         x.attribute.name for x in root.validate().attributes])

    def test_validate_enum_attribute(self):
        leaf = UnrootedLeaf()
        leaf.clean()

        self.assertIn(
            'enum2', [x.attribute.name for x in leaf.validate().attributes])
        self.assertNotIn(
            'enum3', [x.attribute.name for x in leaf.validate().attributes])

        leaf.enum2 = Order['root']
        leaf.clean()
        self.assertNotIn(
            'enum2', [x.attribute.name for x in leaf.validate().attributes])

        leaf.enum2 = 'root'
        leaf.clean()
        self.assertNotIn(
            'enum2', [x.attribute.name for x in leaf.validate().attributes])

        leaf.enum2 = 1
        leaf.clean()
        self.assertNotIn(
            'enum2', [x.attribute.name for x in leaf.validate().attributes])

        leaf.enum2 = 'root2'
        leaf.clean()
        self.assertIn(
            'enum2', [x.attribute.name for x in leaf.validate().attributes])

        leaf.enum2 = 3
        leaf.clean()
        self.assertIn(
            'enum2', [x.attribute.name for x in leaf.validate().attributes])

    def test_date_attribute(self):
        attr = core.DateAttribute()

        # clean
        self.assertEqual(attr.clean(None), (None, None))

        now = datetime(year=1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        self.assertEqual(attr.clean(now), (now.date(), None))

        now = datetime(year=1, month=1, day=1, hour=1)
        self.assertEqual(attr.clean(now)[0], None)
        self.assertNotEqual(attr.clean(now)[1], None)

        now = date(year=1, month=1, day=1)
        self.assertEqual(attr.clean(now), (now, None))

        now = '2000-01-01'
        self.assertEqual(attr.clean(now), (date(year=2000, month=1, day=1), None))

        now = '2000-01-01 01:01:00'
        self.assertEqual(attr.clean(now)[0], None)
        self.assertNotEqual(attr.clean(now)[1], None)

        now = 'x'
        self.assertEqual(attr.clean(now)[0], None)
        self.assertNotEqual(attr.clean(now)[1], None)

        now = []
        self.assertEqual(attr.clean(now)[0], None)
        self.assertNotEqual(attr.clean(now)[1], None)

    def test_validate_date_attribute(self):
        root = DateRoot()

        # positive examples
        root.date = date(2000, 10, 1)
        root.clean()
        self.assertEqual(root.validate(), None)

        root.date = '1900-1-1'
        root.clean()
        self.assertEqual(root.validate(), None)

        root.date = 1
        root.clean()
        self.assertEqual(root.validate(), None)

        root.date = 1.
        root.clean()
        self.assertEqual(root.validate(), None)

        # negative examples
        root.date = date(1, 10, 1)
        root.clean()
        self.assertNotEqual(root.validate(), None)

        root.date = datetime(1, 10, 1, 1, 0, 0, 0)
        root.clean()
        self.assertNotEqual(root.validate(), None)

        root.date = '1900-1-1 1:00:00.00'
        root.clean()
        self.assertNotEqual(root.validate(), None)

        root.date = 0
        root.clean()
        self.assertNotEqual(root.validate(), None)

        root.date = 1.5
        root.clean()
        self.assertNotEqual(root.validate(), None)

        # Not none
        root = NotNoneDateRoot()
        root.date = date(1900, 1, 1)
        root.time = time(0, 0, 0, 0)
        root.datetime = datetime(1900, 1, 1, 0, 0, 0, 0)

        root.clean()
        self.assertEqual(root.validate(), None)

        root.date = None
        root.clean()
        self.assertNotEqual(root.validate(), None)

    def test_time_attribute(self):
        root = DateRoot()

        # positive examples
        root.time = time(1, 0, 0, 0)
        root.clean()
        self.assertEqual(root.validate(), None)

        root.time = '1:1'
        root.clean()
        self.assertEqual(root.validate(), None)

        root.time = '1:1:1'
        root.clean()
        self.assertEqual(root.validate(), None)

        root.time = 0.25
        root.clean()
        self.assertEqual(root.validate(), None)

        # negative examples
        root.time = time(1, 0, 0, 1)
        root.clean()
        self.assertNotEqual(root.validate(), None)

        root.time = '1:1:1.01'
        root.clean()
        self.assertNotEqual(root.validate(), None)

        root.time = '1900-01-01 1:1:1.01'
        root.clean()
        self.assertNotEqual(root.validate(), None)

        root.time = 'x'
        root.clean()
        self.assertNotEqual(root.validate(), None)

        root.time = '99:99:99'
        root.clean()
        self.assertNotEqual(root.validate(), None)

        root.time = -0.25
        root.clean()
        self.assertNotEqual(root.validate(), None)

        root.time = 1.25
        root.clean()
        self.assertNotEqual(root.validate(), None)

        root.time = []
        root.clean()
        self.assertNotEqual(root.validate(), None)

        # Not none
        root = NotNoneDateRoot()
        root.date = date(1900, 1, 1)
        root.time = time(0, 0, 0, 0)
        root.datetime = datetime(1900, 1, 1, 0, 0, 0, 0)

        root.clean()
        self.assertEqual(root.validate(), None)

        root.time = None
        root.clean()
        self.assertNotEqual(root.validate(), None)

    def test_datetime_attribute(self):
        root = DateRoot()

        # positive examples
        root.datetime = None
        root.clean()
        self.assertEqual(root.validate(), None)

        root.datetime = datetime(2000, 10, 1, 0, 0, 1, 0)
        root.clean()
        self.assertEqual(root.validate(), None)

        root.datetime = date(2000, 10, 1)
        root.clean()
        self.assertEqual(root.validate(), None)

        root.datetime = '2000-10-01'
        root.clean()
        self.assertEqual(root.validate(), None)

        root.datetime = '2000-10-01 1:00:00'
        root.clean()
        self.assertEqual(root.validate(), None)

        root.datetime = 'x'
        root.clean()
        self.assertNotEqual(root.validate(), None)

        root.datetime = 10.25
        root.clean()
        self.assertEqual(root.validate(), None)

        root.datetime = 1.-1e-10
        root.clean()
        self.assertEqual(root.validate(), None)

        root.datetime = []
        root.clean()
        self.assertNotEqual(root.validate(), None)

        # negative examples
        root.datetime = datetime(2000, 10, 1, 0, 0, 1, 1)
        root.clean()
        self.assertNotEqual(root.validate(), None)

        root.datetime = '2000-10-01 1:00:00.01'
        root.clean()
        self.assertNotEqual(root.validate(), None)

        root.datetime = -1.5
        root.clean()
        self.assertNotEqual(root.validate(), None)

        # Not none
        root = NotNoneDateRoot()
        root.date = date(1900, 1, 1)
        root.time = time(0, 0, 0, 0)
        root.datetime = datetime(1900, 1, 1, 0, 0, 0, 0)

        root.clean()
        self.assertEqual(root.validate(), None)

        root.datetime = None
        root.clean()
        self.assertNotEqual(root.validate(), None)

    def test_related_attribute(self):
        class ConcreteRelatedAttribute(core.RelatedAttribute):

            def set_related_value(self):
                pass

            def validate(self):
                pass

            def serialize(self):
                pass

            def deserialize(self):
                pass

        with self.assertRaisesRegexp(ValueError, 'Default must be `None`, a list, or a callable'):
            ConcreteRelatedAttribute(None, default='')

        with self.assertRaisesRegexp(ValueError, 'Related default must be `None`, a list, or a callable'):
            ConcreteRelatedAttribute(None, related_default='')

        attr = ConcreteRelatedAttribute(None)
        with self.assertRaisesRegexp(ValueError, 'Related property is not defined'):
            attr.get_related_init_value(None)
        with self.assertRaisesRegexp(ValueError, 'Related property is not defined'):
            attr.get_related_default(None)

    @unittest.expectedFailure
    def test_related_no_double_default(self):
        class RootDefault(core.Model):
            label = core.StringAttribute(
                primary=True, unique=True, default='root0')

        class LeafDefault(core.Model):
            label = core.StringAttribute(
                primary=True, unique=True, default='leaf0')
            root = core.OneToOneAttribute(RootDefault, related_name='leaf',
                                          default=lambda: RootDefault(
                                              label='root0'),
                                          related_default=lambda: LeafDefault(label='leaf0'))

    def test_onetoone_default(self):
        class RootDefault(core.Model):
            label = core.StringAttribute(
                primary=True, unique=True, default='root0')

        class LeafDefault(core.Model):
            label = core.StringAttribute(
                primary=True, unique=True, default='leaf0')
            root = core.OneToOneAttribute(
                RootDefault, related_name='leaf', default=lambda: RootDefault(label='root2'))

        leaf0 = LeafDefault(root=RootDefault())
        self.assertEqual(leaf0.label, 'leaf0')
        self.assertIsInstance(leaf0.root, RootDefault)
        self.assertEqual(leaf0.root.label, 'root0')
        self.assertEqual(leaf0.root.leaf, leaf0)

        leaf1 = LeafDefault(label='leaf1')
        self.assertEqual(leaf1.label, 'leaf1')
        self.assertIsInstance(leaf1.root, RootDefault)
        self.assertEqual(leaf1.root.label, 'root2')
        self.assertEqual(leaf1.root.leaf, leaf1)

        leaf2 = LeafDefault(label='leaf2', root=RootDefault(label='root3'))
        self.assertEqual(leaf2.label, 'leaf2')
        self.assertIsInstance(leaf2.root, RootDefault)
        self.assertEqual(leaf2.root.label, 'root3')
        self.assertEqual(leaf2.root.leaf, leaf2)

    def test_onetoone_related_default(self):
        class RootDefault(core.Model):
            label = core.StringAttribute(
                primary=True, unique=True, default='root0')

        class LeafDefault(core.Model):
            label = core.StringAttribute(
                primary=True, unique=True, default='leaf0')
            root = core.OneToOneAttribute(RootDefault, related_name='leaf',
                                          related_default=lambda: LeafDefault(label='leaf2'))

        leaf0 = LeafDefault()
        self.assertEqual(leaf0.label, 'leaf0')
        self.assertEqual(leaf0.root, None)

        root0 = RootDefault()
        self.assertEqual(root0.label, 'root0')
        self.assertIsInstance(root0.leaf, LeafDefault)
        self.assertEqual(root0.leaf.label, 'leaf2')
        self.assertEqual(root0.leaf.root, root0)

        root1 = RootDefault(label='root1')
        self.assertEqual(root1.label, 'root1')
        self.assertIsInstance(root1.leaf, LeafDefault)
        self.assertEqual(root1.leaf.label, 'leaf2')
        self.assertEqual(root1.leaf.root, root1)

        root2 = RootDefault(label='root2', leaf=LeafDefault(label='leaf3'))
        self.assertEqual(root2.label, 'root2')
        self.assertIsInstance(root2.leaf, LeafDefault)
        self.assertEqual(root2.leaf.label, 'leaf3')
        self.assertEqual(root2.leaf.root, root2)

    def test_onetomany_default(self):
        class LeafDefault(core.Model):
            label = core.StringAttribute(
                primary=True, unique=True, default='leaf22')

        class RootDefault(core.Model):
            label = core.StringAttribute(
                primary=True, unique=True, default='root0')
            leaves = core.OneToManyAttribute(LeafDefault, related_name='root', default=lambda: [
                LeafDefault(label='leaf00'), LeafDefault(label='leaf01')])

        root0 = RootDefault()
        self.assertEqual(root0.label, 'root0')
        self.assertEqual(len(root0.leaves), 2)
        self.assertEqual(
            set([l.label for l in root0.leaves]), set(['leaf00', 'leaf01']))
        self.assertEqual(set([l.root for l in root0.leaves]), set([root0]))

        root1 = RootDefault(leaves=[LeafDefault(), LeafDefault()])
        self.assertEqual(root1.label, 'root0')
        self.assertEqual(len(root1.leaves), 2)
        self.assertEqual(
            set([l.label for l in root1.leaves]), set(['leaf22', 'leaf22']))
        self.assertEqual(set([l.root for l in root1.leaves]), set([root1]))

        root2 = RootDefault(label='root2', leaves=[LeafDefault(
            label='leaf20'), LeafDefault(label='leaf21')])
        self.assertEqual(root2.label, 'root2')
        self.assertEqual(len(root2.leaves), 2)
        self.assertEqual(
            set([l.label for l in root2.leaves]), set(['leaf20', 'leaf21']))
        self.assertEqual(set([l.root for l in root2.leaves]), set([root2]))

    def test_onetomany_related_default(self):
        class LeafDefault(core.Model):
            label = core.StringAttribute(
                primary=True, unique=True, default='leaf22')

        class RootDefault(core.Model):
            label = core.StringAttribute(
                primary=True, unique=True, default='root0')
            leaves = core.OneToManyAttribute(LeafDefault, related_name='root',
                                             related_default=lambda: RootDefault(label='root1'))

        root0 = RootDefault()
        self.assertEqual(root0.label, 'root0')
        self.assertEqual(root0.leaves, [])

        leaf0 = LeafDefault()
        self.assertEqual(leaf0.label, 'leaf22')
        self.assertIsInstance(leaf0.root, RootDefault)
        self.assertEqual(leaf0.root.label, 'root1')
        self.assertEqual(len(leaf0.root.leaves), 1)
        self.assertEqual(leaf0.root.leaves[0], leaf0)

        leaf1 = LeafDefault(label='leaf33')
        self.assertEqual(leaf1.label, 'leaf33')
        self.assertIsInstance(leaf1.root, RootDefault)
        self.assertEqual(leaf1.root.label, 'root1')
        self.assertEqual(len(leaf1.root.leaves), 1)
        self.assertEqual(leaf1.root.leaves[0], leaf1)

        leaf2 = LeafDefault(label='leaf44', root=RootDefault(label='root2'))
        self.assertEqual(leaf2.label, 'leaf44')
        self.assertIsInstance(leaf2.root, RootDefault)
        self.assertEqual(leaf2.root.label, 'root2')
        self.assertEqual(len(leaf2.root.leaves), 1)
        self.assertEqual(leaf2.root.leaves[0], leaf2)

    def test_manytoone_default(self):
        class RootDefault(core.Model):
            label = core.StringAttribute(
                primary=True, unique=True, default='root0')

        class LeafDefault(core.Model):
            label = core.StringAttribute(
                primary=True, unique=True, default='leaf2')
            root = core.ManyToOneAttribute(RootDefault, related_name='leaves',
                                           default=lambda: RootDefault(label='root1'))

        root0 = RootDefault()
        self.assertEqual(root0.label, 'root0')
        self.assertEqual(len(root0.leaves), 0)

        leaf1 = LeafDefault()
        self.assertEqual(leaf1.label, 'leaf2')
        self.assertIsInstance(leaf1.root, RootDefault)
        self.assertEqual(leaf1.root.label, 'root1')
        self.assertEqual(leaf1.root.leaves, [leaf1])

        leaf2 = LeafDefault(label='leaf4', root=RootDefault(label='root3'))
        self.assertEqual(leaf2.label, 'leaf4')
        self.assertIsInstance(leaf2.root, RootDefault)
        self.assertEqual(leaf2.root.label, 'root3')
        self.assertEqual(leaf2.root.leaves, [leaf2])

    def test_manytoone_related_default(self):
        class RootDefault(core.Model):
            label = core.StringAttribute(
                primary=True, unique=True, default='root0')

        class LeafDefault(core.Model):
            label = core.StringAttribute(
                primary=True, unique=True, default='leaf2')
            root = core.ManyToOneAttribute(RootDefault, related_name='leaves',
                                           related_default=lambda: [
                                               LeafDefault(label='leaf3'),
                                               LeafDefault(label='leaf4'),
                                               LeafDefault(label='leaf5')
                                           ])

        leaf0 = LeafDefault()
        self.assertEqual(leaf0.label, 'leaf2')
        self.assertEqual(leaf0.root, None)

        root1 = RootDefault()
        self.assertEqual(root1.label, 'root0')
        self.assertEqual(
            set([l.__class__ for l in root1.leaves]), set([LeafDefault]))
        self.assertEqual(set([l.label for l in root1.leaves]),
                         set(['leaf3', 'leaf4', 'leaf5']))
        self.assertEqual(set([l.root for l in root1.leaves]), set([root1]))

        root2 = RootDefault(label='root2', leaves=[LeafDefault(
            label='leaf6'), LeafDefault(label='leaf7')])
        self.assertEqual(root2.label, 'root2')
        self.assertEqual(
            set([l.__class__ for l in root2.leaves]), set([LeafDefault]))
        self.assertEqual(
            set([l.label for l in root2.leaves]), set(['leaf6', 'leaf7']))
        self.assertEqual(set([l.root for l in root2.leaves]), set([root2]))

    def test_manytomany_default(self):
        class RootDefault(core.Model):
            label = core.StringAttribute(
                primary=True, unique=True, default='root0')

        class LeafDefault(core.Model):
            label = core.StringAttribute(
                primary=True, unique=True, default='leaf0')
            roots = core.ManyToManyAttribute(RootDefault, related_name='leaves', default=lambda: [
                                             RootDefault(label='root1'), RootDefault(label='root2')])

        root0 = RootDefault()
        self.assertEqual(root0.label, 'root0')
        self.assertEqual(root0.leaves, [])

        leaf1 = LeafDefault()
        self.assertEqual(leaf1.label, 'leaf0')
        self.assertEqual(len(leaf1.roots), 2)
        self.assertEqual(
            set([r.__class__ for r in leaf1.roots]), set([RootDefault]))
        self.assertEqual(
            set([r.label for r in leaf1.roots]), set(['root1', 'root2']))
        self.assertEqual(set([len(r.leaves) for r in leaf1.roots]), set([1]))
        self.assertEqual(set([r.leaves[0] for r in leaf1.roots]), set([leaf1]))

    def test_manytomany_related_default(self):
        class RootDefault(core.Model):
            label = core.StringAttribute(
                primary=True, unique=True, default='root0')

        class LeafDefault(core.Model):
            label = core.StringAttribute(
                primary=True, unique=True, default='leaf0')
            roots = core.ManyToManyAttribute(RootDefault, related_name='leaves', related_default=lambda: [
                                             LeafDefault(label='leaf1'), LeafDefault(label='leaf2'), LeafDefault(label='leaf3')])

        leaf0 = LeafDefault()
        self.assertEqual(leaf0.label, 'leaf0')
        self.assertEqual(leaf0.roots, [])

        root1 = RootDefault()
        self.assertEqual(root1.label, 'root0')
        self.assertEqual(len(root1.leaves), 3)
        self.assertEqual(
            set([l.__class__ for l in root1.leaves]), set([LeafDefault]))
        self.assertEqual(set([l.label for l in root1.leaves]),
                         set(['leaf1', 'leaf2', 'leaf3']))
        self.assertEqual(set([len(l.roots) for l in root1.leaves]), set([1]))
        self.assertEqual(set([l.roots[0] for l in root1.leaves]), set([root1]))

    def test_validate_onetoone_attribute(self):
        root = OneToOneRoot(id='root')
        leaf = OneToOneLeaf(root=root)

        self.assertEqual(root.leaf, leaf)

        self.assertEqual(root.validate(), None)
        self.assertEqual(leaf.validate(), None)

    def test_validate_manytoone_attribute(self):
        # none=False
        leaf = Leaf()
        self.assertIn(
            'root', [x.attribute.name for x in leaf.validate().attributes])

        def set_root():
            leaf.root = Leaf()
        self.assertRaises(AttributeError, set_root)

        leaf.root = Root()
        self.assertNotIn(
            'root', [x.attribute.name for x in leaf.validate().attributes])

        # none=True
        unrooted_leaf = UnrootedLeaf()
        self.assertNotIn(
            'root2', [x.attribute.name for x in unrooted_leaf.validate().attributes])

    def test_validate_onetomany_attribute(self):
        root = OneToManyRoot()
        leaf = OneToManyLeaf()
        self.assertNotIn(
            'roots', [x.attribute.name for x in leaf.validate().attributes])

        root.leaf = leaf
        self.assertEqual(leaf.roots, [root])
        self.assertNotIn(
            'leaf', [x.attribute.name for x in root.validate().attributes])
        self.assertNotIn(
            'roots', [x.attribute.name for x in leaf.validate().attributes])

    def test_validate_manytomany_attribute(self):
        roots = [
            ManyToManyRoot(id='root_0'),
            ManyToManyRoot(id='root_1'),
            ManyToManyRoot(id='root_2'),
            ManyToManyRoot(id='root_3'),
        ]
        leaves = [
            ManyToManyLeaf(roots=roots[0:2], id='leaf_0'),
            ManyToManyLeaf(roots=roots[1:3], id='leaf_1'),
            ManyToManyLeaf(roots=roots[2:4], id='leaf_2'),
        ]

        self.assertEqual(roots[0].leaves, leaves[0:1])
        self.assertEqual(set(roots[1].leaves), set(leaves[0:2]))
        self.assertEqual(set(roots[2].leaves), set(leaves[1:3]))
        self.assertEqual(roots[3].leaves, leaves[2:3])

        # self.assertRaises(Exception, lambda: leaves[0].roots.add(roots[2]))

        for obj in chain(roots, leaves):
            error = obj.validate()
            self.assertEqual(error, None)

    def test_validate_one_to_one_num_related(self):
        # min_related=0, min_related_rev=0
        class TestRoot(core.Model):
            id = core.SlugAttribute()

        class TestNode(core.Model):
            id = core.SlugAttribute()
            root = core.OneToOneAttribute(
                TestRoot, related_name='node', min_related=0, min_related_rev=0)

        root = TestRoot(id='a')
        node = TestNode(id='b')
        self.assertEqual(root.validate(), None)
        self.assertEqual(node.validate(), None)

        root.node = node
        self.assertEqual(root.validate(), None)
        self.assertEqual(node.validate(), None)

        # min_related=1, min_related_rev=1
        class TestRoot(core.Model):
            id = core.SlugAttribute()

        class TestNode(core.Model):
            id = core.SlugAttribute()
            root = core.OneToOneAttribute(
                TestRoot, related_name='node', min_related=1, min_related_rev=1)

        root = TestRoot(id='a')
        node = TestNode(id='b')
        self.assertNotEqual(root.validate(), None)
        self.assertNotEqual(node.validate(), None)

        root.node = node
        self.assertEqual(root.validate(), None)
        self.assertEqual(node.validate(), None)

    def test_validate_one_to_many_num_related(self):
        # min_related=1, max_related=2, min_related_rev=1
        class TestRoot(core.Model):
            id = core.SlugAttribute()

        class TestNode(core.Model):
            id = core.SlugAttribute()
            roots = core.OneToManyAttribute(
                TestRoot, related_name='node', min_related=1, max_related=2, min_related_rev=1)

        root1 = TestRoot(id='a')
        root2 = TestRoot(id='b')
        root3 = TestRoot(id='c')
        node = TestNode(id='a')
        self.assertNotEqual(root1.validate(), None)
        self.assertNotEqual(root2.validate(), None)
        self.assertNotEqual(root3.validate(), None)
        self.assertNotEqual(node.validate(), None)

        node.roots = [root1]
        self.assertEqual(root1.validate(), None)
        self.assertNotEqual(root2.validate(), None)
        self.assertNotEqual(root3.validate(), None)
        self.assertEqual(node.validate(), None)

        node.roots = [root1, root2]
        self.assertEqual(root1.validate(), None)
        self.assertEqual(root2.validate(), None)
        self.assertNotEqual(root3.validate(), None)
        self.assertEqual(node.validate(), None)

        node.roots = [root1, root2, root3]
        self.assertEqual(root1.validate(), None)
        self.assertEqual(root2.validate(), None)
        self.assertEqual(root3.validate(), None)
        self.assertNotEqual(node.validate(), None)

        # min_related=1, max_related=2, min_related_rev=0
        class TestRoot(core.Model):
            id = core.SlugAttribute()

        class TestNode(core.Model):
            id = core.SlugAttribute()
            roots = core.OneToManyAttribute(
                TestRoot, related_name='node', min_related=1, max_related=2, min_related_rev=0)

        root1 = TestRoot(id='a')
        root2 = TestRoot(id='b')
        root3 = TestRoot(id='c')
        node = TestNode(id='a')
        self.assertEqual(root1.validate(), None)
        self.assertEqual(root2.validate(), None)
        self.assertEqual(root3.validate(), None)
        self.assertNotEqual(node.validate(), None)

        node.roots = [root1]
        self.assertEqual(root1.validate(), None)
        self.assertEqual(root2.validate(), None)
        self.assertEqual(root3.validate(), None)
        self.assertEqual(node.validate(), None)

        node.roots = [root1, root2]
        self.assertEqual(root1.validate(), None)
        self.assertEqual(root2.validate(), None)
        self.assertEqual(root3.validate(), None)
        self.assertEqual(node.validate(), None)

        node.roots = [root1, root2, root3]
        self.assertEqual(root1.validate(), None)
        self.assertEqual(root2.validate(), None)
        self.assertEqual(root3.validate(), None)
        self.assertNotEqual(node.validate(), None)

    def test_validate_many_to_one_num_related(self):
        # min_related=1, min_related_rev=1, max_related_rev=2
        class TestRoot(core.Model):
            id = core.SlugAttribute()

        class TestNode(core.Model):
            id = core.SlugAttribute()
            root = core.ManyToOneAttribute(
                TestRoot, related_name='nodes', min_related=1, min_related_rev=1, max_related_rev=2)

        root = TestRoot(id='a')
        node1 = TestNode(id='a')
        node2 = TestNode(id='b')
        node3 = TestNode(id='a')
        self.assertNotEqual(root.validate(), None)
        self.assertNotEqual(node1.validate(), None)
        self.assertNotEqual(node2.validate(), None)
        self.assertNotEqual(node3.validate(), None)

        root.nodes = [node1]
        self.assertEqual(root.validate(), None)
        self.assertEqual(node1.validate(), None)
        self.assertNotEqual(node2.validate(), None)
        self.assertNotEqual(node3.validate(), None)

        root.nodes = [node1, node2]
        self.assertEqual(root.validate(), None)
        self.assertEqual(node1.validate(), None)
        self.assertEqual(node2.validate(), None)
        self.assertNotEqual(node3.validate(), None)

        root.nodes = [node1, node2, node3]
        self.assertNotEqual(root.validate(), None)
        self.assertEqual(node1.validate(), None)
        self.assertEqual(node2.validate(), None)
        self.assertEqual(node3.validate(), None)

        # min_related=0, min_related_rev=1, max_related_rev=2
        class TestRoot(core.Model):
            id = core.SlugAttribute()

        class TestNode(core.Model):
            id = core.SlugAttribute()
            root = core.ManyToOneAttribute(
                TestRoot, related_name='nodes', min_related=0, min_related_rev=1, max_related_rev=2)

        root = TestRoot(id='a')
        node1 = TestNode(id='a')
        node2 = TestNode(id='b')
        node3 = TestNode(id='a')
        self.assertNotEqual(root.validate(), None)
        self.assertEqual(node1.validate(), None)
        self.assertEqual(node2.validate(), None)
        self.assertEqual(node3.validate(), None)

        root.nodes = [node1]
        self.assertEqual(root.validate(), None)
        self.assertEqual(node1.validate(), None)
        self.assertEqual(node2.validate(), None)
        self.assertEqual(node3.validate(), None)

        root.nodes = [node1, node2]
        self.assertEqual(root.validate(), None)
        self.assertEqual(node1.validate(), None)
        self.assertEqual(node2.validate(), None)
        self.assertEqual(node3.validate(), None)

        root.nodes = [node1, node2, node3]
        self.assertNotEqual(root.validate(), None)
        self.assertEqual(node1.validate(), None)
        self.assertEqual(node2.validate(), None)
        self.assertEqual(node3.validate(), None)

    def test_validate_many_to_many_num_related(self):
        # min_related=1, max_related=2, min_related_rev=1, max_related_rev=2
        class TestRoot(core.Model):
            id = core.SlugAttribute()

        class TestNode(core.Model):
            id = core.SlugAttribute()
            roots = core.ManyToManyAttribute(TestRoot, related_name='nodes',
                                             min_related=1, max_related=2, min_related_rev=1, max_related_rev=2)

        root1 = TestRoot(id='a')
        root2 = TestRoot(id='b')
        root3 = TestRoot(id='c')
        node1 = TestNode(id='a')
        node2 = TestNode(id='b')
        node3 = TestNode(id='a')
        self.assertNotEqual(root1.validate(), None)
        self.assertNotEqual(root2.validate(), None)
        self.assertNotEqual(root3.validate(), None)
        self.assertNotEqual(node1.validate(), None)
        self.assertNotEqual(node2.validate(), None)
        self.assertNotEqual(node3.validate(), None)

        root1.nodes = [node1]
        self.assertEqual(root1.validate(), None)
        self.assertNotEqual(root2.validate(), None)
        self.assertNotEqual(root3.validate(), None)
        self.assertEqual(node1.validate(), None)
        self.assertNotEqual(node2.validate(), None)
        self.assertNotEqual(node3.validate(), None)

        root1.nodes = [node1, node2]
        self.assertEqual(root1.validate(), None)
        self.assertNotEqual(root2.validate(), None)
        self.assertNotEqual(root3.validate(), None)
        self.assertEqual(node1.validate(), None)
        self.assertEqual(node2.validate(), None)
        self.assertNotEqual(node3.validate(), None)

        root1.nodes = [node1, node2, node3]
        self.assertNotEqual(root1.validate(), None)
        self.assertNotEqual(root2.validate(), None)
        self.assertNotEqual(root3.validate(), None)
        self.assertEqual(node1.validate(), None)
        self.assertEqual(node2.validate(), None)
        self.assertEqual(node3.validate(), None)

        root1.nodes = []
        node1.roots = [root1]
        self.assertEqual(root1.validate(), None)
        self.assertNotEqual(root2.validate(), None)
        self.assertNotEqual(root3.validate(), None)
        self.assertEqual(node1.validate(), None)
        self.assertNotEqual(node2.validate(), None)
        self.assertNotEqual(node3.validate(), None)

        node1.roots = [root1, root2]
        self.assertEqual(root1.validate(), None)
        self.assertEqual(root2.validate(), None)
        self.assertNotEqual(root3.validate(), None)
        self.assertEqual(node1.validate(), None)
        self.assertNotEqual(node2.validate(), None)
        self.assertNotEqual(node3.validate(), None)

        node1.roots = [root1, root2, root3]
        self.assertEqual(root1.validate(), None)
        self.assertEqual(root2.validate(), None)
        self.assertEqual(root3.validate(), None)
        self.assertNotEqual(node1.validate(), None)
        self.assertNotEqual(node2.validate(), None)
        self.assertNotEqual(node3.validate(), None)

    def test_onetoone_set_related(self):
        root = OneToOneRoot()
        leaf = OneToOneLeaf()

        root.leaf = leaf
        self.assertEqual(leaf.root, root)

        root.leaf = None
        self.assertEqual(leaf.root, None)

        leaf.root = root
        self.assertEqual(root.leaf, leaf)

        leaf.root = None
        self.assertEqual(root.leaf, None)

    def test_manytoone_set_related(self):
        roots = [
            ManyToOneRoot(id='root0'),
            ManyToOneRoot(id='root1'),
        ]
        leaves = [
            ManyToOneLeaf(id='leaf0'),
            ManyToOneLeaf(id='leaf1'),
        ]

        leaves[0].root = roots[0]
        self.assertEqual(roots[0].leaves, leaves[0:1])

        leaves[1].root = roots[0]
        self.assertEqual(set(roots[0].leaves), set(leaves[0:2]))

        leaves[0].root = None
        self.assertEqual(roots[0].leaves, leaves[1:2])

        roots[0].leaves = []
        self.assertEqual(roots[0].leaves, [])
        self.assertEqual(leaves[1].root, None)

        roots[0].leaves.add(leaves[0])
        self.assertEqual(roots[0].leaves, leaves[0:1])
        self.assertEqual(leaves[0].root, roots[0])

        roots[0].leaves.update(leaves[1:2])
        self.assertEqual(set(roots[0].leaves), set(leaves[0:2]))
        self.assertEqual(leaves[1].root, roots[0])

        roots[0].leaves.remove(leaves[0])
        self.assertEqual(roots[0].leaves, leaves[1:2])
        self.assertEqual(leaves[0].root, None)

        roots[0].leaves = []
        leaves[0].root = roots[0]
        leaves[0].root = roots[1]
        self.assertEqual(roots[0].leaves, [])
        self.assertEqual(roots[1].leaves, leaves[0:1])

        roots[0].leaves = leaves[0:1]
        self.assertEqual(roots[0].leaves, leaves[0:1])
        self.assertEqual(roots[1].leaves, [])
        self.assertEqual(leaves[0].root, roots[0])

        roots[1].leaves = leaves[0:2]
        self.assertEqual(roots[0].leaves, [])
        self.assertEqual(set(roots[1].leaves), set(leaves[0:2]))
        self.assertEqual(leaves[0].root, roots[1])
        self.assertEqual(leaves[1].root, roots[1])

    def test_onetomany_set_related(self):
        roots = [
            OneToManyRoot(id='root0'),
            OneToManyRoot(id='root1'),
        ]
        leaves = [
            OneToManyLeaf(id='leaf0'),
            OneToManyLeaf(id='leaf1'),
        ]

        roots[0].leaf = leaves[0]
        self.assertEqual(leaves[0].roots, roots[0:1])

        roots[1].leaf = leaves[0]
        self.assertEqual(set(leaves[0].roots), set(roots[0:2]))

        roots[0].leaf = None
        self.assertEqual(leaves[0].roots, roots[1:2])

        leaves[0].roots = []
        self.assertEqual(leaves[0].roots, [])
        self.assertEqual(roots[1].leaf, None)

        leaves[0].roots.add(roots[0])
        self.assertEqual(leaves[0].roots, roots[0:1])
        self.assertEqual(roots[0].leaf, leaves[0])

        leaves[0].roots.update(roots[1:2])
        self.assertEqual(set(leaves[0].roots), set(roots[0:2]))
        self.assertEqual(roots[1].leaf, leaves[0])

        leaves[0].roots.remove(roots[0])
        self.assertEqual(leaves[0].roots, roots[1:2])
        self.assertEqual(roots[0].leaf, None)

        leaves[0].roots = []
        roots[0].leaf = leaves[0]
        roots[0].leaf = leaves[1]
        self.assertEqual(leaves[0].roots, [])
        self.assertEqual(leaves[1].roots, roots[0:1])

        leaves[0].roots = roots[0:1]
        self.assertEqual(leaves[0].roots, roots[0:1])
        self.assertEqual(leaves[1].roots, [])
        self.assertEqual(roots[0].leaf, leaves[0])

        leaves[1].roots = roots[0:2]
        self.assertEqual(leaves[0].roots, [])
        self.assertEqual(set(leaves[1].roots), set(roots[0:2]))
        self.assertEqual(roots[0].leaf, leaves[1])
        self.assertEqual(roots[1].leaf, leaves[1])

    def test_manytomany_set_related(self):
        roots = [
            ManyToManyRoot(id='root0'),
            ManyToManyRoot(id='root1'),
        ]
        leaves = [
            ManyToManyLeaf(id='leaf0'),
            ManyToManyLeaf(id='leaf1'),
        ]

        roots[0].leaves.add(leaves[0])
        self.assertEqual(leaves[0].roots, roots[0:1])

        roots[0].leaves.remove(leaves[0])
        self.assertEqual(leaves[0].roots, [])

        roots[0].leaves.add(leaves[0])
        roots[1].leaves.add(leaves[0])
        self.assertEqual(set(leaves[0].roots), set(roots[0:2]))

        roots[0].leaves.clear()
        roots[1].leaves.clear()
        self.assertEqual(leaves[0].roots, [])
        self.assertEqual(leaves[1].roots, [])

        roots[0].leaves = leaves
        roots[1].leaves = leaves
        self.assertEqual(set(leaves[0].roots), set(roots[0:2]))
        self.assertEqual(set(leaves[1].roots), set(roots[0:2]))

        # reverse
        roots[0].leaves.clear()
        roots[1].leaves.clear()

        leaves[0].roots.add(roots[0])
        self.assertEqual(roots[0].leaves, leaves[0:1])

        leaves[0].roots.remove(roots[0])
        self.assertEqual(roots[0].leaves, [])

        leaves[0].roots.add(roots[0])
        leaves[1].roots.add(roots[0])
        self.assertEqual(set(roots[0].leaves), set(leaves[0:2]))

        leaves[0].roots.clear()
        leaves[1].roots.clear()
        self.assertEqual(roots[0].leaves, [])
        self.assertEqual(roots[1].leaves, [])

        leaves[0].roots = roots
        leaves[1].roots = roots
        self.assertEqual(set(roots[0].leaves), set(leaves[0:2]))
        self.assertEqual(set(roots[1].leaves), set(leaves[0:2]))

    def test_related_set_create(self):
        # many to one
        root = ManyToOneRoot()
        leaf = root.leaves.create(id='leaf')
        self.assertEqual(root.leaves, [leaf])
        self.assertEqual(leaf.root, root)

        # one to many
        leaf = OneToManyLeaf()
        root = leaf.roots.create(id='root')
        self.assertEqual(leaf.roots, [root])
        self.assertEqual(root.leaf, leaf)

        # many to many
        root_0 = ManyToManyRoot(id='root_0')

        leaf_0 = root_0.leaves.create(id='leaf_0')
        self.assertEqual(root_0.leaves, [leaf_0])
        self.assertEqual(leaf_0.roots, [root_0])

        root_1 = leaf_0.roots.create(id='root_1')
        self.assertEqual(root_1.leaves, [leaf_0])
        self.assertEqual(set(leaf_0.roots), set((root_0, root_1)))

    def test_related_set_filter_and_get_index(self):
        # many to one
        root = ManyToOneRoot()
        leaves = [
            ManyToOneLeaf(id='leaf_0'),
            ManyToOneLeaf(id='leaf_1'),
            ManyToOneLeaf(id='leaf_1'),
            ManyToOneLeaf(id='leaf_2'),
        ]
        root.leaves = leaves

        self.assertEqual(root.leaves.filter(id='leaf_0'), leaves[0:1])
        self.assertEqual(set(root.leaves.filter(id='leaf_1')),
                         set(leaves[1:3]))
        self.assertEqual(root.leaves.filter(id='leaf_2'), leaves[3:4])

        self.assertEqual(root.leaves.get(id='leaf_0'), leaves[0])
        self.assertRaises(ValueError, lambda: root.leaves.get(id='leaf_1'))
        self.assertEqual(root.leaves.get(id='leaf_2'), leaves[3])

        leaves_list = [l for l in root.leaves]
        self.assertEqual(root.leaves.index(id='leaf_0'),
                         leaves_list.index(leaves[0]))
        self.assertRaises(ValueError, lambda: root.leaves.index(id='leaf_1'))
        self.assertEqual(root.leaves.index(id='leaf_2'),
                         leaves_list.index(leaves[3]))

        self.assertEqual(root.leaves.index(
            leaves[0]), leaves_list.index(leaves[0]))
        self.assertEqual(root.leaves.index(
            leaves[1]), leaves_list.index(leaves[1]))
        self.assertEqual(root.leaves.index(
            leaves[2]), leaves_list.index(leaves[2]))
        self.assertEqual(root.leaves.index(
            leaves[3]), leaves_list.index(leaves[3]))

        # one to many
        leaf = OneToManyLeaf()
        roots = [
            OneToManyRoot(id='root_0'),
            OneToManyRoot(id='root_1'),
            OneToManyRoot(id='root_1'),
            OneToManyRoot(id='root_2'),
        ]
        leaf.roots = roots

        self.assertEqual(leaf.roots.filter(id='root_0'), roots[0:1])
        self.assertEqual(set(leaf.roots.filter(id='root_1')), set(roots[1:3]))
        self.assertEqual(leaf.roots.filter(id='root_2'), roots[3:4])

        self.assertEqual(leaf.roots.get(id='root_0'), roots[0])
        self.assertRaises(ValueError, lambda: leaf.roots.get(id='root_1'))
        self.assertEqual(leaf.roots.get(id='root_2'), roots[3])

        # many to many
        roots = [
            ManyToManyRoot(id='root_0'),
            ManyToManyRoot(id='root_1'),
            ManyToManyRoot(id='root_1'),
            ManyToManyRoot(id='root_2'),
        ]
        leaf = ManyToManyLeaf(roots=roots)

        self.assertEqual(leaf.roots.filter(id='root_0'), roots[0:1])
        self.assertEqual(set(leaf.roots.filter(id='root_1')), set(roots[1:3]))
        self.assertEqual(leaf.roots.filter(id='root_2'), roots[3:4])

        self.assertEqual(leaf.roots.get(id='root_0'), roots[0])
        self.assertRaises(ValueError, lambda: leaf.roots.get(id='root_1'))
        self.assertEqual(leaf.roots.get(id='root_2'), roots[3])

    def test_asymmetric_self_reference_one_to_one(self):
        class TestNodeAsymmetricOneToOne(core.Model):
            name = core.SlugAttribute()
            child = core.OneToOneAttribute(
                'TestNodeAsymmetricOneToOne', related_name='parent')

        parent = TestNodeAsymmetricOneToOne(name='parent_0')
        child = TestNodeAsymmetricOneToOne(name='child_0')
        parent.child = child
        self.assertEqual(child.parent, parent)

    def test_asymmetric_self_reference_one_to_many(self):
        class TestNodeAsymmetricOneToMany(core.Model):
            name = core.SlugAttribute()
            children = core.OneToManyAttribute(
                'TestNodeAsymmetricOneToMany', related_name='parent')

        parent = TestNodeAsymmetricOneToMany(name='parent_0')
        children = [
            TestNodeAsymmetricOneToMany(name='child_0'),
            TestNodeAsymmetricOneToMany(name='child_1'),
        ]
        parent.children.append(children[0])
        parent.children.append(children[1])

        self.assertEqual(parent.children, children)
        self.assertEqual(children[0].parent, parent)
        self.assertEqual(children[1].parent, parent)

    def test_asymmetric_self_reference_many_to_one(self):
        class TestNodeAsymmetricManyToOne(core.Model):
            name = core.SlugAttribute()
            parent = core.ManyToOneAttribute(
                'TestNodeAsymmetricManyToOne', related_name='children')

        parent = TestNodeAsymmetricManyToOne(name='parent_0')
        children = [
            TestNodeAsymmetricManyToOne(name='child_0'),
            TestNodeAsymmetricManyToOne(name='child_1'),
        ]
        parent.children.append(children[0])
        parent.children.append(children[1])

        self.assertEqual(parent.children, children)
        self.assertEqual(children[0].parent, parent)
        self.assertEqual(children[1].parent, parent)

    def test_asymmetric_self_reference_many_to_many(self):
        class TestNodeAsymmetricManyToMany(core.Model):
            name = core.SlugAttribute()
            children = core.ManyToManyAttribute(
                'TestNodeAsymmetricManyToMany', related_name='parents')

        parents = [
            TestNodeAsymmetricManyToMany(name='parent_0'),
            TestNodeAsymmetricManyToMany(name='parent_1'),
        ]
        children = [
            TestNodeAsymmetricManyToMany(name='child_0'),
            TestNodeAsymmetricManyToMany(name='child_1'),
        ]
        parents[0].children = children
        parents[1].children = children

        self.assertEqual(children[0].parents, parents)
        self.assertEqual(children[1].parents, parents)

    def test_symmetric_self_reference_one_to_one(self):
        class TestNodeSymmetricOneToOne(core.Model):
            name = core.SlugAttribute()
            other = core.OneToOneAttribute(
                'TestNodeSymmetricOneToOne', related_name='other')

        nodes = [
            TestNodeSymmetricOneToOne(name='node_0'),
            TestNodeSymmetricOneToOne(name='node_1'),
        ]
        nodes[0].other = nodes[1]
        self.assertEqual(nodes[1].other, nodes[0])
        nodes[0].validate()
        self.assertFalse(nodes[0].is_equal(nodes[1]))
        nodes[1].name = 'node_0'
        self.assertTrue(nodes[0].is_equal(nodes[1]))

        nodes[0].other = None
        nodes[0].other = nodes[0]
        nodes[0].validate()
        self.assertFalse(nodes[0].is_equal(nodes[1]))
        nodes[1].other = nodes[1]
        self.assertTrue(nodes[0].is_equal(nodes[1]))

    def test_symmetric_self_reference_one_to_many(self):
        def make_TestNodeSymmetricOneToMany():
            class TestNodeSymmetricOneToMany(core.Model):
                name = core.SlugAttribute()
                others = core.OneToManyAttribute(
                    'TestNodeSymmetricOneToMany', related_name='others')

        self.assertRaises(ValueError, make_TestNodeSymmetricOneToMany)

    def test_symmetric_self_reference_many_to_one(self):
        def make_TestNodeSymmetricManyToOne():
            class TestNodeSymmetricManyToOne(core.Model):
                name = core.SlugAttribute()
                others = core.OneToManyAttribute(
                    'TestNodeSymmetricManyToOne', related_name='others')

        self.assertRaises(ValueError, make_TestNodeSymmetricManyToOne)

    def test_symmetric_self_reference_many_to_many(self):
        class TestNodeSymmetricManyToMany(core.Model):
            name = core.SlugAttribute()
            others = core.ManyToManyAttribute(
                'TestNodeSymmetricManyToMany', related_name='others')

        nodes = [
            TestNodeSymmetricManyToMany(name='node_0'),
            TestNodeSymmetricManyToMany(name='node_1'),
            TestNodeSymmetricManyToMany(name='node_2'),
            TestNodeSymmetricManyToMany(name='node_3'),
        ]
        nodes[0].others = nodes[2:4]
        nodes[1].others = nodes[2:4]
        self.assertEqual(nodes[2].others, nodes[0:2])
        self.assertEqual(nodes[3].others, nodes[0:2])
        nodes[0].validate()
        nodes[1].validate()
        nodes[2].validate()
        nodes[3].validate()
        self.assertFalse(nodes[0].is_equal(nodes[1]))
        nodes[1].name = 'node_0'
        self.assertTrue(nodes[0].is_equal(nodes[1]))

        nodes[0].others = nodes[0:1]
        self.assertEqual(nodes[2].others, nodes[1:2])
        self.assertEqual(nodes[3].others, nodes[1:2])
        nodes[0].validate()
        self.assertFalse(nodes[0].is_equal(nodes[1]))
        nodes[1].others = nodes[1:2]
        self.assertTrue(nodes[0].is_equal(nodes[1]))

    def test_validator(self):
        grandparent = Grandparent(id='root')
        parents = [
            Parent(grandparent=grandparent, id='node-0'),
            Parent(grandparent=grandparent),
        ]

        errors = core.Validator().run(parents)
        self.assertEqual(len(errors.invalid_objects), 2)
        self.assertEqual(errors.invalid_objects[0].object, parents[0])
        self.assertEqual(len(errors.invalid_objects[0].attributes), 1)
        self.assertEqual(errors.invalid_objects[0].attributes[
                         0].attribute.name, 'id')

        roots = [
            Root(label='root-0'),
            Root(label='root-1'),
            Root(label='root-2'),
        ]
        errors = core.Validator().run(roots)
        self.assertEqual(errors, None)

        roots = [
            UniqueRoot(label='root_0', url='http://www.test.com'),
            UniqueRoot(label='root_0', url='http://www.test.com'),
            UniqueRoot(label='root_0', url='http://www.test.com'),
        ]
        errors = core.Validator().run(roots)

        self.assertEqual(len(errors.invalid_objects), 0)
        self.assertEqual(
            set([model.model for model in errors.invalid_models]), set((Root, UniqueRoot)))
        self.assertEqual(len(errors.invalid_models[0].attributes), 1)
        self.assertEqual(errors.invalid_models[0].attributes[
                         0].attribute.name, 'label')
        self.assertEqual(
            len(errors.invalid_models[0].attributes[0].messages), 1)
        self.assertRegexpMatches(errors.invalid_models[0].attributes[
                                 0].messages[0], 'values must be unique')

    def test_validator_related(self):
        class TestParent(core.Model):
            id = core.StringAttribute(min_length=4)

        class TestChild(core.Model):
            id = core.StringAttribute(min_length=4)
            value = core.FloatAttribute()
            parent = core.ManyToOneAttribute(TestParent, related_name='children')

        parent = TestParent(id='parent_0')
        child_0 = parent.children.create(id='c_0', value='c_0')
        child_1 = parent.children.create(id='c_1', value='c_1')

        errors = core.Validator().run(parent, get_related=True)
        self.assertIsInstance(errors, core.InvalidObjectSet)
        self.assertEqual(set([invalid_obj.object for invalid_obj in errors.invalid_objects]), set([child_0, child_1]))

    def test_inheritance(self):
        self.assertEqual(Leaf.Meta.attributes['name'].max_length, 255)
        self.assertEqual(UnrootedLeaf.Meta.attributes['name'].max_length, 10)

        self.assertEqual(set(Root.Meta.related_attributes.keys()),
                         set(('leaves', 'leaves2')))

        self.assertEqual(Leaf.Meta.attributes['root'].primary_class, Leaf)
        self.assertEqual(Leaf.Meta.attributes['root'].related_class, Root)
        self.assertEqual(UnrootedLeaf.Meta.attributes[
                         'root'].primary_class, Leaf)
        self.assertEqual(UnrootedLeaf.Meta.attributes[
                         'root'].related_class, Root)
        self.assertEqual(Leaf3.Meta.attributes['root'].primary_class, Leaf)
        self.assertEqual(Leaf3.Meta.attributes['root'].related_class, Root)

        self.assertEqual(UnrootedLeaf.Meta.attributes[
                         'root2'].primary_class, UnrootedLeaf)
        self.assertEqual(UnrootedLeaf.Meta.attributes[
                         'root2'].related_class, Root)
        self.assertEqual(Leaf3.Meta.attributes[
                         'root2'].primary_class, UnrootedLeaf)
        self.assertEqual(Leaf3.Meta.attributes['root2'].related_class, Root)

        self.assertEqual(Root.Meta.related_attributes[
                         'leaves'].primary_class, Leaf)
        self.assertEqual(Root.Meta.related_attributes[
                         'leaves'].related_class, Root)

        self.assertEqual(Root.Meta.related_attributes[
                         'leaves2'].primary_class, UnrootedLeaf)
        self.assertEqual(Root.Meta.related_attributes[
                         'leaves2'].related_class, Root)

        root = Root()
        leaf = Leaf(root=root)
        unrooted_leaf = UnrootedLeaf(root=root)

        self.assertEqual(leaf.root, root)
        self.assertEqual(unrooted_leaf.root, root)
        self.assertEqual(set(root.leaves), set((leaf, unrooted_leaf, )))

    def test_attribute_inheritance(self):
        X = type('X', (core.Model, ), {'label': core.StringAttribute()})
        Y = type('Y', (X, ), {'label': core.StringAttribute()})

        x = X(label='x')
        y = Y(label='y')

        self.assertRaises(ValueError, lambda: type('Z', (X, ), {'label': 'z'}))

        Z = type('Z', (Y, ), {'label': core.StringAttribute()})
        z = Z(label='z')

    def test_unique(self):
        roots = [
            UniqueTogetherRoot(val0='a', val1='a', val2='a'),
            UniqueTogetherRoot(val0='b', val1='b', val2='a'),
            UniqueTogetherRoot(val0='c', val1='c', val2='a'),
        ]
        self.assertEqual(UniqueTogetherRoot.validate_unique(roots), None)

        roots = [
            UniqueTogetherRoot(val0='a', val1='a', val2='a'),
            UniqueTogetherRoot(val0='a', val1='b', val2='a'),
            UniqueTogetherRoot(val0='a', val1='c', val2='a'),
        ]
        errors = [x.attribute.name for x in UniqueTogetherRoot.validate_unique(
            roots).attributes]
        self.assertEqual(errors, ['val0'])

        roots = [
            UniqueTogetherRoot(val0='a', val1='a', val2='a'),
            UniqueTogetherRoot(val0='b', val1='a', val2='a'),
            UniqueTogetherRoot(val0='c', val1='c', val2='a'),
        ]
        errors = [x.attribute.name for x in UniqueTogetherRoot.validate_unique(
            roots).attributes]
        self.assertNotIn('val0', errors)
        self.assertEqual(len(errors), 1)

    def test_copy(self):
        g1 = Grandparent(id='root-1')
        p1 = [
            Parent(grandparent=g1, id='node-1-0'),
            Parent(grandparent=g1, id='node-1-1'),
        ]
        c1 = [
            Child(parent=p1[0], id='leaf-1-0-0'),
            Child(parent=p1[0], id='leaf-1-0-1'),
            Child(parent=p1[1], id='leaf-1-1-0'),
            Child(parent=p1[1], id='leaf-1-1-1'),
        ]

        copy = g1.copy()
        self.assertFalse(copy is g1)
        self.assertTrue(g1.is_equal(copy))

    def test_pformat(self):
        root = Root(label='test-root')
        unrooted_leaf = UnrootedLeaf(root=root, id='a', id2='b', name2='ab', float2=2.4,
                                     float3=None, enum2=None, enum3=Order['leaf'])
        expected = \
            '''UnrootedLeaf:
    id: a
    name: 
    root: 
        Root:
            label: test-root
            leaves: 
            leaves2: 
    enum2: None
    enum3: Order.leaf
    float2: 2.4
    float3: None
    id2: b
    multi_word_name: 
    name2: ab
    root2: None'''
        self.assertEqual(expected, unrooted_leaf.pformat(indent=4))

        class Root0(core.Model):
            label = core.SlugAttribute()
            f = core.FloatAttribute()

        class Node0(core.Model):
            id = core.SlugAttribute()
            root = core.OneToOneAttribute(Root0, related_name='node')
        root0 = Root0(label='root0-1', f=3.14)
        node0 = Node0(id='node0-1', root=root0)
        # pformat()s of root0 and node0 contain each other's lines, except for
        # lines with re-encountered Models
        for (this, other) in [(root0, node0), (node0, root0)]:
            for this_line in this.pformat().split('\n'):
                if '--' not in this_line:
                    self.assertIn(this_line.strip(), other.pformat())

        class Root1(core.Model):
            label = core.SlugAttribute()

        class Node1(core.Model):
            id = core.SlugAttribute()
            roots = core.OneToManyAttribute(Root1, related_name='node')

        class Root2(core.Model):
            label = core.StringAttribute()

        class Node2(core.Model):
            id = core.StringAttribute()
            root = core.ManyToOneAttribute(Root2, related_name='nodes')

        NUM = 3
        roots1 = [Root1(label='root_{}'.format(i)) for i in range(NUM)]
        node1 = Node1(id='node1', roots=roots1)
        expected = \
            '''Root1:
    label: root_0
    node: 
        Node1:
            id: node1
            roots: 
                Root1:
                    label: root_1
                    node: --
                Root1:
                    label: root_2
                    node: --'''
        self.assertEqual(expected, roots1[0].pformat(indent=4))
        self.assertEqual(node1.pformat(max_depth=1).count('label: root'), NUM)
        self.assertEqual(node1.pformat(max_depth=0).count('Root1: ...'), NUM)

        class Root3(core.Model):
            label = core.StringAttribute()

        class Node3(core.Model):
            id = core.StringAttribute()
            roots = core.ManyToManyAttribute(Root3, related_name='nodes')
        root3s = [Root3(label='root3_{}'.format(i)) for i in range(NUM)]
        node3s = [Node3(id='node3_{}'.format(i), roots=root3s)
                  for i in range(NUM)]

        # the lines in root3_tree are all in node3_tree
        default_depth_plus_3 = core.Model.DEFAULT_MAX_DEPTH+3
        root3_tree = root3s[0].pformat(max_depth=default_depth_plus_3)
        node3_tree = node3s[0].pformat(max_depth=default_depth_plus_3)
        for root3_line in root3_tree.split('\n'):
            self.assertIn(root3_line.strip(), node3_tree)

        root = DateRoot()
        root.date = date(2000, 10, 1)
        root.datetime = datetime(1900, 1, 1, 0, 0, 0, 0)
        root.time = time(0, 0, 0, 0)
        self.assertIn('time: 0.0', root.pformat())

    def test_difference(self):
        g = [
            Grandparent(id='g', val='gparent_0'),
            Grandparent(id='g', val='gparent_0'),
        ]
        p = [
            Parent(grandparent=g[0], id='p_0', val='parent_0'),
            Parent(grandparent=g[0], id='p_1', val='parent_1'),
            Parent(grandparent=g[1], id='p_0', val='parent_0'),
            Parent(grandparent=g[1], id='p_1', val='parent_1'),
        ]
        c = [
            Child(parent=p[0], id='c_0_0', val='child_0_0'),
            Child(parent=p[0], id='c_0_1', val='child_0_1'),
            Child(parent=p[1], id='c_1_0', val='child_1_0'),
            Child(parent=p[1], id='c_1_1', val='child_1_1'),
            Child(parent=p[2], id='c_0_0', val='child_0_0'),
            Child(parent=p[2], id='c_0_1', val='child_0_1'),
            Child(parent=p[3], id='c_1_0', val='child_1_0'),
            Child(parent=p[3], id='c_1_1', val='child_1_1'),
        ]

        self.assertTrue(g[1].is_equal(g[0]))
        self.assertEqual(g[0].difference(g[1]), '')

        g[1].val = 'gparent_1'
        msg = (
            'Objects (Grandparent: "g", Grandparent: "g") have different attribute values:\n'
            '  `val` are not equal:\n'
            '    gparent_0 != gparent_1'
        )
        self.assertFalse(g[1].is_equal(g[0]))
        self.assertEqual(g[0].difference(g[1]), msg, '\n\n' +
                         g[0].difference(g[1]) + '\n\n' + msg)

        g[1].val = 'gparent_1'
        c[4].val = 'child_3_0'
        msg = (
            'Objects (Grandparent: "g", Grandparent: "g") have different attribute values:\n'
            '  `val` are not equal:\n'
            '    gparent_0 != gparent_1\n'
            '  `children` are not equal:\n'
            '    element: Parent: "p_0" != element: Parent: "p_0"\n'
            '      Objects (Parent: "p_0", Parent: "p_0") have different attribute values:\n'
            '        `children` are not equal:\n'
            '          element: Child: "c_0_0" != element: Child: "c_0_0"\n'
            '            Objects (Child: "c_0_0", Child: "c_0_0") have different attribute values:\n'
            '              `val` are not equal:\n'
            '                child_0_0 != child_3_0'
        )
        self.assertFalse(g[1].is_equal(g[0]))
        self.assertEqual(g[0].difference(g[1]), msg, '\n\n' +
                         g[0].difference(g[1]) + '\n\n' + msg)

        g[1].val = 'gparent_0'
        c[4].val = 'child_3_0'
        msg = (
            'Objects (Grandparent: "g", Grandparent: "g") have different attribute values:\n'
            '  `children` are not equal:\n'
            '    element: Parent: "p_0" != element: Parent: "p_0"\n'
            '      Objects (Parent: "p_0", Parent: "p_0") have different attribute values:\n'
            '        `children` are not equal:\n'
            '          element: Child: "c_0_0" != element: Child: "c_0_0"\n'
            '            Objects (Child: "c_0_0", Child: "c_0_0") have different attribute values:\n'
            '              `val` are not equal:\n'
            '                child_0_0 != child_3_0'
        )
        self.assertFalse(g[1].is_equal(g[0]))
        self.assertEqual(g[0].difference(g[1]), msg, '\n\n' +
                         g[0].difference(g[1]) + '\n\n' + msg)

        g[1].val = 'gparent_0'
        c[4].val = 'child_3_0'
        c[5].val = 'child_3_1'
        msg = (
            'Objects (Grandparent: "g", Grandparent: "g") have different attribute values:\n'
            '  `children` are not equal:\n'
            '    element: Parent: "p_0" != element: Parent: "p_0"\n'
            '      Objects (Parent: "p_0", Parent: "p_0") have different attribute values:\n'
            '        `children` are not equal:\n'
            '          element: Child: "c_0_0" != element: Child: "c_0_0"\n'
            '            Objects (Child: "c_0_0", Child: "c_0_0") have different attribute values:\n'
            '              `val` are not equal:\n'
            '                child_0_0 != child_3_0\n'
            '          element: Child: "c_0_1" != element: Child: "c_0_1"\n'
            '            Objects (Child: "c_0_1", Child: "c_0_1") have different attribute values:\n'
            '              `val` are not equal:\n'
            '                child_0_1 != child_3_1'
        )
        self.assertFalse(g[1].is_equal(g[0]))
        self.assertEqual(g[0].difference(g[1]), msg, '\n\n' +
                         g[0].difference(g[1]) + '\n\n' + msg)

        g[1].val = 'gparent_0'
        c[4].val = 'child_3_0'
        c[4].id = 'c_3_0'
        c[5].val = 'child_3_1'
        c[5].id = 'c_3_1'
        msg = (
            'Objects (Grandparent: "g", Grandparent: "g") have different attribute values:\n'
            '  `children` are not equal:\n'
            '    element: Parent: "p_0" != element: Parent: "p_0"\n'
            '      Objects (Parent: "p_0", Parent: "p_0") have different attribute values:\n'
            '        `children` are not equal:\n'
            '          No matching element c_0_0\n'
            '          No matching element c_0_1'
        )
        self.assertFalse(g[1].is_equal(g[0]))
        self.assertEqual(g[0].difference(g[1]), msg, '\n\n' +
                         g[0].difference(g[1]) + '\n\n' + msg)

    def test_invalid_attribute_str(self):
        attr = core.StringAttribute()
        attr.name = 'attr'
        msgs = ['msg1', 'msg2\ncontinue']
        err = core.InvalidAttribute(attr, msgs)
        self.assertEqual(str(err),
                         "'{}':\n  {}\n  {}".format(attr.name, msgs[0], msgs[1].replace('\n', '\n  ')))

        class TestChild(core.Model):
            id = core.StringAttribute(primary=True)

        class TestParent(core.Model):
            id = core.StringAttribute(primary=True)
            children = core.OneToManyAttribute(TestChild, related_name='parent', min_related_rev=1)

        child = TestChild(id='child')

        error = child.validate().attributes[0]
        self.assertRegexpMatches(str(error), "parent':\n  Value cannot be `None`")

    def test_invalid_object_str(self):
        attrs = [
            core.StringAttribute(),
            core.StringAttribute(),
        ]
        attrs[0].name = 'attr0'
        attrs[1].name = 'attr1'
        msgs = ['msg00', 'msg01\ncontinue', 'msg10', 'msg11']
        attr_errs = [
            core.InvalidAttribute(attrs[0], msgs[0:2]),
            core.InvalidAttribute(attrs[1], msgs[2:4]),
        ]
        obj = Grandparent(id='gp')
        err = core.InvalidObject(obj, attr_errs)
        self.assertEqual(str(err), (
            "'{}':\n".format(attrs[0].name) +
            "  {}\n".format(msgs[0]) +
            "  {}\n".format(msgs[1].replace("\n", "\n  ")) +
            "'{}':\n".format(attrs[1].name) +
            "  {}\n".format(msgs[2]) +
            "  {}".format(msgs[3])
        ))

    def test_invalid_model_str(self):
        attrs = [
            core.StringAttribute(),
            core.StringAttribute(),
        ]
        attrs[0].name = 'attr0'
        attrs[1].name = 'attr1'
        msgs = ['msg00', 'msg01\ncontinue', 'msg10', 'msg11']
        attr_errs = [
            core.InvalidAttribute(attrs[0], msgs[0:2]),
            core.InvalidAttribute(attrs[1], msgs[2:4]),
        ]
        err = core.InvalidModel(Grandparent, attr_errs)
        self.assertEqual(str(err), (
            "'{}':\n".format(attrs[0].name) +
            "  {}\n".format(msgs[0]) +
            "  {}\n".format(msgs[1].replace("\n", "\n  ")) +
            "'{}':\n".format(attrs[1].name) +
            "  {}\n".format(msgs[2]) +
            "  {}".format(msgs[3])
        ))

    def test_invalid_object_set_exception(self):
        p = Parent(id='parent')
        invalid_model = core.InvalidModel(p, [])
        self.assertRaises(ValueError,
                          lambda: core.InvalidObjectSet([], [invalid_model, invalid_model]))

    # .. todo :: fix InvalidObjectSet.str()
    @unittest.skip('skipping until I (Arthur Goldberg) have time to do a detailed comparison')
    def test_invalid_object_set_str(self):
        attr = core.Attribute()
        attr.name = 'attr'
        msg = 'msg\ncontinue'
        attr_err = core.InvalidAttribute(attr, [msg, msg])
        gp = Grandparent(id='gp')
        p = Parent(id='parent')
        obj_err_gp = core.InvalidObject(gp, [attr_err, attr_err])
        obj_err_p = core.InvalidObject(p, [attr_err, attr_err])
        mod_err_gp = core.InvalidModel(Grandparent, [attr_err, attr_err])
        mod_err_p = core.InvalidModel(Parent, [attr_err, attr_err])
        err = core.InvalidObjectSet([obj_err_gp, obj_err_gp, obj_err_p, obj_err_p], [
                                    mod_err_gp, mod_err_p])

        self.assertEqual(str(err), (
            '{}:\n'.format(Grandparent.__name__) +
            "  '{}':\n".format(attr.name) +
            '    {}\n'.format(msg.replace('\n', '\n    ')) +
            '    {}\n'.format(msg.replace('\n', '\n    ')) +
            "  '{}':\n".format(attr.name) +
            '    {}\n'.format(msg.replace('\n', '\n    ')) +
            '    {}\n'.format(msg.replace('\n', '\n    ')) +
            '  \n' +
            '    {}:\n'.format(attr.name) +
            '      {}\n'.format(msg.replace('\n', '\n      ')) +
            '      {}\n'.format(msg.replace('\n', '\n      ')) +
            '    {}:\n'.format(attr.name) +
            '      {}\n'.format(msg.replace('\n', '\n      ')) +
            '      {}\n'.format(msg.replace('\n', '\n      ')) +
            '  \n' +
            '    {}:\n'.format(attr.name) +
            '      {}\n'.format(msg.replace('\n', '\n      ')) +
            '      {}\n'.format(msg.replace('\n', '\n      ')) +
            '    {}:\n'.format(attr.name) +
            '      {}\n'.format(msg.replace('\n', '\n      ')) +
            '      {}\n'.format(msg.replace('\n', '\n      ')) +
            '{}:\n'.format(Parent.__name__) +
            "  '{}':\n".format(attr.name) +
            '    {}\n'.format(msg.replace('\n', '\n    ')) +
            '    {}\n'.format(msg.replace('\n', '\n    ')) +
            "  '{}':\n".format(attr.name) +
            '    {}\n'.format(msg.replace('\n', '\n    ')) +
            '    {}\n'.format(msg.replace('\n', '\n    ')) +
            '  \n' +
            '    {}:\n'.format(attr.name) +
            '      {}\n'.format(msg.replace('\n', '\n      ')) +
            '      {}\n'.format(msg.replace('\n', '\n      ')) +
            '    {}:\n'.format(attr.name) +
            '      {}\n'.format(msg.replace('\n', '\n      ')) +
            '      {}\n'.format(msg.replace('\n', '\n      ')) +
            '  \n' +
            '    {}:\n'.format(attr.name) +
            '      {}\n'.format(msg.replace('\n', '\n      ')) +
            '      {}\n'.format(msg.replace('\n', '\n      ')) +
            '    {}:\n'.format(attr.name) +
            '      {}\n'.format(msg.replace('\n', '\n      ')) +
            '      {}'.format(msg.replace('\n', '\n      '))
        ))

    def test_excel_col_name(self):
        self.assertRaises(ValueError, lambda: excel_col_name(0))
        self.assertRaises(ValueError, lambda: excel_col_name(''))
        self.assertEqual(excel_col_name(5), 'E')
        self.assertEqual(excel_col_name(2**14), 'XFD')

    def test_manager_small_methods(self):
        class Foo(object):

            def __init__(self, a, b):
                self.a = a
                self.b = b
        attrs = ('a', 'b')
        vals = ('hi', 3)
        f1 = Foo(*vals)
        self.assertEqual(vals, core.Manager._get_attr_tuple_vals(f1, attrs))

        # test _get_hashable_values
        t0 = Example0()
        vs, vi = 's', 1
        t1a = Example1(str_attr=vs, int_attr=vi, test0=t0)
        hashable_values = core.Manager._get_hashable_values(
            (t1a.str_attr, t1a.int_attr, t1a.test0))
        id_t0 = id(t0)
        self.assertEqual(id_t0, id(t0))
        self.assertEqual((id_t0,), (id(t0),))
        # self.assertEqual((vs, vi, id(t0)), hashable_values) fails, but the
        # assertion below succeeds
        self.assertEqual((vs, vi, id_t0), hashable_values)
        s = set()
        try:
            s.add(hashable_values)
        except Exception:
            self.fail(
                "Manager._get_hashable_values() returns values that are not hashable")

        t0s = [Example0() for i in range(3)]
        ids = tuple(sorted([id(t0) for t0 in t0s]))
        t1b = Example1()
        t1b.test0s.extend(t0s)
        hashable_values = core.Manager._get_hashable_values((t1b.test0s,))
        self.assertEqual((ids,), hashable_values)
        try:
            s.add(hashable_values)
        except Exception:
            self.fail(
                "Manager._get_hashable_values() returns values that are not hashable")

        with self.assertRaises(ValueError) as context:
            core.Manager._get_hashable_values('abc')
        self.assertIn("_get_hashable_values does not take a string",
                      str(context.exception))
        with self.assertRaises(ValueError) as context:
            core.Manager._get_hashable_values(3)
        self.assertIn("_get_hashable_values takes an iterable, not",
                      str(context.exception))

        # test _hashable_attr_tup_vals
        self.assertEqual((vs, vi, id_t0),
                         core.Manager._hashable_attr_tup_vals(t1a, ('str_attr', 'int_attr', 'test0')))

        # test _get_attribute_types
        mgr1 = core.Manager(Example1)
        self.assertEqual((core.OneToOneAttribute, core.StringAttribute, core.IntegerAttribute),
                         tuple([attr.__class__
                                for attr in mgr1._get_attribute_types(t1a, ('test0', 'str_attr', 'int_attr'))]))

        mgr0 = core.Manager(Example0)
        t0a = Example0()
        t1c = Example1(test0=t0a)
        self.assertTrue(isinstance(mgr0._get_attribute_types(
            t0a, ('test1',))[0], core.OneToOneAttribute))

        bad_attr = 'no_attr'
        with self.assertRaises(ValueError) as context:
            mgr1._get_attribute_types(t1a, (bad_attr,))
        self.assertIn("Cannot find '{}' in attribute names".format(
            bad_attr), str(context.exception))

        with self.assertRaises(ValueError) as context:
            mgr1._get_attribute_types(t1a, 'abc')
        self.assertIn("_get_attribute_types(): attr_names cannot be a string", str(
            context.exception))
        with self.assertRaises(ValueError) as context:
            mgr1._get_attribute_types(t1a, 3)
        self.assertIn("_get_attribute_types(): attr_names must be an iterable", str(
            context.exception))

    def test_manager(self):
        self.assertEqual(Example1.objects, Example1.get_manager())
        mgr1 = Example1.get_manager()
        mgr1.clear_new_instances()

        # test all()
        self.assertEqual(0, len(set(mgr1.all())))
        FIRST = 12
        t1s = [Example1(int_attr=i+FIRST) for i in range(4)]
        mgr1.insert_all_new()
        self.assertEqual(set(t1s), set(mgr1.all()))

        # test get() with no arguments
        with self.assertRaises(ValueError) as context:
            mgr1.get()
        self.assertIn('No arguments provided in get()', str(context.exception))

        # test get() with an attribute that's not an indexed_attribute
        with self.assertRaises(ValueError) as context:
            Example1.objects.get(non_indexed_attribute=7)
        self.assertIn('not an indexed attribute tuple in',
                      str(context.exception))

        # test get() return nothing
        self.assertEqual(None, Example1.objects.get(str_attr='x'))

        # test get() on Model not indexed
        self.assertEqual(None, Example2.objects.get(str_attr='x'))

        # test _insert_new()
        letters = 'ABC'
        test_attrs = zip(letters, range(len(letters)))
        more_t1s = [Example1(str_attr=s, int_attr=i, int_attr2=i+1)
                    for s, i in test_attrs]
        mgr1._insert_new(more_t1s[0])

        # test get() w multiple attributes
        kwargs = dict(zip(('int_attr', 'int_attr2'), range(2)))
        self.assertIn(more_t1s[0], Example1.objects.get(**kwargs))

        # test get() of recently inserted objects
        self.assertEqual(1, len(Example1.objects.get(str_attr='A')))
        self.assertIn(more_t1s[0], Example1.objects.get(str_attr='A'))
        with self.assertRaises(ValueError) as context:
            mgr1._insert_new(t1s[0])
        self.assertIn("Cannot _insert_new() an instance of 'Example1' that is not new", str(
            context.exception))

        # test get() return multiple Models
        copy_t1s_0 = more_t1s[0].copy()
        mgr1._insert_new(copy_t1s_0)
        self.assertEqual(2, len(mgr1.get(str_attr='A')))
        self.assertIn(more_t1s[0], mgr1.get(str_attr='A'))
        self.assertIn(copy_t1s_0, mgr1.get(str_attr='A'))

        # test get_one()
        # return no instance
        self.assertEqual(None, mgr1.get_one(str_attr='B'))
        # return 1
        self.assertEqual(t1s[0], mgr1.get_one(int_attr=FIRST, int_attr2=None))
        # return > 1
        with self.assertRaises(ValueError) as context:
            mgr1.get_one(str_attr='A')
        self.assertIn("get_one(): 2 Example1 instances with".format(len(mgr1.get(str_attr='A'))),
                      str(context.exception))

        output = six.StringIO()
        mgr1._dump_index_dicts(file=output)
        content = output.getvalue()
        for s in ["Dicts", "indexed attr tuple:", "Reverse dicts for", "model at"]:
            self.assertIn(s, content)

        # test weakrefs
        for i in range(1, len(more_t1s)):
            mgr1._insert_new(more_t1s[i])
        self.assertEqual(1, len(mgr1.get(str_attr='B')))
        del more_t1s[:]
        # models without strong refs disappear from indices after gc
        gc.collect()
        self.assertEqual(None, mgr1.get(str_attr='B'))

        tmp = Example1()
        self.assertIn(tmp, mgr1._new_instances)
        s = len(mgr1._new_instances)
        tmp = None
        gc.collect()
        self.assertEqual(s-1, len(mgr1._new_instances))

        unused_val = 1234243
        tmp = Example1(int_attr2=unused_val)
        mgr1._insert_new(tmp)
        self.assertIn(tmp, mgr1._reverse_index)
        tmp = None
        gc.collect()
        for m in mgr1.all():
            self.assertNotEqual(unused_val, m.int_attr2)

        # test _gc_weaksets
        mgr0 = Example0.get_manager()
        make = 9
        l = [Example0(int_attr=i) for i in range(make)]
        mgr0.insert_all_new()
        self.assertEqual(0, mgr0._gc_weaksets())
        n = 3
        del l[n:]
        gc.collect()
        self.assertEqual(make-n, mgr0._gc_weaksets())

        # test _run_gc_weaksets()
        l2 = [Example0(int_attr=unused_val+1)]
        mgr0._insert_new(l2[0])
        mgr0.num_ops_since_gc = 0
        for i in range(core.Manager.GC_PERIOD-1):
            self.assertEqual(0, mgr0._run_gc_weaksets())
        del l2[:]
        gc.collect()
        self.assertEqual(1, mgr0._run_gc_weaksets())

        # test wrong model type
        t = Example1()
        with self.assertRaises(ValueError) as context:
            mgr0._update(t)
        self.assertIn("The 'Example0' Manager does not process 'Example1' objects", str(
            context.exception))

        t = Example0()
        with self.assertRaisesRegexp(ValueError, "Can't _update an instance of "):
            mgr0._update(t)

        # test _update
        mgr1.reset()
        t1 = Example1(str_attr='x')
        mgr1._insert_new(t1)
        t1.str_attr = 'y'
        mgr1._update(t1)
        self.assertEqual(None, mgr1.get(str_attr='x'))
        self.assertEqual(t1, mgr1.get(str_attr='y').pop())

        # test insert_all_new
        mgr1.reset()
        n = 5
        t1s = [Example1(int_attr=i, int_attr2=i+1) for i in range(n)]
        mgr1.insert_all_new()
        for i in range(n):
            self.assertEqual(t1s[i], mgr1.get_one(int_attr=i, int_attr2=i+1))

        # test upsert and upsert_all
        mgr1.reset()
        t1 = Example1(str_attr='x')
        mgr1.upsert(t1)
        self.assertIn(t1, mgr1.get(str_attr='x'))
        self.assertEqual(t1, mgr1.get_one(str_attr='x'))
        t1.str_attr = 'y'
        mgr1.upsert(t1)
        self.assertEqual(None, mgr1.get(str_attr='x'))
        self.assertIn(t1, mgr1.get(str_attr='y'))
        n = 5
        t1s = [Example1(int_attr=i, int_attr2=i+1) for i in range(n)]
        mgr1.insert_all_new()
        for t1 in t1s:
            t1.int_attr += 1
        mgr1.upsert_all()
        for i in range(n):
            self.assertEqual(t1s[i], mgr1.get_one(int_attr=i+1, int_attr2=i+1))

        # test index on related objects
        mgr1.reset()
        t0 = Example0(int_attr=1)
        t1 = Example1(str_attr='x', test0=t0)
        mgr1.insert_all_new()
        self.assertEqual(mgr1.get_one(test0=id(t0)), t1)

        t2 = Example2()
        with self.assertRaises(ValueError) as context:
            Example2.objects._check_model(t2, 'test')
        self.assertIn("'{}' Manager does not have any indexed attribute tuples".format(Example2.__name__),
                      str(context.exception))
        self.assertEqual(Example2.objects.all(), None)

    def test_simple_manager_example(self):
        from obj_model.core import Model, StringAttribute, IntegerAttribute, OneToManyAttribute

        class Example1(Model):
            str_attr = StringAttribute()
            int_attr = IntegerAttribute()
            int_attr2 = IntegerAttribute()

            class Meta(Model.Meta):
                indexed_attrs_tuples = (
                    ('str_attr',), ('int_attr', 'int_attr2'), )

        mgr1 = Example1.get_manager()
        e1 = Example1(str_attr='s')
        e2 = Example1(str_attr='s', int_attr=1, int_attr2=3)
        mgr1.insert_all_new()
        mgr1.get(str_attr='s')              # get e1 and e2
        self.assertIn(e1, mgr1.get(str_attr='s'))
        self.assertIn(e2, mgr1.get(str_attr='s'))
        mgr1.get(int_attr=1, int_attr2=3)   # get e2
        self.assertIn(e2, mgr1.get(int_attr=1, int_attr2=3))
        e2.str_attr = 't'
        mgr1.upsert(e2)
        mgr1.get(str_attr='t')              # get e2
        self.assertIn(e2, mgr1.get(str_attr='t'))

        # test weak refs
        mgr1 = Example1.get_manager()
        val = 'unique apg'
        e1 = Example1(str_attr=val)
        mgr1.upsert(e1)
        self.assertIn(e1, mgr1.get(str_attr=val))
        # models without strong refs disappear from indices after gc
        e1 = None
        gc.collect()
        self.assertEqual(None, mgr1.get(str_attr=val))

    def test_sort(self):
        roots = [
            Root(label='c'),
            Root(label='d'),
            Root(label='a'),
            Root(label='b'),
        ]

        roots2 = Root.sort(roots)
        self.assertEqual(roots[0].label, 'c')
        self.assertEqual(roots[1].label, 'd')
        self.assertEqual(roots[2].label, 'a')
        self.assertEqual(roots[3].label, 'b')

        self.assertEqual(roots2[0].label, 'a')
        self.assertEqual(roots2[1].label, 'b')
        self.assertEqual(roots2[2].label, 'c')
        self.assertEqual(roots2[3].label, 'd')

        self.assertEqual(roots2[0], roots[2])
        self.assertEqual(roots2[1], roots[3])
        self.assertEqual(roots2[2], roots[0])
        self.assertEqual(roots2[3], roots[1])

    def test_normalize(self):
        class NormNodeLevel0(core.Model):
            label = core.StringAttribute(primary=True, unique=True)

        class NormNodeLevel1(core.Model):
            label = core.StringAttribute(primary=True, unique=True)
            parent = core.ManyToOneAttribute(
                NormNodeLevel0, related_name='children')

        class NormNodeLevel2(core.Model):
            label = core.StringAttribute(primary=True, unique=True)
            parent = core.ManyToOneAttribute(
                NormNodeLevel1, related_name='children')

        class NormNodeLevel3(core.Model):
            label = core.StringAttribute()

        # example
        node_0 = NormNodeLevel0()

        node_0_c = node_0.children.create(label='c')
        node_0_a = node_0.children.create(label='a')
        node_0_b = node_0.children.create(label='b')

        node_0_a_a = node_0_a.children.create(label='a_a')
        node_0_a_c = node_0_a.children.create(label='a_c')
        node_0_a_b = node_0_a.children.create(label='a_b')

        node_0_b_a = node_0_b.children.create(label='b_a')
        node_0_b_c = node_0_b.children.create(label='b_c')
        node_0_b_b = node_0_b.children.create(label='b_b')

        node_0_c_a = node_0_c.children.create(label='c_a')
        node_0_c_c = node_0_c.children.create(label='c_c')
        node_0_c_b = node_0_c.children.create(label='c_b')

        # test
        node_0.normalize()

        self.assertEqual(node_0.children, [node_0_a, node_0_b, node_0_c])

        self.assertEqual(node_0.children[0].children, [
                         node_0_a_a, node_0_a_b, node_0_a_c])
        self.assertEqual(node_0.children[1].children, [
                         node_0_b_a, node_0_b_b, node_0_b_c])
        self.assertEqual(node_0.children[2].children, [
                         node_0_c_a, node_0_c_b, node_0_c_c])

        # example
        node_0 = NormNodeLevel0(label='node_0')
        node_1 = NormNodeLevel1(parent=node_0, label='node_1')
        node_2_a = NormNodeLevel2(parent=node_1, label='node_a')
        node_2_b = NormNodeLevel2(parent=node_1, label='node_b')
        node_2_d = NormNodeLevel2(parent=node_1, label='node_d')
        node_2_c = NormNodeLevel2(parent=node_1, label='node_c')

        node_0.normalize()
        self.assertEqual(node_1.children, [
                         node_2_a, node_2_b, node_2_c, node_2_d])

    def test_setter(self):
        class Site(core.Model):
            id = core.StringAttribute(primary=True, unique=True)

        class AddBond(core.Model):
            sites = core.OneToManyAttribute(Site, related_name='operation')

            @property
            def targets(self):
                """ Get targets

                Returns:
                    :obj:`list` of :obj:`Site`: list of targets
                """
                return self.sites

            @targets.setter
            def targets(self, value):
                """ Set targets

                Args:
                    value (:obj:`list` of :obj:`Site`): list of targets
                """
                self.sites = value

        s1 = Site(id='site1')
        s2 = Site(id='site2')
        self.assertEqual(s1.operation, None)
        self.assertEqual(s2.operation, None)

        add_bond1 = AddBond(sites=[s1, s2])
        self.assertEqual(set(add_bond1.sites), set([s1, s2]))
        self.assertEqual(set(add_bond1.targets), set([s1, s2]))

        add_bond2 = AddBond()
        add_bond2.targets = [s1, s2]
        self.assertEqual(set(add_bond2.sites), set([s1, s2]))
        self.assertEqual(set(add_bond2.targets), set([s1, s2]))

        self.assertRaises(
            TypeError, "targets' is an invalid keyword argument for AddBond.__init__", AddBond, targets=[s1, s2])

    def test_chaining_many_to_one(self):
        class Mother(core.Model):
            id = core.SlugAttribute()

        class Daughter(core.Model):
            id = core.SlugAttribute()
            mother = core.ManyToOneAttribute(Mother, related_name='daughters')

        m = Mother()
        d1 = Daughter()
        d2 = Daughter()
        self.assertEqual(m.daughters.add(d1), m.daughters)
        self.assertEqual(m.daughters.add(d2), m.daughters)
        self.assertEqual(m.daughters.remove(d1), m.daughters)
        self.assertEqual(m.daughters.extend([d1]), m.daughters)
        self.assertEqual(m.daughters.discard(d2), m.daughters)
        self.assertEqual(m.daughters.update([d2]), m.daughters)
        self.assertEqual(m.daughters.clear(), m.daughters)
        self.assertEqual(m.daughters.extend([d1, d2]), m.daughters)
        self.assertEqual(m.daughters.intersection_update([d1]), m.daughters)
        self.assertEqual(set(m.daughters), set([d1]))
        self.assertEqual(m.daughters.difference_update([d1]), m.daughters)
        self.assertEqual(set(m.daughters), set([]))
        self.assertEqual(m.daughters.extend([d1, d2]), m.daughters)
        self.assertEqual(
            m.daughters.symmetric_difference_update([d1]), m.daughters)
        self.assertEqual(set(m.daughters), set([d2]))

        m = Mother()
        d1 = Daughter()
        d2 = Daughter()
        m.daughters \
            .add(d1) \
            .add(d2) \
            .remove(d1) \
            .extend([d1]) \
            .discard(d2) \
            .update([d2]) \
            .clear() \
            .extend([d1, d2]) \
            .intersection_update([d1]) \
            .difference_update([d1]) \
            .extend([d1, d2]) \
            .symmetric_difference_update([d1])
        self.assertEqual(set(m.daughters), set([d2]))

    def test_chaining_one_to_many(self):
        class Daughter(core.Model):
            id = core.SlugAttribute()

        class Mother(core.Model):
            id = core.SlugAttribute()
            daughters = core.OneToManyAttribute(
                Daughter, related_name='mother')

        m = Mother()
        d1 = Daughter()
        d2 = Daughter()
        self.assertEqual(m.daughters.add(d1), m.daughters)
        self.assertEqual(m.daughters.add(d2), m.daughters)
        self.assertEqual(m.daughters.remove(d1), m.daughters)
        self.assertEqual(m.daughters.extend([d1]), m.daughters)
        self.assertEqual(m.daughters.discard(d2), m.daughters)
        self.assertEqual(m.daughters.update([d2]), m.daughters)
        self.assertEqual(m.daughters.clear(), m.daughters)
        self.assertEqual(m.daughters.extend([d1, d2]), m.daughters)
        self.assertEqual(m.daughters.intersection_update([d1]), m.daughters)
        self.assertEqual(set(m.daughters), set([d1]))
        self.assertEqual(m.daughters.difference_update([d1]), m.daughters)
        self.assertEqual(set(m.daughters), set([]))
        self.assertEqual(m.daughters.extend([d1, d2]), m.daughters)
        self.assertEqual(
            m.daughters.symmetric_difference_update([d1]), m.daughters)
        self.assertEqual(set(m.daughters), set([d2]))

        m = Mother()
        d1 = Daughter()
        d2 = Daughter()
        m.daughters \
            .add(d1) \
            .add(d2) \
            .remove(d1) \
            .extend([d1]) \
            .discard(d2) \
            .update([d2]) \
            .clear() \
            .extend([d1, d2]) \
            .intersection_update([d1]) \
            .difference_update([d1]) \
            .extend([d1, d2]) \
            .symmetric_difference_update([d1])
        self.assertEqual(set(m.daughters), set([d2]))

    def test_chaining_many_to_many(self):
        class Mother(core.Model):
            id = core.SlugAttribute()

        class Daughter(core.Model):
            id = core.SlugAttribute()
            mothers = core.ManyToManyAttribute(
                Mother, related_name='daughters')

        m = Mother()
        d1 = Daughter()
        d2 = Daughter()
        self.assertEqual(m.daughters.add(d1), m.daughters)
        self.assertEqual(m.daughters.add(d2), m.daughters)
        self.assertEqual(m.daughters.remove(d1), m.daughters)
        self.assertEqual(m.daughters.extend([d1]), m.daughters)
        self.assertEqual(m.daughters.discard(d2), m.daughters)
        self.assertEqual(m.daughters.update([d2]), m.daughters)
        self.assertEqual(m.daughters.clear(), m.daughters)
        self.assertEqual(m.daughters.extend([d1, d2]), m.daughters)
        self.assertEqual(m.daughters.intersection_update([d1]), m.daughters)
        self.assertEqual(set(m.daughters), set([d1]))
        self.assertEqual(m.daughters.difference_update([d1]), m.daughters)
        self.assertEqual(set(m.daughters), set([]))
        self.assertEqual(m.daughters.extend([d1, d2]), m.daughters)
        self.assertEqual(
            m.daughters.symmetric_difference_update([d1]), m.daughters)
        self.assertEqual(set(m.daughters), set([d2]))

        m = Mother()
        d1 = Daughter()
        d2 = Daughter()
        m.daughters \
            .add(d1) \
            .add(d2) \
            .remove(d1) \
            .extend([d1]) \
            .discard(d2) \
            .update([d2]) \
            .clear() \
            .extend([d1, d2]) \
            .intersection_update([d1]) \
            .difference_update([d1]) \
            .extend([d1, d2]) \
            .symmetric_difference_update([d1])
        self.assertEqual(set(m.daughters), set([d2]))

        m1 = Mother()
        m2 = Mother()
        d = Daughter()
        self.assertEqual(d.mothers.add(m1), d.mothers)
        self.assertEqual(d.mothers.add(m2), d.mothers)
        self.assertEqual(d.mothers.remove(m1), d.mothers)
        self.assertEqual(d.mothers.extend([m1]), d.mothers)
        self.assertEqual(d.mothers.discard(m2), d.mothers)
        self.assertEqual(d.mothers.update([m2]), d.mothers)
        self.assertEqual(d.mothers.clear(), d.mothers)
        self.assertEqual(d.mothers.extend([m1, m2]), d.mothers)
        self.assertEqual(d.mothers.intersection_update([m1]), d.mothers)
        self.assertEqual(set(d.mothers), set([m1]))
        self.assertEqual(d.mothers.difference_update([m1]), d.mothers)
        self.assertEqual(set(d.mothers), set([]))
        self.assertEqual(d.mothers.extend([m1, m2]), d.mothers)
        self.assertEqual(
            d.mothers.symmetric_difference_update([m1]), d.mothers)
        self.assertEqual(set(d.mothers), set([m2]))

        m1 = Mother()
        m2 = Mother()
        d = Daughter()
        d.mothers \
            .add(m1) \
            .add(m2) \
            .remove(m1) \
            .extend([m1]) \
            .discard(m2) \
            .update([m2]) \
            .clear() \
            .extend([m1, m2]) \
            .intersection_update([m1]) \
            .difference_update([m1]) \
            .extend([m1, m2]) \
            .symmetric_difference_update([m1])
        self.assertEqual(set(d.mothers), set([m2]))

    def test_override_superclass_attributes(self):
        class TestSup(core.Model):
            value = core.IntegerAttribute(min=1, max=10)
        class TestSub(TestSup):
            value = core.IntegerAttribute(min=3, max=12)

        sup = TestSup(value=0)
        sub = TestSub(value=0)
        self.assertNotEqual(sup.validate(), None)
        self.assertNotEqual(sub.validate(), None)

        sup = TestSup(value=2)
        sub = TestSub(value=2)
        self.assertEqual(sup.validate(), None)
        self.assertNotEqual(sub.validate(), None)

        sup = TestSup(value=12)
        sub = TestSub(value=12)
        self.assertNotEqual(sup.validate(), None)
        self.assertEqual(sub.validate(), None)

        sup = TestSup(value=13)
        sub = TestSub(value=13)
        self.assertNotEqual(sup.validate(), None)
        self.assertNotEqual(sub.validate(), None)

    def test_modify_superclass_attributes(self):
        class TestSup(core.Model):
            value = core.IntegerAttribute(min=1, max=10)
        class TestSub(TestSup):
            pass

        self.assertNotEqual(TestSub.Meta.attributes[
                            'value'], TestSup.Meta.attributes['value'])
        TestSub.Meta.attributes['value'].min = 3
        TestSub.Meta.attributes['value'].max = 12

        sup = TestSup(value=0)
        sub = TestSub(value=0)
        self.assertNotEqual(sup.validate(), None)
        self.assertNotEqual(sub.validate(), None)

        sup = TestSup(value=2)
        sub = TestSub(value=2)
        self.assertEqual(sup.validate(), None)
        self.assertNotEqual(sub.validate(), None)

        sup = TestSup(value=12)
        sub = TestSub(value=12)
        self.assertNotEqual(sup.validate(), None)
        self.assertEqual(sub.validate(), None)

        sup = TestSup(value=13)
        sub = TestSub(value=13)
        self.assertNotEqual(sup.validate(), None)
        self.assertNotEqual(sub.validate(), None)


class TestErrors(unittest.TestCase):

    def test_error_related_attribute_with_same_name_as_primary_attribute(self):
        class Parent1(core.Model):
            id = core.StringAttribute(primary=True)
            children1 = core.StringAttribute()

        with self.assertRaisesRegexp(ValueError, 'cannot use the same related name as'):
            class Child1(core.Model):
                id = core.StringAttribute(primary=True)
                parent1 = core.ManyToOneAttribute(
                    Parent1, related_name='children1')

    def test_error_related_attribute_with_same_name_as_related_attribute(self):
        class Parent2(core.Model):
            id = core.StringAttribute(primary=True)

        class Child2a(core.Model):
            id = core.StringAttribute(primary=True)
            parent2 = core.ManyToOneAttribute(
                Parent2, related_name='children2')

        with self.assertRaisesRegexp(ValueError, 'cannot use the same related attribute name'):
            class Child2b(core.Model):
                id = core.StringAttribute(primary=True)
                parent2 = core.ManyToOneAttribute(
                    Parent2, related_name='children2')
