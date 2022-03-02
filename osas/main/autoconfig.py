#
# Authors: Security Intelligence Team within the Security Coordination Center
#
# Copyright (c) 2018 Adobe Systems Incorporated. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import optparse
import sys
import inspect

sys.path.append('')
from osas.data.datasources import CSVDataSource
from osas.core import label_generators


def _get_type(val):
    try:
        x = int(val)
        return 'int'
    except:
        try:
            x = float(val)
            return 'float'
        except:
            if val is None:
                return 'none'
            else:
                return 'str'


def _detect_field_type(datasource, count_column=None):
    item = datasource[0]
    field_type = {key: 'int' for key in item}
    sys.stdout.write('\n')
    sys.stdout.flush()

    if count_column is None:
        count = len(datasource)
    else:
        count = 0

    for item in datasource:
        if count_column is not None:
            count += item[count_column]
        for key in item:
            t = _get_type(item[key])
            if t == 'float':
                if field_type[key] == 'int':
                    field_type[key] = t
            elif t == 'str':
                field_type[key] = t

    field2val = {}
    for item in datasource:
        for key in field_type:
            if field_type[key] == 'str' or field_type[key] == 'int' or field_type[key] == 'float':
                value = item[key]
                if key not in field2val:
                    field2val[key] = {}
                if (len(field2val[key]) - 1) / count < 0.1:
                    if value not in field2val[key]:
                        field2val[key][value] = '1'
    for key in field2val:
        if len(field2val[key]) / count < 0.1:
            field_type[key] = 'multinomial'
        elif field_type[key] == 'str':
            field_type[key] = 'text'

    return field_type


def _get_generators(datasource: CSVDataSource, field_types: dict):
    generator_list = []
    for key in field_types:
        if field_types[key] == 'int' or field_types[key] == 'float':
            generator_list.append(['NumericField', [key]])
        if field_types[key] == 'multinomial':
            generator_list.append(['MultinomialField', [key]])
        if field_types[key] == 'text':
            generator_list.append(['TextField', [key]])
    assigned = {}
    for key1 in field_types:
        for key2 in field_types:
            if field_types[key1] == 'multinomial' and field_types[key2] == 'multinomial' and \
                    (key2, key1) not in assigned and key1 != key2:
                generator_list.append(['MultinomialFieldCombiner', [key1, key2]])
                assigned[(key1, key2)] = '1'

    generator_list = list(sorted(generator_list, key=lambda x: x[0]))

    return generator_list


HEADER = """; OSAS autogenerated configuration file
;
; Below we provide a list of standard label generator templates - feel free to copy-paste and edit them
; in order to cope with your own dataset
;

; [LG_MULTINOMIAL]
; generator_type = MultinomialField
; field_name = <FIELD_NAME>
; absolute_threshold = 10
; relative_threshold = 0.1

; [LG_TEXT]
; generator_type = TextField
; field_name = <FIELD_NAME>
; lm_mode = char
; ngram_range = (3, 5)

; [LG_NUMERIC]
; generator_type = NumericField
; field_name = <FIELD_NAME>

; [LG_MUTLINOMIAL_COMBINER]
; generator_type = MultinomialFieldCombiner
; field_names = ['<FIELD_1>', '<FIELD_2>', ...]
; absolute_threshold = 10
; relative_threshold = 0.1

; [LG_KEYWORD]
; generator_type = KeywordBased
; field_name = <FIELD_NAME>
; keyword_list = ['<KEYWORD_1>', '<KEYWORD_2>', '<KEYWORD_3>', ...]

; [LG_REGEX]
; generator_type = KnowledgeBased
; field_name = <FIELD_NAME>
; rules_and_labels_tuple_list = [('<REGEX_1>','<LABEL_1>'), ('<REGEX_2>','<LABEL_2>'), ...]"""


def _write_conf(generators, filename):
    f = open(filename, 'w')
    f.write(HEADER)
    f.write('\n\n')
    count = 0
    for generator in generators:
        count += 1
        f.write('[LG_{0}]\n'.format(count))
        f.write('generator_type = {0}\n'.format(generator[0]))
        dyn_class = getattr(sys.modules[label_generators.__name__], generator[0])

        signature = inspect.signature(dyn_class.__init__)
        for param in signature.parameters.items():
            param_name = param[1].name
            param_value = param[1].default
            if param_name == 'self':
                continue
            if param_name == 'field_name' or param_name == 'field_names':
                if len(generator[1]) == 1:
                    param_value = generator[1][0]
                else:
                    param_value = generator[1]
            f.write('{0} = {1}\n'.format(param_name, param_value))
        f.write('\n')
    f.write('[AnomalyScoring]\nscoring_algorithm = StatisticalNGramAnomaly\n')
    f.close()


def process(params):
    datasource = CSVDataSource(params.input_file)
    sys.stdout.write('Preprocessing')
    if params.count_column:
        cc = params.count_column
    else:
        cc = None
    field_type = _detect_field_type(datasource, count_column=cc)
    sys.stdout.write('\t::Detected field types:\n')
    for key in field_type:
        sys.stdout.write('\t\t"{0}": {1}\n'.format(key, field_type[key]))

    generators = _get_generators(datasource, field_type)
    sys.stdout.write('\t::Suggested generators:\n')
    for item in generators:
        sys.stdout.write('\t\t{0}: {1}\n'.format(item[0], item[1]))

    _write_conf(generators, params.output_file)


if __name__ == '__main__':
    parser = optparse.OptionParser()
    parser.add_option('--input-file', action='store', dest='input_file', help='location of the input file')
    parser.add_option('--output-file', action='store', dest='output_file', help='location of the output file')
    parser.add_option('--count-column', action='store', dest='count_column',
                      help='if this value is set, OSAS will consider the data clustered and this column will indicate'
                           'the number of occurrences of the event. Otherwise, this number is considered equal to 1')
    (params, _) = parser.parse_args(sys.argv)

    if params.input_file and params.output_file:
        process(params)
    else:
        parser.print_help()
