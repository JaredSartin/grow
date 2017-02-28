"""Caching for pod meta information."""

from . import document_cache
from . import dependency
from grow.common import timer


class PodCache(object):

    KEY_DOCUMENTS = 'documents'
    KEY_DEPENDENCIES = 'dependencies'

    def __init__(self, yaml, pod):
        self._pod = pod

        self._collection_cache = {}
        self._doc_cache = {}

        self._document_cache = document_cache.DocumentCache()
        self._document_cache.add_all(yaml.get(self.KEY_DOCUMENTS, {}))

        self._dependency_graph = dependency.DependencyGraph()
        self._dependency_graph.add_all(yaml.get(self.KEY_DEPENDENCIES, {}))

    @property
    def collection_cache(self):
        """Cache for the collections."""
        return self._collection_cache

    @property
    def doc_cache(self):
        """Cache for the full document."""
        return self._doc_cache

    @property
    def dependency_graph(self):
        """Dependency graph from rendered docs."""
        return self._dependency_graph

    @property
    def document_cache(self):
        """Cache for specific document properties."""
        return self._document_cache

    def reset(self):
        self._collection_cache = {}
        self._doc_cache = {}
        self._dependency_graph.reset()
        self._document_cache.reset()

    def write(self):
        yaml = {}
        yaml[self.KEY_DEPENDENCIES] = self._dependency_graph.export()
        yaml[self.KEY_DOCUMENTS] = self._document_cache.export()
        self._pod.write_yaml('/{}'.format(self._pod.FILE_PODCACHE), yaml)
