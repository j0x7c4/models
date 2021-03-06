# Copyright 2017 The TensorFlow Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
"""Example code for TensorFlow Wide & Deep Tutorial using tf.estimator API."""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import shutil

from absl import app as absl_app
from absl import flags
import tensorflow as tf  # pylint: disable=g-bad-import-order
from official.utils.flags import core as flags_core
from official.utils.logs import hooks_helper
from official.utils.misc import model_helpers

print(tf.__version__)

_CSV_COLUMNS = [
    'age', 'workclass', 'fnlwgt', 'education', 'education_num',
    'marital_status', 'occupation', 'relationship', 'race', 'gender',
    'capital_gain', 'capital_loss', 'hours_per_week', 'native_country',
    'income_bracket'
]

_CSV_COLUMN_DEFAULTS = [[0], [''], [0], [''], [0], [''], [''], [''], [''], [''],
                        [0], [0], [0], [''], ['']]

sparse_feature_define = {
    'education': [
        'Bachelors', 'HS-grad', '11th', 'Masters', '9th', 'Some-college',
        'Assoc-acdm', 'Assoc-voc', '7th-8th', 'Doctorate', 'Prof-school',
        '5th-6th', '10th', '1st-4th', 'Preschool', '12th'],
    "workclass": [
        'Self-emp-not-inc', 'Private', 'State-gov', 'Federal-gov',
        'Local-gov', '?', 'Self-emp-inc', 'Without-pay', 'Never-worked']
}

multi_hot_feature_define = {
    "workclass": {"th": 3}
}

tf_feature_shape = {'age': tf.TensorShape([]), 'workclass': tf.TensorShape([9]),
                    'fnlwgt': tf.TensorShape([]), 'education': tf.TensorShape([]),
                    'education_num': tf.TensorShape([]),
                    'marital_status': tf.TensorShape([]), 'occupation': tf.TensorShape([]),
                    'relationship': tf.TensorShape([]),
                    'race': tf.TensorShape([]), 'gender': tf.TensorShape([]),
                    'capital_gain': tf.TensorShape([]), 'capital_loss': tf.TensorShape([]),
                    'hours_per_week': tf.TensorShape([]),
                    'native_country': tf.TensorShape([])
                    }

tf_label_shape = tf.TensorShape([])

tf_feature_type = {'age': tf.int32, 'workclass': tf.string, 'fnlwgt': tf.int64, 'education': tf.string,
                   'education_num': tf.int32,
                   'marital_status': tf.string, 'occupation': tf.string, 'relationship': tf.string,
                   'race': tf.string, 'gender': tf.string,
                   'capital_gain': tf.int32, 'capital_loss': tf.int32, 'hours_per_week': tf.int32,
                   'native_country': tf.string
                   }

tf_label_type = tf.int32

_NUM_EXAMPLES = {
    'train': 32561,
    'validation': 16281,
}

LOSS_PREFIX = {'wide': 'linear/', 'deep': 'dnn/'}


def define_wide_deep_flags():
    """Add supervised learning flags, as well as wide-deep model type."""
    flags_core.define_base()

    flags.adopt_module_key_flags(flags_core)

    flags.DEFINE_enum(
        name="model_type", short_name="mt", default="wide_deep",
        enum_values=['wide', 'deep', 'wide_deep'],
        help="Select model topology.")

    flags_core.set_defaults(data_dir='/tmp/census_data',
                            model_dir='/tmp/census_model',
                            train_epochs=40,
                            epochs_between_evals=2,
                            batch_size=40)


def build_model_columns():
    """Builds a set of wide and deep feature columns."""
    # Continuous columns
    age = tf.feature_column.numeric_column('age')
    education_num = tf.feature_column.numeric_column('education_num')
    capital_gain = tf.feature_column.numeric_column('capital_gain')
    capital_loss = tf.feature_column.numeric_column('capital_loss')
    hours_per_week = tf.feature_column.numeric_column('hours_per_week')

    education = tf.feature_column.categorical_column_with_vocabulary_list(
        'education', [
            'Bachelors', 'HS-grad', '11th', 'Masters', '9th', 'Some-college',
            'Assoc-acdm', 'Assoc-voc', '7th-8th', 'Doctorate', 'Prof-school',
            '5th-6th', '10th', '1st-4th', 'Preschool', '12th'])

    marital_status = tf.feature_column.categorical_column_with_vocabulary_list(
        'marital_status', [
            'Married-civ-spouse', 'Divorced', 'Married-spouse-absent',
            'Never-married', 'Separated', 'Married-AF-spouse', 'Widowed'])

    relationship = tf.feature_column.categorical_column_with_vocabulary_list(
        'relationship', [
            'Husband', 'Not-in-family', 'Wife', 'Own-child', 'Unmarried',
            'Other-relative'])

    workclass = tf.feature_column.categorical_column_with_vocabulary_list(
        'workclass', [
            'Self-emp-not-inc', 'Private', 'State-gov', 'Federal-gov',
            'Local-gov', '?', 'Self-emp-inc', 'Without-pay', 'Never-worked'])

    # To show an example of hashing:
    occupation = tf.feature_column.categorical_column_with_hash_bucket(
        'occupation', hash_bucket_size=1000)

    # Transformations.
    age_buckets = tf.feature_column.bucketized_column(
        age, boundaries=[18, 25, 30, 35, 40, 45, 50, 55, 60, 65])

    # Wide columns and deep columns.
    base_columns = [
        education, marital_status, relationship, workclass, occupation,
        age_buckets,
    ]

    crossed_columns = [
        tf.feature_column.crossed_column(
            ['education', 'occupation'], hash_bucket_size=1000),
        tf.feature_column.crossed_column(
            [age_buckets, 'education', 'occupation'], hash_bucket_size=1000),
    ]

    wide_columns = base_columns + crossed_columns

    deep_columns = [
        age,
        education_num,
        capital_gain,
        capital_loss,
        hours_per_week,
        tf.feature_column.indicator_column(workclass),
        tf.feature_column.indicator_column(education),
        tf.feature_column.indicator_column(marital_status),
        tf.feature_column.indicator_column(relationship),
        # To show an example of embedding
        tf.feature_column.embedding_column(occupation, dimension=8),
    ]

    return wide_columns, deep_columns


def build_estimator(model_dir, model_type):
    """Build an estimator appropriate for the given model type."""
    wide_columns, deep_columns = build_model_columns()
    hidden_units = [100, 75, 50, 25]

    # Create a tf.estimator.RunConfig to ensure the model is run on CPU, which
    # trains faster than GPU for this model.
    run_config = tf.estimator.RunConfig().replace(
        session_config=tf.ConfigProto(device_count={'GPU': 0}))

    if model_type == 'wide':
        return tf.estimator.LinearClassifier(
            model_dir=model_dir,
            feature_columns=wide_columns,
            config=run_config)
    elif model_type == 'deep':
        return tf.estimator.DNNClassifier(
            model_dir=model_dir,
            feature_columns=deep_columns,
            hidden_units=hidden_units,
            config=run_config)
    else:
        return tf.estimator.DNNLinearCombinedClassifier(
            model_dir=model_dir,
            linear_feature_columns=wide_columns,
            dnn_feature_columns=deep_columns,
            dnn_hidden_units=hidden_units,
            config=run_config)

def input_fn(data_file, num_epochs=1, shuffle=True, batch_size=5):
    """Generate an input function for the Estimator."""
    assert tf.gfile.Exists(data_file), (
        '%s not found. Please make sure you have run data_download.py and '
        'set the --data_dir argument to the correct path.' % data_file)

    def padding(a, size, default=None):
        t = list(a)
        assert len(t) < size
        return tuple(t + [default for i in range(size - len(t))])

    def attempt_dict(arr, th=0):
        ans = []
        for t in arr:
            if len(t.split(':')) == 2:
                tmp = t.split(':')
                k, v = tmp[0], float(tmp[1])
                if v > th:
                    ans.append(k)
            else:
                ans.append(t)
        return ans

    def data_generator():
        with open(data_file) as f:
            for line in f:
                buf = line.strip().split(',')
                for i, field in enumerate(_CSV_COLUMN_DEFAULTS):
                    if type(_CSV_COLUMN_DEFAULTS[i][0]) == int:
                        buf[i] = int(buf[i])
                    elif multi_hot_feature_define.get(_CSV_COLUMNS[i]):
                        buf[i] = attempt_dict(buf[i][1:-1].split('|'), multi_hot_feature_define.get(_CSV_COLUMNS[i])["th"])
                        buf[i] = padding(buf[i], len(sparse_feature_define[_CSV_COLUMNS[i]]), default="")
                features = dict(zip(_CSV_COLUMNS, buf))
                label = features.pop("income_bracket")
                print(features)
                yield features, 1 if label == ">50K" else 0

    # from_generator is more flexible
    dataset = tf.data.Dataset.from_generator(data_generator, (tf_feature_type, tf_label_type), (tf_feature_shape, tf_label_shape))
    #
    if shuffle:
        dataset = dataset.shuffle(buffer_size=_NUM_EXAMPLES['train'])

    # We call repeat after shuffling, rather than before, to prevent separate
    # epochs from blending together.
    dataset = dataset.repeat(num_epochs)
    dataset = dataset.batch(batch_size)
    iter = dataset.make_one_shot_iterator()
    return iter.get_next()


def export_model(model, model_type, export_dir):
    """Export to SavedModel format.

    Args:
      model: Estimator object
      model_type: string indicating model type. "wide", "deep" or "wide_deep"
      export_dir: directory to export the model.
    """
    wide_columns, deep_columns = build_model_columns()
    if model_type == 'wide':
        columns = wide_columns
    elif model_type == 'deep':
        columns = deep_columns
    else:
        columns = wide_columns + deep_columns
    feature_spec = tf.feature_column.make_parse_example_spec(columns)
    example_input_fn = (
        tf.estimator.export.build_parsing_serving_input_receiver_fn(feature_spec))
    model.export_savedmodel(export_dir, example_input_fn)


def run_wide_deep(flags_obj):
    """Run Wide-Deep training and eval loop.

    Args:
      flags_obj: An object containing parsed flag values.
    """

    # Clean up the model directory if present
    shutil.rmtree(flags_obj.model_dir, ignore_errors=True)
    model = build_estimator(flags_obj.model_dir, flags_obj.model_type)

    train_file = os.path.join(flags_obj.data_dir, 'adult.data')
    test_file = os.path.join(flags_obj.data_dir, 'adult.test')

    # Train and evaluate the model every `flags.epochs_between_evals` epochs.
    def train_input_fn():
        return input_fn(
            train_file, flags_obj.epochs_between_evals, True, flags_obj.batch_size)

    def eval_input_fn():
        return input_fn(test_file, 1, False, flags_obj.batch_size)

    loss_prefix = LOSS_PREFIX.get(flags_obj.model_type, '')
    train_hooks = hooks_helper.get_train_hooks(
        flags_obj.hooks, batch_size=flags_obj.batch_size,
        tensors_to_log={'average_loss': loss_prefix + 'head/truediv',
                        'loss': loss_prefix + 'head/weighted_loss/Sum'})

    # Train and evaluate the model every `flags.epochs_between_evals` epochs.
    for n in range(flags_obj.train_epochs // flags_obj.epochs_between_evals):
        model.train(input_fn=train_input_fn, hooks=train_hooks)
        results = model.evaluate(input_fn=eval_input_fn)

        # Display evaluation metrics
        print('Results at epoch', (n + 1) * flags_obj.epochs_between_evals)
        print('-' * 60)

        for key in sorted(results):
            print('%s: %s' % (key, results[key]))

        if model_helpers.past_stop_threshold(
                flags_obj.stop_threshold, results['accuracy']):
            break

    # Export the model
    if flags_obj.export_dir is not None:
        export_model(model, flags_obj.model_type, flags_obj.export_dir)


def main(_):
    run_wide_deep(flags.FLAGS)


if __name__ == '__main__':
    tf.logging.set_verbosity(tf.logging.INFO)
    define_wide_deep_flags()
    absl_app.run(main)
