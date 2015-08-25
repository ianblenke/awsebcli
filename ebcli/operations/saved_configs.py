# Copyright 2014 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You
# may not use this file except in compliance with the License. A copy of
# the License is located at
#
# http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
# ANY KIND, either express or implied. See the License for the specific
# language governing permissions and limitations under the License.

import os

from ..lib import elasticbeanstalk, s3, utils
from ..resources.strings import strings, responses
from ..core import io, fileoperations
from ..objects.exceptions import NotFoundError
from ..lib.aws import InvalidParameterValueError
from . import commonops

SAVED_CONFIG_FOLDER_NAME = 'saved_configs' + os.path.sep


def _get_s3_keyname_for_template(app_name, cfg_name):
    return 'resources/templates/' + app_name + '/' + cfg_name


def create_config(app_name, env_name, cfg_name):
    description = strings['template.description']
    result = elasticbeanstalk.create_configuration_template(
        app_name, env_name, cfg_name, description
    )

    download_config_from_s3(app_name, cfg_name)


def update_environment_with_config_file(env_name, cfg_name,
                                        nohang, timeout=None):

    commonops.update_environment(env_name, None, nohang,
                                  template=cfg_name, timeout=timeout)


def update_environment_with_config_data(env_name, data,
                                        nohang, timeout=None):

    commonops.update_environment(env_name, None, nohang,
                                  timeout=timeout, template_body=data)


def download_config_from_s3(app_name, cfg_name):
    bucket = elasticbeanstalk.get_storage_location()
    body = s3.get_object(bucket,
                         _get_s3_keyname_for_template(app_name, cfg_name))

    location = write_to_local_config(cfg_name, body)
    fileoperations.set_user_only_permissions(location)
    io.echo()
    io.echo('Configuration saved at: ' + location)


def delete_config(app_name, cfg_name):
    elasticbeanstalk.delete_configuration_template(app_name, cfg_name)
    location = resolve_config_location(cfg_name)
    if location is not None:
        fileoperations.delete_file(location)


def update_config(app_name, cfg_name):
    config_location = resolve_config_location(cfg_name)
    if config_location is None:
        raise NotFoundError('No local version of ' + cfg_name + ' found.')

    if cfg_name.endswith('.cfg.yml'):
        cfg_name = cfg_name.rstrip('.cfg.yml')

    upload_config_file(app_name, cfg_name, config_location)


def upload_config_file(app_name, cfg_name, file_location):
    """
    Does the actual uploading to s3.
    :param app_name:  name of application. Needed for resolving bucket
    :param cfg_name:  Name of configuration to update
    :param file_location: str: full path to file.
    :param region: region of application. Needed for resolving bucket
    """
    bucket = elasticbeanstalk.get_storage_location()
    key = _get_s3_keyname_for_template(app_name, cfg_name)
    s3.upload_file(bucket, key, file_location)


def resolve_config_location(cfg_name):
    """
    Need to check if config name is a file path, a file reference,
       or a configuration name.
    Acceptable formats are:
    /full/path/to/file.cfg.yml
    ./relative/path/to/file.cfg.yml
    filename.cfg.yml
    filename

    If cfg_name is not a path, we will resolve it in this order:
     1. Private config files: .elasticbeanstalk/saved_configs/cfg_name.cfg.yml
     2. Public config files: .elasticbeanstalk/cfg_name.cfg.yml
    """
    slash = os.path.sep
    if cfg_name.startswith(slash) or \
            cfg_name.startswith('.' + slash):
        # Using path
        if not os.path.isfile(cfg_name):
            raise NotFoundError('File ' + cfg_name + ' not found.')

        return os.path.expanduser(cfg_name)
    else:
        for folder in ('saved_configs' + os.path.sep, ''):
            folder = folder + cfg_name
            for extension in ('.cfg.yml', ''):
                file_location = folder + extension
                if fileoperations.eb_file_exists(file_location):
                    return fileoperations.\
                        get_eb_file_full_location(file_location)


def resolve_config_name(app_name, cfg_name):
    """  Resolve the name of the s3 template.
    If cfg_name is a file, we need to first upload the file.

    if the cfg_name is not a file, we can assume it is a correct s3 name.
    We will get an error later if it is invalid.
    """
    config_location = resolve_config_location(cfg_name)
    if config_location is None:
        return cfg_name
    else:
        if cfg_name.endswith('.cfg.yml'):
            cfg_name = cfg_name.rstrip('.cfg.yml')
        upload_config_file(app_name, cfg_name, config_location)
        return cfg_name


def write_to_local_config(cfg_name, data):
    fileoperations.make_eb_dir(SAVED_CONFIG_FOLDER_NAME)

    file_location = SAVED_CONFIG_FOLDER_NAME + cfg_name + '.cfg.yml'
    fileoperations.write_to_eb_data_file(file_location, data)
    return fileoperations.get_eb_file_full_location(file_location)


def get_configurations(app_name):
    app = elasticbeanstalk.describe_application(app_name)
    return app['ConfigurationTemplates']


def validate_config_file(app_name, cfg_name, platform):
    try:
        result = elasticbeanstalk.validate_template(app_name, cfg_name)
    except InvalidParameterValueError as e:
        # Platform not in Saved config. Try again with default platform
        if e.message == responses['create.noplatform']:
           result = elasticbeanstalk.validate_template(app_name, cfg_name,
                                                       platform=platform)
        else:
            raise

    for m in result['Messages']:
        severity = m['Severity']
        message = m['Message']
        if severity == 'error':
            io.log_error(message)
        elif severity == 'warning':
            # Ignore warnings. They are common on partial configurations
            # and almost always completely irrelevant.
            # io.log_warning(message)
            pass
