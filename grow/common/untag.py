"""Untag an object using convention based keys."""

import re
from boltons import iterutils


LOCALIZED_KEY_REGEX = re.compile(r'(.*)@([^@]+)$')


class Untag(object):
    """Untagging utility for locale and environment based untagging."""

    @staticmethod
    def untag(data, locale_identifier=None, params=None):
        """Untags fields, handling translation priority."""
        paths_to_keep_tagged = set()

        # When untagging the order of the keys isn't consistent. Sometimes the
        # tagged value is found but then is overwritten by the original value
        # since it is processed after the tagged version. Need to keep track of
        # untagged keys to make sure that they are not overwritten by the original.
        untagged_key_paths = set()

        # pylint: disable=too-many-return-statements
        def _visit(path, key, value):
            """Function for each key and value in the data."""
            if not isinstance(key, str):
                return key, value

            if key.endswith('@#'):
                # Translation Comment.
                return False

            # If the key has already been untagged, don't overwrite.
            if (path, key) in untagged_key_paths:
                return False

            marked_for_extraction = key.endswith('@')
            if marked_for_extraction:
                if isinstance(value, list):
                    paths_to_keep_tagged.add((path, key))
                key = key[:-1]

            # Support <key>@<param key>.<param value>: <value>.
            if params:
                param_regex = re.compile(
                    r'(.*)@({})\.([^@]+)$'.format('|'.join(params.keys())))
                param_match = param_regex.match(key)
                if param_match:
                    untagged_key, param_key, param_value = param_match.groups()
                    if not params[param_key]:
                        return False
                    return params[param_key](
                        data, untagged_key, param_key, param_value, value,
                        locale_identifier=locale_identifier)

            # Support <key>@<locale regex>: <value>.
            match = LOCALIZED_KEY_REGEX.match(key)
            if not match:
                return key, value
            untagged_key, locale_from_key = match.groups()
            locale_regex = r'^{}$'.format(locale_from_key)
            if marked_for_extraction or not locale_identifier or not re.match(locale_regex, locale_identifier):
                return False

            # Keep track of the untagged key with the path to make sure that it
            # isn't overwritten later by the original untagged value.
            untagged_key_paths.add((path, untagged_key))

            return untagged_key, value

        # Backwards compatibility for https://github.com/grow/grow/issues/95
        def _remap_exit(path, key, old_parent, new_parent, new_items):
            resp = iterutils.default_exit(path, key, old_parent,
                                          new_parent, new_items)
            if paths_to_keep_tagged and isinstance(resp, dict):
                updated_values = {}
                for sub_key, value in resp.items():
                    if not isinstance(value, list):
                        continue
                    new_key = '{}@'.format(sub_key)
                    updated_values[new_key] = value
                resp.update(updated_values)
                try:
                    paths_to_keep_tagged.remove((path, key))
                except KeyError:
                    pass
            return resp

        return iterutils.remap(data, visit=_visit, exit=_remap_exit)


class UntagParam(object):
    """Untagging param for complex untagging."""

    def __call__(self, data, untagged_key, param_key, param_value, value, locale_identifier=None):
        raise NotImplementedError()


class UntagParamRegex(object):
    """Param using the value of the param value as a regex to match."""

    def __init__(self, value):
        self.value = value

    def __call__(self, data, untagged_key, param_key, param_value, value, locale_identifier=None):
        if not self.value:
            return False
        value_regex = r'^{}$'.format(param_value)
        if not re.match(value_regex, self.value):
            return False
        return untagged_key, value


class UntagParamFieldRegex(object):
    """Param using the value a document field with fallback as a regex to match.

    Attempts to use the value of one of the other data fields as a regex.
    If there is no matching key found it falls back to the collection or podspec.
    """

    def __init__(self, podspec_data, collection_data, value):
        self.podspec_data = podspec_data
        self.collection_data = collection_data
        self.value = value

    def __call__(self, data, untagged_key, param_key, param_value, value, locale_identifier=None):
        podspec_value = self.podspec_data.get(param_value, None)
        collection_value = self.collection_data.get(param_value, podspec_value)
        regex_value = data.get(param_value, collection_value)
        if not regex_value:
            return False
        value_regex = r'^{}$'.format(regex_value)
        if not re.match(value_regex, self.value):
            return False
        return untagged_key, value


class UntagParamLocaleRegex(object):
    """Param using a document field as a regex group to match locale.

    Attempts to use the value of one of the other data fields as a locale regex.
    If there is no matching key found it falls back to the collection or podspec.
    """

    def __init__(self, pod, collection):
        self.podspec_data = pod.podspec.get('localization', {})
        self.collection_data = collection.get('localization', {})

    def __call__(self, data, untagged_key, param_key, param_value, value, locale_identifier=None):
        podspec_value = self.podspec_data.get(param_value, None)
        collection_value = self.collection_data.get(param_value, podspec_value)
        regex_value = data.get(param_value, collection_value)
        if not regex_value:
            return False

        value_regex = r'^{}$'.format(regex_value)
        if not re.match(value_regex, locale_identifier):
            return False
        return untagged_key, value
