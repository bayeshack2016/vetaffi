#!/usr/bin/env python3
import argparse
import json
import logging

from xml.etree import ElementTree
from transitions import logger

import transitions

import munging
import models
import util

logger.setLevel(logging.INFO)


def get_args():
    parser = argparse.ArgumentParser('Parse all tables that show percent disability rating for particular conditions')
    parser.add_argument('--input-files', dest='input_files', nargs='+')
    return parser.parse_args()


def print_subject(element: ElementTree.Element):
    subject_element = element.find('.//SUBJECT')
    if subject_element is None:
        print("No SUBJECT.")
    else:
        util.pretty_print_element(subject_element)


def is_ratings_subject(element: ElementTree.Element):
    subject_element = element.find('.//SUBJECT')
    if subject_element is None:
        return False
    else:
        return ('ratings' in subject_element.text.lower() and
                not subject_element.text.startswith('Combined'))


def parse_tables(filename: str):
    root = ElementTree.parse(munging.repair_xml(filename))
    for element in root.findall(""".//GPOTABLE/.."""):
        if is_ratings_subject(element):
            yield element


def parse_files(filenames: list):
    for filename in filenames:
        for rating_table in parse_tables(filename):
            yield rating_table


def get_table_key_name(table_element: ElementTree.Element):
    return table_element.find('.//SUBJECT').text.lower().replace('.', '').replace(',', '').replace(' ', '_').replace(
        '—', '_')


def save_xml(table_element: ElementTree.Element):
    with open(get_table_key_name(table_element) + '.xml', 'w') as of:
        of.write(util.pformat_element(table_element))


def is_category_row(row_element: ElementTree.Element):
    entries = [entry for entry in row_element.findall('ENT') if munging.extract_entry_text(entry).strip()]
    row_length = len(entries)
    return row_length == 1


def get_description(row_element: ElementTree.Element):
    return row_element.find('ENT').text


def is_rating_row(row_element: ElementTree.Element):
    entries = [entry for entry in row_element.findall('ENT') if munging.extract_entry_text(entry).strip()]
    row_length = len(entries)
    return row_length >= 2 and all([munging.is_integer_0_100(entry.text) for entry in entries[1:]])


def get_rating(row_element: ElementTree.Element):
    return row_element.findall('ENT')[0].text, int(row_element.findall('ENT')[1].text)


def is_diagnostic_code_row(row_element: ElementTree.Element):
    entries = row_element.findall('ENT')
    row_length = len(entries)
    return row_length == 1 and munging.describes_diagnostic_code(entries[0].text)


def is_reference_row(row_element: ElementTree.Element):
    """
    Some rows reference a different rating table, saying something like:
    
    "Or evaluate as DC 7800, scars, disfiguring, head, face, or neck."
    
    This will return true if this is the case.
    
    :param row_element: The row ElementTree object
    :return: 
    """
    entries = row_element.findall('ENT')
    row_length = len(entries)
    return row_length == 1 and 'or evaluate as' in entries[0].text.lower()


def is_note_row(row_element: ElementTree.Element):
    """
    Some rows are just an advisory note, for example:
    
    <ROW>
        <ENT I="13">
            <E T="02">Note 1:</E>
            Natural menopause, primary amenorrhea, and pregnancy and childbirth are not disabilities for rating purposes. Chronic residuals of medical or surgical complications of pregnancy may be disabilities for rating purposes.
        </ENT>
    </ROW>
                
    This will return true if this is the case.
    """
    entries = row_element.findall('ENT')
    row_length = len(entries)
    if row_length == 1:
        return entries[0].find('E') is not None and 'note' in entries[0].find('E').text.lower()
    else:
        return False


def is_see_other_row(row_element: ElementTree.Element):
    """
    Some rows refer to another section of the CFR.
    
    For example:
    
    <ROW>
        <ENT I="12">Inactive: See §§ 4.88b and 4.89.</ENT>
    </ROW>

    This will return true if this is the case.
    """
    entries = row_element.findall('ENT')
    row_length = len(entries)

    for entry in entries:
        if '§' in munging.extract_entry_text(entry) and 'see' in munging.extract_entry_text(entry).lower():
            return True
    return False


def is_general_rating_note_row(row_element: ElementTree.Element):
    """
    This type of row explains that the ratings to follow are applicable to
    the above listed diagnostic codes.
    
    For example:
    
    <ROW>
        <ENT I="11">General Rating Formula for Disease, Injury, or Adhesions of Female Reproductive Organs (diagnostic codes 7610 through 7615):</ENT>
    </ROW>
    """
    entries = row_element.findall('ENT')
    row_length = len(entries)
    return row_length == 1 and munging.extract_entry_text(entries[0]).lower().strip().startswith('general rating formula')


class RatingTableStateMachine:
    """
    Defines a state machine for parsing the ratings table XML
    """
    states = ['category', 'diagnostic_code', 'rating', 'reference', 'note', 'see_other_note']

    transitions = [
        {'trigger': 'process_category', 'source': 'category', 'dest': 'category', 'before': 'add_child_category'},
        {'trigger': 'process_category', 'source': 'reference', 'dest': 'category', 'before': 'add_sibling_category'},
        {'trigger': 'process_category', 'source': 'rating', 'dest': 'category', 'before': 'add_sibling_category'},
        {'trigger': 'process_category', 'source': 'note', 'dest': 'category', 'before': 'add_sibling_category'},
        {'trigger': 'process_category', 'source': 'diagnostic_code', 'dest': 'diagnostic_code', 'before': 'add_diagnostic_code_info'},
        {'trigger': 'process_reference', 'source': 'rating', 'dest': 'reference', 'before': 'add_reference'},
        {'trigger': 'process_reference', 'source': 'category', 'dest': 'reference', 'before': 'add_reference'},
        {'trigger': 'process_rating', 'source': 'rating', 'dest': 'rating', 'before': 'add_rating'},
        {'trigger': 'process_rating', 'source': 'diagnostic_code', 'dest': 'rating', 'before': 'add_rating'},
        {'trigger': 'process_rating', 'source': 'note', 'dest': 'rating', 'before': 'add_rating'},
        {'trigger': 'process_diagnostic_code', 'source': 'note', 'dest': 'diagnostic_code', 'before': 'add_first_diagnostic_code'},
        {'trigger': 'process_diagnostic_code', 'source': 'see_other_note', 'dest': 'diagnostic_code', 'before': 'add_first_diagnostic_code'},
        {'trigger': 'process_diagnostic_code', 'source': 'category', 'dest': 'diagnostic_code', 'before': 'add_first_diagnostic_code'},
        {'trigger': 'process_diagnostic_code', 'source': 'diagnostic_code', 'dest': 'diagnostic_code', 'before': 'add_diagnostic_code'},
        {'trigger': 'process_note', 'source': 'category', 'dest': 'note', 'before': 'add_note'},
        {'trigger': 'process_note', 'source': 'rating', 'dest': 'note', 'before': 'add_note'},
        {'trigger': 'process_note', 'source': 'note', 'dest': 'note', 'before': 'add_note'},
        {'trigger': 'process_see_other_note', 'source': 'rating', 'dest': 'see_other_note', 'before': 'add_see_other_note'},
    ]

    def __init__(self, name: str, initial: models.RatingCategory):
        self.name = name
        self.current_category = initial
        self.last_row = None
        self.current_row = None
        self.current_diagnostic_code_set = None

        # Initialize the state machine
        self.machine = transitions.Machine(model=self,
                                           states=RatingTableStateMachine.states,
                                           initial='category',
                                           transitions=self.transitions)

    def add_child_category(self, element):
        desc = get_description(element)
        subcategory = models.RatingCategory(desc, parent=self.current_category)
        self.current_category.add_subcategory(subcategory)
        self.current_category = subcategory

    def add_sibling_category(self, element):
        desc = get_description(element)
        category = models.RatingCategory(desc, parent=self.current_category.parent)
        self.current_category.parent.add_subcategory(category)
        self.current_category = category

    def add_reference(self, element):
        self.current_category.add_reference(models.RatingReference.from_element(element))

    def add_first_diagnostic_code(self, element):
        self.current_diagnostic_code_set = models.DiagnosticCodeSet()
        self.current_category.add_diagnostic_code_set(self.current_diagnostic_code_set)
        self.add_diagnostic_code(element)

    def add_diagnostic_code(self, element):
        self.current_diagnostic_code_set.add_diagnostic_code(models.DiagnosticCode.from_element(element))

    def add_rating(self, element):
        self.current_diagnostic_code_set.add_rating(models.Rating.from_element(element))

    def add_note(self, element):
        self.current_category.add_note(models.RatingNote.from_element(element))

    def add_see_other_note(self, element):
        self.current_category.add_see_other_note(models.SeeOtherRatingNote.from_element(element))

    def add_diagnostic_code_info(self, element):
        self.current_diagnostic_code_set.add_note(
            models.RatingNote.from_element(element))

    def process_row(self, row: ElementTree.Element):
        self.last_row = self.current_row
        self.current_row = row

        try:
            self.process_row_unsafe(row)
        except Exception as e:
            util.pretty_print_element(self.last_row)
            util.pretty_print_element(self.current_row)
            raise e

    def process_row_unsafe(self, row: ElementTree.Element):
        if is_diagnostic_code_row(row):
            self.process_diagnostic_code(row)
        elif is_reference_row(row):
            self.process_reference(row)
        elif is_rating_row(row):
            self.process_rating(row)
        elif is_note_row(row):
            self.process_note(row)
        elif is_general_rating_note_row(row):
            pass
        elif is_see_other_row(row):
            self.process_see_other_note(row)
        elif is_category_row(row):
            self.process_category(row)
        else:
            raise ValueError('Unexpected row: {}'.format(util.pformat_element(row)))


def convert_table_to_json(table_element: ElementTree.Element):
    subject = table_element.find('.//SUBJECT').text

    gpo_table = table_element.find('GPOTABLE')

    rows = gpo_table.findall('ROW')

    root = models.RatingCategory(subject)
    root.parent = root
    machine = RatingTableStateMachine(subject, root)

    for row in rows:
        machine.process_row(row)

    return json.dumps(root, indent=True, cls=models.RatingTableEncoder)


def save_json(table_element: ElementTree.Element):
    with open(get_table_key_name(table_element) + '.json', 'w') as of:
        of.write(convert_table_to_json(table_element))


def main():
    args = get_args()
    for table_element in parse_files(args.input_files):
        save_xml(table_element)
        save_json(table_element)


if __name__ == '__main__':
    main()
