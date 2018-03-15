# coding=utf-8

"""
Collects stats from Endeca Dgraph/MDEX server.
Tested with: Endeca Information Access Platform version 6.3.0.655584

=== Authors

Jan van Bemmelen <jvanbemmelen@bol.com>
Renzo Toma <rtoma@bol.com>

"""

import diamond.collector
import urllib2
from StringIO import StringIO
import re
import xml.etree.cElementTree as ElementTree


class EndecaDgraphCollector(diamond.collector.Collector):

    # ignore these elements, because they are of no use
    IGNORE_ELEMENTS = [
        'most_expensive_queries',
        'general_information',
        'analytics_performance',
        'disk_usage',
        'configupdates',
        'xqueryconfigupdates',
        'spelling_updates',
        'precomputed_sorts',
        'analytics_performance',
        'cache_slices',
    ]

    # ignore these metrics, because they can be generated by graphite
    IGNORE_STATS = [
        'name',
        'units',
    ]

    # set of regular expressions for matching & sub'ing.
    NUMVAL_MATCH = re.compile('^[\d\.e\-\+]*$')
    CHAR_BLACKLIST = re.compile('\-|\ |,|:|/|>|\(|\)')
    UNDERSCORE_UNDUPE = re.compile('_+')

    # endeca xml namespace
    XML_NS = '{http://xmlns.endeca.com/ene/dgraph}'

    def get_default_config_help(self):
        config_help = super(EndecaDgraphCollector,
                            self).get_default_config_help()
        config_help.update({
            'host': "Hostname of Endeca Dgraph instance",
            'port': "Port of the Dgraph API listener",
            'timeout': "Timeout for http API calls",
        })
        return config_help

    def get_default_config(self):
        """
        Returns the default collector settings
        """
        config = super(EndecaDgraphCollector, self).get_default_config()
        config.update({
            'path': 'endeca.dgraph',
            'host': 'localhost',
            'port': 8080,
            'timeout': 1,
        })
        return config

    def collect(self):

        def makeSane(stat):
            stat = self.CHAR_BLACKLIST.sub('_', stat.lower())
            stat = self.UNDERSCORE_UNDUPE.sub('_', stat)
            return stat

        def createKey(element):
            if element.attrib.get("name"):
                key = element.attrib.get("name")
                key = makeSane(key)
            else:
                key = element.tag[len(self.XML_NS):]
            return key

        def processElem(elem, keyList):
            for k, v in elem.items():
                prefix = '.'.join(keyList)
                if k not in self.IGNORE_ELEMENTS and self.NUMVAL_MATCH.match(v):
                    k = makeSane(k)
                    self.publish('%s.%s' % (prefix, k), v)

        def walkXML(context, elemList):
            try:
                for event, elem in context:
                    elemName = createKey(elem)
                    if event == 'start':
                        elemList.append(elemName)
                        if len(elem) == 0:
                            if set(elemList).intersection(self.IGNORE_ELEMENTS):
                                continue
                            processElem(elem, elemList)
                    elif event == 'end':
                        elemList.pop()
            except Exception, e:
                self.log.error('Something went wrong: %s', e)

        url = 'http://%s:%d/admin?op=stats' % (self.config['host'],
                                               self.config['port'])
        try:
            xml = urllib2.urlopen(url, timeout=self.config['timeout']).read()
        except Exception, e:
            self.log.error('Could not connect to endeca on %s: %s' % (url, e))
            return {}

        context = ElementTree.iterparse(StringIO(xml), events=('start', 'end'))
        elemList = []
        walkXML(context, elemList)
