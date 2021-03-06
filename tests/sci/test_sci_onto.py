""" Test ontology attributes

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2019-01-14
:Copyright: 2019, Karr Lab
:License: MIT
"""

from obj_tables import core
import copy
import mock
import obj_tables.sci.onto
import pronto
import unittest


class OntoTermAttributeTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ontology = pronto.Ontology('tests/fixtures/SBO.owl')
        cls.term = cls.ontology['SBO_0000000']

    def test_init(self):
        attr = obj_tables.sci.onto.OntoTermAttribute(self.ontology)
        with self.assertRaisesRegex(ValueError, 'be an instance of `pronto.Ontology`'):
            attr = obj_tables.sci.onto.OntoTermAttribute('NOT_AN_ONTOLOGY')

        attr = obj_tables.sci.onto.OntoTermAttribute(self.ontology, terms=[self.ontology['SBO_0000001']])
        attr = obj_tables.sci.onto.OntoTermAttribute(self.ontology, terms=self.ontology['SBO_0000001'].subclasses())
        attr = obj_tables.sci.onto.OntoTermAttribute(
            self.ontology, terms=[self.ontology['SBO_0000001']] + list(self.ontology['SBO_0000001'].subclasses()))
        with self.assertRaisesRegex(ValueError, 'must be in `ontology`'):
            attr = obj_tables.sci.onto.OntoTermAttribute(self.ontology, terms=['SBO_0000001'])

        attr = obj_tables.sci.onto.OntoTermAttribute(self.ontology, default=self.term)
        attr = obj_tables.sci.onto.OntoTermAttribute(self.ontology, default=self.term, terms=[self.ontology['SBO_0000000']])
        with self.assertRaisesRegex(ValueError, 'must be `None` or in `terms`'):
            attr = obj_tables.sci.onto.OntoTermAttribute(self.ontology, default='NOT_A_TERM')
        with self.assertRaisesRegex(ValueError, 'must be `None` or in `terms`'):
            attr = obj_tables.sci.onto.OntoTermAttribute(self.ontology, default=self.term, terms=[self.ontology['SBO_0000001']])

        attr = obj_tables.sci.onto.OntoTermAttribute(self.ontology, default_cleaned_value=self.term)
        attr = obj_tables.sci.onto.OntoTermAttribute(self.ontology, default_cleaned_value=self.term, terms=[self.ontology['SBO_0000000']])
        with self.assertRaisesRegex(ValueError, 'must be `None` or in `terms`'):
            attr = obj_tables.sci.onto.OntoTermAttribute(self.ontology, default_cleaned_value='NOT_A_TERM')
        with self.assertRaisesRegex(ValueError, 'must be `None` or in `terms`'):
            attr = obj_tables.sci.onto.OntoTermAttribute(
                self.ontology, default_cleaned_value=self.term, terms=[self.ontology['SBO_0000001']])

    def test_get_default(self):
        attr = obj_tables.sci.onto.OntoTermAttribute(self.ontology, default=self.term)
        self.assertEqual(attr.get_default(), self.term)

    def test_get_default_cleaned_value(self):
        attr = obj_tables.sci.onto.OntoTermAttribute(self.ontology, default_cleaned_value=self.term)
        self.assertEqual(attr.get_default_cleaned_value(), self.term)

    def test_value_equal(self):
        attr = obj_tables.sci.onto.OntoTermAttribute(self.ontology)

        self.assertTrue(attr.value_equal(self.ontology['SBO_0000000'], self.ontology['SBO_0000000']))
        self.assertTrue(attr.value_equal(None, None))
        self.assertTrue(attr.value_equal('', ''))

        self.assertFalse(attr.value_equal(self.ontology['SBO_0000000'], None))
        self.assertFalse(attr.value_equal(self.ontology['SBO_0000000'], ''))
        self.assertFalse(attr.value_equal(None, self.ontology['SBO_0000000']))
        self.assertFalse(attr.value_equal('', self.ontology['SBO_0000000']))

    def test_clean(self):
        attr = obj_tables.sci.onto.OntoTermAttribute(self.ontology)
        self.assertEqual(attr.clean('SBO_0000000 ! systems biology representation'), (self.term, None))

        attr = obj_tables.sci.onto.OntoTermAttribute(self.ontology, namespace='SBO', namespace_sep='_')
        self.assertEqual(attr.clean('0000000 ! systems biology representation'), (self.term, None))

        attr = obj_tables.sci.onto.OntoTermAttribute(self.ontology, namespace='SBO', namespace_sep='_')
        self.assertNotEqual(attr.clean('SBO_0000000 ! systems biology representation'), (self.term, None))

        attr = obj_tables.sci.onto.OntoTermAttribute(self.ontology)
        self.assertEqual(attr.clean(None), (None, None))

        attr = obj_tables.sci.onto.OntoTermAttribute(self.ontology)
        self.assertEqual(attr.clean(''), (None, None))

        attr = obj_tables.sci.onto.OntoTermAttribute(self.ontology)
        self.assertEqual(attr.clean(self.term)[1], None)

        attr = obj_tables.sci.onto.OntoTermAttribute(self.ontology, terms=[self.term])
        self.assertEqual(attr.clean(self.term)[1], None)

        attr = obj_tables.sci.onto.OntoTermAttribute(self.ontology, terms=[])
        self.assertNotEqual(attr.clean(self.term)[1], None)

        attr = obj_tables.sci.onto.OntoTermAttribute(self.ontology, default_cleaned_value=self.term)
        self.assertEqual(attr.clean(None)[0].id, self.term.id)

        attr = obj_tables.sci.onto.OntoTermAttribute(self.ontology)
        self.assertNotEqual(attr.clean('NOT_A_TERM ! NOT_A_TERM')[1], None)

        attr = obj_tables.sci.onto.OntoTermAttribute(self.ontology)
        onto2 = pronto.Ontology()
        term2 = onto2.create_term('NOT_A_TERM')
        self.assertNotEqual(attr.clean(term2)[1], None)

    def test_validate(self):
        attr = obj_tables.sci.onto.OntoTermAttribute(self.ontology)
        self.assertEqual(attr.validate(None, self.term), None)
        self.assertEqual(attr.validate(None, None), None)
        self.assertNotEqual(attr.validate(None, 'SBO_0000000'), None)

        attr = obj_tables.sci.onto.OntoTermAttribute(self.ontology, none=False)
        self.assertNotEqual(attr.validate(None, None), None)

        attr = obj_tables.sci.onto.OntoTermAttribute(self.ontology, terms=[self.term])
        self.assertEqual(attr.validate(None, self.term), None)

        attr = obj_tables.sci.onto.OntoTermAttribute(self.ontology, terms=[])
        self.assertNotEqual(attr.validate(None, self.term), None)

    def test_copy_value(self):
        attr = obj_tables.sci.onto.OntoTermAttribute(self.ontology)
        self.assertEqual(attr.copy_value(self.term, {}), self.term)
        self.assertEqual(attr.copy_value(self.term, {}).id, self.term.id)

    def test_serialize(self):
        attr = obj_tables.sci.onto.OntoTermAttribute(self.ontology)
        self.assertEqual(attr.serialize(self.term), 'SBO_0000000')
        self.assertEqual(attr.serialize(None), '')
        self.assertEqual(attr.serialize(''), '')
        self.assertEqual(attr.serialize(mock.Mock(id='0000000')), '0000000')

        attr = obj_tables.sci.onto.OntoTermAttribute(self.ontology, namespace='SBO', namespace_sep='_')
        self.assertEqual(attr.serialize(self.term), '0000000')
        self.assertEqual(attr.serialize(None), '')
        self.assertEqual(attr.serialize(''), '')
        with self.assertRaisesRegex(ValueError, 'must begin with namespace'):
            attr.serialize(mock.Mock(id='0000000'))

    def test_deserialize(self):
        attr = obj_tables.sci.onto.OntoTermAttribute(self.ontology)
        self.assertEqual(attr.deserialize('SBO_0000000 ! systems biology representation')[0].id, 'SBO_0000000')
        self.assertEqual(attr.deserialize(None), (None, None))
        self.assertEqual(attr.deserialize(''), (None, None))

    def test_to_builtin(self):
        attr = obj_tables.sci.onto.OntoTermAttribute(self.ontology)
        self.assertEqual(attr.to_builtin(self.term), 'SBO_0000000')
        self.assertEqual(attr.to_builtin(None), None)
        self.assertEqual(attr.to_builtin(''), None)

    def test_from_builtin(self):
        attr = obj_tables.sci.onto.OntoTermAttribute(self.ontology)
        self.assertEqual(attr.from_builtin('SBO_0000000').id, 'SBO_0000000')
        self.assertEqual(attr.from_builtin(None), None)
        self.assertEqual(attr.from_builtin(''), None)

    def test_merge(self):
        class Model(core.Model):
            attr = obj_tables.sci.onto.OntoTermAttribute(self.ontology)

        model_1 = Model(attr=self.ontology['SBO_0000000'])
        model_2 = Model(attr=copy.copy(model_1.attr))

        try:
            Model.attr.merge(model_1, model_2, {}, {})
        except ValueError:
            self.fail("Shouldn't raise 'ValueError: Model.attr must be equal'; check version and fork of pronto")
