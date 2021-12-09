from lxml import etree
from owslib.util import element_to_string
import six
import json
import datetime
import re

import logging
log = logging.getLogger(__name__)


# Py2 vs Py3 encoding
def _encode(element):
    import sys
    if sys.version_info[0] < 3:
        return element.encode('utf-8')
    else:
        return str(element)

class MappedXmlObject(object):
    elements = []

class MappedXmlDocument(MappedXmlObject):
    def __init__(self, xml_str=None, xml_tree=None):
        assert (xml_str or xml_tree is not None), 'Must provide some XML in one format or another'
        self.xml_str = xml_str
        self.xml_tree = xml_tree

    def read_values(self):
        '''For all of the elements listed, finds the values of them in the
        XML and returns them.'''
        values = {}
        tree = self.get_xml_tree()
        for element in self.elements:
            values[element.name] = element.read_value(tree)
        self.infer_values(values)
        return values

    def read_value(self, name):
        '''For the given element name, find the value in the XML and return
        it.
        '''
        tree = self.get_xml_tree()
        for element in self.elements:
            if element.name == name:
                return element.read_value(tree)
        raise KeyError

    def get_xml_tree(self):
        if self.xml_tree is None:
            parser = etree.XMLParser(remove_blank_text=True)
            xml_str = six.ensure_str(self.xml_str)
            self.xml_tree = etree.fromstring(xml_str, parser=parser)
        return self.xml_tree

    def infer_values(self, values):
        pass


class MappedXmlElement(MappedXmlObject):
    namespaces = {}

    def __init__(self, name, search_paths=[], multiplicity="*", elements=[]):
        self.name = name
        self.search_paths = search_paths
        self.multiplicity = multiplicity
        self.elements = elements or self.elements

    def read_value(self, tree):
        values = []
        for xpath in self.get_search_paths():
            elements = self.get_elements(tree, xpath)
            values = self.get_values(elements)
            if values:
                break
        return self.fix_multiplicity(values)

    def get_search_paths(self):
        if type(self.search_paths) != type([]):
            search_paths = [self.search_paths]
        else:
            search_paths = self.search_paths
        return search_paths

    def get_elements(self, tree, xpath):
        return tree.xpath(xpath, namespaces=self.namespaces)

    def get_values(self, elements):
        values = []
        if len(elements) == 0:
            pass
        else:
            for element in elements:
                value = self.get_value(element)
                values.append(value)
        return values

    def get_value(self, element):
        if self.elements:
            value = {}
            for child in self.elements:
                value[child.name] = child.read_value(element)
            return value
        elif type(element) == etree._ElementStringResult:
            value = str(element)
        elif type(element) == etree._ElementUnicodeResult:
            value = str(element)
        else:
            value = self.element_tostring(element)
        return value

    def element_tostring(self, element):
        return etree.tostring(element, pretty_print=False)

    def fix_multiplicity(self, values):
        '''
        When a field contains multiple values, yet the spec says
        it should contain only one, then return just the first value,
        rather than a list.

        In the ISO19115 specification, multiplicity relates to:
        * 'Association Cardinality'
        * 'Obligation/Condition' & 'Maximum Occurence'
        '''
        if self.multiplicity == "0":
            # 0 = None
            if values:
                log.warn("Values found for element '%s' when multiplicity should be 0: %s",  self.name, values)
            return ""
        elif self.multiplicity == "1":
            # 1 = Mandatory, maximum 1 = Exactly one
            if not values:
                log.warn("Value not found for element '%s'" % self.name)
                return ''
            return values[0]
        elif self.multiplicity == "*":
            # * = 0..* = zero or more
            return values
        elif self.multiplicity == "0..1":
            # 0..1 = Mandatory, maximum 1 = optional (zero or one)
            if values:
                return values[0]
            else:
                return ""
        elif self.multiplicity == "1..*":
            # 1..* = one or more
            return values
        else:
            log.warning('Multiplicity not specified for element: %s',
                        self.name)
            return values


class ISOElement(MappedXmlElement):

    namespaces = {
        "gts": "http://www.isotc211.org/2005/gts",
        # "gml": "http://www.opengis.net/gml",
        "gml32": "http://www.opengis.net/gml/3.2",
        "gmx": "http://www.isotc211.org/2005/gmx",
        "gsr": "http://www.isotc211.org/2005/gsr",
        "gss": "http://www.isotc211.org/2005/gss",
        # "gco": "http://www.isotc211.org/2005/gco",
        "gmd": "http://www.isotc211.org/2005/gmd",
        # "srv": "http://www.isotc211.org/2005/srv",
        # ISO19115-3
        "xlink": "http://www.w3.org/1999/xlink",
        "gml": "http://www.opengis.net/gml/3.2",
        "cit": "http://standards.iso.org/iso/19115/-3/cit/2.0",
        # "fcc": "http://standards.iso.org/iso/19110/fcc/1.0",
        "gco": "http://standards.iso.org/iso/19115/-3/gco/1.0",
        "gcx": "http://standards.iso.org/iso/19115/-3/gcx/1.0",
        "gex": "http://standards.iso.org/iso/19115/-3/gex/1.0",
        "lan": "http://standards.iso.org/iso/19115/-3/lan/1.0",
        # "mac": "http://standards.iso.org/iso/19115/-3/mac/2.0",
        # "mas": "http://standards.iso.org/iso/19115/-3/mas/1.0",
        "mcc": "http://standards.iso.org/iso/19115/-3/mcc/1.0",
        "mco": "http://standards.iso.org/iso/19115/-3/mco/1.0",
        "mdb": "http://standards.iso.org/iso/19115/-3/mdb/2.0",
        "mdq": "http://standards.iso.org/iso/19157/-2/mdq/1.0",
        "mds": "http://standards.iso.org/iso/19115/-3/mds/2.0",
        "mmi": "http://standards.iso.org/iso/19115/-3/mmi/1.0",
        # "mpc": "http://standards.iso.org/iso/19115/-3/mpc/1.0",
        # "mrc": "http://standards.iso.org/iso/19115/-3/mrc/2.0",
        "mrd": "http://standards.iso.org/iso/19115/-3/mrd/1.0",
        "mri": "http://standards.iso.org/iso/19115/-3/mri/1.0",
        "mrl": "http://standards.iso.org/iso/19115/-3/mrl/2.0",
        "mrs": "http://standards.iso.org/iso/19115/-3/mrs/1.0",
        # "msr": "http://standards.iso.org/iso/19115/-3/msr/2.0",
        "srv": "http://standards.iso.org/iso/19115/-3/srv/2.0",
        "xml": "http://www.w3.org/XML/1998/namespace",
        # "xsi": "http://www.w3.org/2001/XMLSchema-instance",
        # "dqc": "http://standards.iso.org/iso/19157/-2/dqc/1.0",

    }


class ISOResourceLocator(ISOElement):

    elements = [
        ISOElement(
            name="url",
            search_paths=[
                "cit:linkage/gco:CharacterString/text()",
            ],
            multiplicity="1",
        ),
        ISOElement(
            name="function",
            search_paths=[
                "cit:function/cit:CI_OnLineFunctionCode/@codeListValue",
                "cit:function/cit:CI_OnLineFunctionCode/text()",
            ],
            multiplicity="0..1",
        ),
        ISOElement(
            name="name",
            search_paths=[
                "cit:name/gco:CharacterString/text()",
            ],
            multiplicity="0..1",
        ),
        ISOElement(
            name="description",
            search_paths=[
                "cit:description/gco:CharacterString/text()",
            ],
            multiplicity="0..1",
        ),
        ISOElement(
            name="protocol",
            search_paths=[
                "cit:protocol/gco:CharacterString/text()",
            ],
            multiplicity="0..1",
        ),
        # 19115-3
        ISOElement(
            name="protocol-request",
            search_paths=[
                "cit:protocolRequest/gco:CharacterString/text()",
            ],
            multiplicity="0..1",
        ),
        ISOElement(
            name="application-profile",
            search_paths=[
                "cit:applicationProfile/gco:CharacterString/text()",
            ],
            multiplicity="0..1",
        ),
        ISOElement(
            name="distribution-format",
            search_paths=[
                "ancestor::mrd:MD_DigitalTransferOptions/mrd:distributionFormat/mrd:MD_Format/mrd:formatSpecificationCitation/cit:CI_Citation/cit:title/gco:CharacterString/text()"
            ],
            multiplicity="*"
        ),
        ISOElement(
            name="distributor-format",
            search_paths=[
                "ancestor::mrd:MD_Distributor/mrd:distributorFormat/mrd:MD_Format/mrd:formatSpecificationCitation/cit:CI_Citation/cit:title/gco:CharacterString/text()"
            ],
            multiplicity="*"
        ),

        ISOElement(
            name="offline",
            search_paths=[
                "ancestor::mrd:MD_DigitalTransferOptions/mrd:offLine/mrd:MD_Medium/cit:CI_Citation/cit:title/gco:CharacterString/text()"
            ],
            multiplicity="*"
        ),
        ISOElement(
            name="transfer-size",
            search_paths=[
                "ancestor::mrd:MD_DigitalTransferOptions/mrd:transferSize/gco:Real/text()"
            ],
            multiplicity="0..1"
        ),
        ISOElement(
            name="units-of-distribution",
            search_paths=[
                "ancestor::mrd:MD_DigitalTransferOptions/mrd:unitsOfDistribution/gco:CharacterString/text()"
            ],
            multiplicity="0..1"
        )
    ]


class ISOResponsibleParty(ISOElement):

    elements = [
        ISOElement(
            name="individual-name",
            search_paths=[
                "cit:party/cit:CI_Individual/cit:name/gco:CharacterString/text()",
                "cit:party/cit:CI_Organisation/cit:individual/cit:CI_Individual/cit:name/gco:CharacterString/text()",
            ],
            multiplicity="0..1",
        ),
        ISOElement(
            name="organisation-name",
            search_paths=[
                "cit:party/cit:CI_Organisation/cit:name/gco:CharacterString/text()",
            ],
            multiplicity="0..1",
        ),
        ISOElement(
            name="position-name",
            search_paths=[
                "cit:party/cit:CI_Individual/cit:positionName/gco:CharacterString/text()",
                "cit:party/cit:CI_Organisation/cit:individual/cit:CI_Individual/cit:positionName/gco:CharacterString/text()",
            ],
            multiplicity="0..1",
        ),
        ISOElement(
            name="contact-info",
            search_paths=[
                "cit:party/cit:CI_Individual/cit:contactInfo/cit:CI_Contact",
                "cit:party/cit:CI_Organisation/cit:individual/cit:CI_Individual/cit:contactInfo/cit:CI_Contact",
                "cit:party/cit:CI_Organisation/cit:contactInfo/cit:CI_Contact",
            ],
            multiplicity="0..1",
            elements=[
                ISOElement(
                    name="email",
                    search_paths=[
                        "cit:address/cit:CI_Address/cit:electronicMailAddress/gco:CharacterString/text()",
                    ],
                    multiplicity="0..1",
                ),
                ISOResourceLocator(
                    name="online-resource",
                    search_paths=[
                        "cit:onlineResource/cit:CI_OnlineResource",
                    ],
                    multiplicity="0..1",
                ),

            ]
        ),
        ISOElement(
            name="role",
            search_paths=[
                "cit:role/cit:CI_RoleCode/@codeListValue",
                "cit:role/cit:CI_RoleCode/text()",
            ],
            multiplicity="0..1",
        ),
    ]


class ISODataFormat(ISOElement):

    elements = [
        ISOElement(
            name="name",
            search_paths=[
                "mrd:formatSpecificationCitation/cit:CI_Citation/cit:title/gco:CharacterString/text()",
            ],
            multiplicity="0..1",
        ),
        ISOElement(
            name="version",
            search_paths=[
                "mrd:amendmentNumber/gco:CharacterString/text()",
            ],
            multiplicity="0..1",
        ),
    ]


class ISOReferenceDate(ISOElement):

    elements = [
        ISOElement(
            name="type",
            search_paths=[
                "cit:dateType/cit:CI_DateTypeCode/@codeListValue",
                "cit:dateType/cit:CI_DateTypeCode/text()",
            ],
            multiplicity="1",
        ),
        ISOElement(
            name="value",
            search_paths=[
                "cit:date/gco:Date/text()",
                "cit:date/gco:DateTime/text()",
            ],
            multiplicity="1",
            # TODO check multiplicity="0..1", A: both date and type are manditory fields in iso19115
        ),
    ]


class ISOCoupledResources(ISOElement):

    elements = [
        ISOElement(
            name="title",
            search_paths=[
                "@xlink:title",
            ],
            multiplicity="*",
        ),
        ISOElement(
            name="href",
            search_paths=[
                "@xlink:href",
            ],
            multiplicity="*",
        ),
        ISOElement(
            name="uuid",
            search_paths=[
                "@uuidref",
            ],
            multiplicity="*",
        ),

    ]


class ISOBoundingBox(ISOElement):

    elements = [
        ISOElement(
            name="west",
            search_paths=[
                "gex:westBoundLongitude/gco:Decimal/text()",
            ],
            multiplicity="1",
        ),
        ISOElement(
            name="east",
            search_paths=[
                "gex:eastBoundLongitude/gco:Decimal/text()",
            ],
            multiplicity="1",
        ),
        ISOElement(
            name="north",
            search_paths=[
                "gex:northBoundLatitude/gco:Decimal/text()",
            ],
            multiplicity="1",
        ),
        ISOElement(
            name="south",
            search_paths=[
                "gex:southBoundLatitude/gco:Decimal/text()",
            ],
            multiplicity="1",
        ),
    ]


class ISOBrowseGraphic(ISOElement):

    elements = [
        ISOElement(
            name="file",
            search_paths=[
                "mcc:fileName/gco:CharacterString/text()",
            ],
            multiplicity="1",
        ),
        ISOElement(
            name="description",
            search_paths=[
                "mcc:fileDescription/gco:CharacterString/text()",
            ],
            multiplicity="0..1",
        ),
        ISOElement(
            name="type",
            search_paths=[
                "mcc:fileType/gco:CharacterString/text()",
            ],
            multiplicity="0..1",
        ),
    ]


# ISO19115-3
class ISOLocalised(ISOElement):

    elements = [
        ISOElement(
            name="default",
            search_paths=[
                "gco:CharacterString/text()",
            ],
            multiplicity="0..1",
        ),
        ISOElement(
            name='local',
            search_paths=[
                "gmd:PT_FreeText/gmd:textGroup",
                "lan:PT_FreeText/lan:textGroup",
            ],
            multiplicity="0..1",
            elements=[
                ISOElement(
                    name="value",
                    search_paths=[
                        "gmd:LocalisedCharacterString/text()",
                        "lan:LocalisedCharacterString/text()",
                    ],
                    multiplicity="0..1",
                ),
                ISOElement(
                    name="language_code",
                    search_paths=[
                        "gmd:LocalisedCharacterString/@locale",
                        "lan:LocalisedCharacterString/@locale",
                    ],
                    multiplicity="0..1",
                )
            ]
        )
    ]


class ISOKeyword(ISOElement):

    elements = [
        ISOLocalised(
            name="keywords",
            search_paths=[
                "mri:keyword",
            ],
            multiplicity="*",
        ),
        ISOElement(
            name="type",
            search_paths=[
                "mri:type/mri:MD_KeywordTypeCode/@codeListValue",
                "mri:type/mri:MD_KeywordTypeCode/text()",
            ],
            multiplicity="0..1",
        ),
        # If Thesaurus information is needed at some point, this is the
        # place to add it
    ]


# ISO19115-3
class ISOTemporalExtent(ISOElement):

    elements = [
        ISOElement(name="begin",
                   search_paths=[
                       "gml:beginPosition/text()",
                       "gml32:beginPosition/text()",
                   ],
                   multiplicity="0..1"
                   ),
        ISOElement(name="end",
                   search_paths=[
                       "gml:endPosition/text()",
                       "gml32:endPosition/text()",
                   ],
                   multiplicity="0..1"
                   )
    ]


# ISO19115-3
class ISOVerticalExtent(ISOElement):

    elements = [
        ISOElement(name="min",
                   search_paths=[
                       "gex:minimumValue/gco:Real/text()",
                   ],
                   multiplicity="0..1"
                   ),
        ISOElement(name="max",
                   search_paths=[
                       "gex:maximumValue/gco:Real/text()",
                   ],
                   multiplicity="0..1"
                   )
    ]


# ISO19115-3
class ISOIdentifier(ISOElement):

    elements = [
        ISOElement(
            name="code",
            search_paths=[
                # ISO19115-3
                "mcc:code/gco:CharacterString/text()",
                "mcc:code/gcx:Anchor/text()",
            ],
            multiplicity="0..1",
        ),
        ISOElement(
            name="authority",
            search_paths=[
                # ISO19115-3
                "mcc:authority/cit:CI_Citation/cit:title/gco:CharacterString/text()",
                "mcc:authority/cit:CI_Citation/cit:title/gcx:Anchor/text()",
            ],
            multiplicity="0..1",
        ),
        ISOElement(
            name="code-space",
            search_paths=[
                # ISO19115-3
                "mcc:codeSpace/gco:CharacterString/text()",
                "mcc:codeSpace/gcx:Anchor/text()",
            ],
            multiplicity="0..1",
        ),
        ISOElement(
            name="version",
            search_paths=[
                # ISO19115-3
                "mcc:version/gco:CharacterString/text()",
                "mcc:version/gcx:Anchor/text()",
            ],
            multiplicity="0..1",
        ),
    ]


class ISOUsage(ISOElement):

    elements = [
        ISOElement(
            name="usage",
            search_paths=[
                "mri:specificUsage/gco:CharacterString/text()",
            ],
            multiplicity="0..1",
        ),
        ISOResponsibleParty(
            name="contact-info",
            search_paths=[
                "mri:userContactInfo/gmd:CI_ResponsibleParty",
            ],
            multiplicity="0..1",
        ),
    ]


class ISOAggregationInfo(ISOElement):
    elements = [
        ISOElement(
            name="aggregate-dataset-name",
            search_paths=[
                "mri:name/cit:CI_Citation/cit:title/gco:CharacterString/text()"
            ],
            multiplicity="0..1",
        ),
        ISOElement(
            name="aggregate-dataset-identifier",
            search_paths=[
                "mri:name/cit:CI_Citation/cit:identifier/mcc:MD_Identifier/mcc:code/gco:CharacterString/text()"
            ],
            multiplicity="0..1",
        ),
        ISOElement(
            name="association-type",
            search_paths=[
                "mri:associationType/mri:DS_AssociationTypeCode/@codeListValue",
                "mri:associationType/mri:DS_AssociationTypeCode/text()"
            ],
            multiplicity="0..1",
        ),
        ISOElement(
            name="initiative-type",
            search_paths=[
                "mri:initiativeType/mri:DS_InitiativeTypeCode/@codeListValue",
                "mri:initiativeType/mri:DS_InitiativeTypeCode/text()",
            ],
            multiplicity="0..1",
        ),
    ]


class ISOSource(ISOElement):
    elements = [
        ISOElement(
            name="description",
            search_paths=[
                "mrl:description/gco:CharacterString/text()"
            ],
            multiplicity="0..1",
        ),
        ISOElement(
            name="scope",
            search_paths=[
                "mrl:scope/mcc:MD_Scope/mcc:level/mcc:MD_ScopeCode/@codeListValue",
                "mrl:scope/mcc:MD_Scope/mcc:level/mcc:MD_ScopeCode/text()"
            ],
            multiplicity="0..1",
        ),

    ]


class ISOLineage(ISOElement):
    elements = [
        ISOElement(
            name="statement",
            search_paths=[
                "mrl:statement/gco:CharacterString/text()"
            ],
            multiplicity="0..1",
        ),
        ISOSource(
            name="source",
            search_paths=[
                "mrl:source/mrl:LI_Source"
            ],
            multiplicity="*",
        ),
        ISOElement(
            name="processStep",
            search_paths=[
                "mrl:processStep/mrl:LI_ProcessStep/mrl:description/gco:CharacterString/text()"
            ],
            multiplicity="*",
        ),
    ]


# ISO19115-3
class ISOCitation(ISOElement):
    elements = [
        ISOElement(
            name="type",
            search_paths=[
                "ancestor::mdb:MD_Metadata/mdb:metadataScope/mdb:MD_MetadataScope/mdb:resourceScope/mcc:MD_ScopeCode/@codeListValue",
                "ancestor::mdb:MD_Metadata/mdb:metadataScope/mdb:MD_MetadataScope/mdb:resourceScope/mcc:MD_ScopeCode/text()",
            ],
            multiplicity="1",
        ),
        ISOElement(
            name="id",
            search_paths=[
                "ancestor::mdb:MD_Metadata/mdb:metadataIdentifier/mcc:MD_Identifier",
            ],
            multiplicity="0..1",
            elements=[
                ISOElement(
                    name="code",
                    search_paths=[
                        "mcc:code/gco:CharacterString/text()",
                        "mcc:code/gcx:Anchor/text()",
                    ],
                    multiplicity="0..1",
                ),
                ISOElement(
                    name="authority",
                    search_paths=[
                        "mcc:authority/cit:CI_Citation/cit:title/gco:CharacterString/text()",
                        "mcc:authority/cit:CI_Citation/cit:title/gcx:Anchor/text()",
                    ],
                    multiplicity="0..1",
                ),
                ISOElement(
                    name="code-space",
                    search_paths=[
                        "mcc:codeSpace/gco:CharacterString/text()",
                        "mcc:codeSpace/gcx:Anchor/text()",
                    ],
                    multiplicity="0..1",
                ),
                ISOElement(
                    name="version",
                    search_paths=[
                        "mcc:version/gco:CharacterString/text()",
                        "mcc:version/gcx:Anchor/text()",
                    ],
                    multiplicity="0..1",
                ),
            ]
        ),
        ISOResponsibleParty(
            name="author",
            search_paths=[
                "cit:citedResponsibleParty/cit:CI_Responsibility"
            ],
            multiplicity="1..*",
        ),
        ISOReferenceDate(
            name="issued",
            search_paths=[
                "ancestor::mdb:MD_Metadata/mdb:identificationInfo/mri:MD_DataIdentification/mri:citation/cit:CI_Citation/cit:date/cit:CI_Date[cit:dateType/cit:CI_DateTypeCode/@codeListValue != 'creation']",
                "ancestor::mdb:MD_Metadata/mdb:dateInfo/cit:CI_Date"
            ],
            multiplicity="1..*",
        ),
        ISOLocalised(
            name="abstract",
            search_paths=[
                "ancestor::mdb:MD_Metadata/mdb:identificationInfo/mri:MD_DataIdentification/mri:abstract",
                "ancestor::mdb:MD_Metadata/mdb:identificationInfo/srv:SV_ServiceIdentification/srv:abstract",
            ],
            multiplicity="1",
        ),
        ISOElement(
            name="publisher",
            search_paths=[
                "cit:citedResponsibleParty/cit:CI_Responsibility[cit:role/cit:CI_RoleCode/text() ='publisher']/cit:party/cit:CI_Individual/cit:name/gco:CharacterString/text()[boolean(.)]",
                "cit:citedResponsibleParty/cit:CI_Responsibility[cit:role/cit:CI_RoleCode/text() ='publisher']/cit:party/cit:CI_Organisation/cit:name/gco:CharacterString/text()[boolean(.)]",

            ],
            multiplicity="1",
        ),
        ISOLocalised(
            name="title",
            search_paths=[
                "cit:title",
            ],
            multiplicity="1",
        ),
    ]


class ISO19115Document(MappedXmlDocument):

    # Attribute specifications from "XPaths for GEMINI" by Peter Parslow.

    elements = [
        ISOIdentifier(
            name="guid",
            search_paths=[
                "mdb:metadataIdentifier/mcc:MD_Identifier"
            ],
            multiplicity="0..1",
        ),
        ISOElement(
            name="metadata-language",
            search_paths=[
                "mdb:defaultLocale/lan:PT_Locale/lan:language/lan:LanguageCode/@codeListValue",
                "mdb:defaultLocale/lan:PT_Locale/lan:language/lan:LanguageCode/text()",
            ],
            multiplicity="1",
            # TODO check why changed. A: defaultLocal is mandatory when multi-lingual text used in free text fields
            # multiplicity="0..1",
        ),
        ISOElement(
            name="metadata-standard-name",
            search_paths="mdb:metadataStandardName/cit:CI_Citation/cit:title/gco:CharacterString/text()",
            multiplicity="0..1",
        ),
        ISOElement(
            name="metadata-standard-version",
            search_paths="mdb:metadataStandardName/cit:CI_Citation/cit:edition/gco:CharacterString/text()",
            multiplicity="0..1",
        ),
        ISOElement(
            name="resource-type",
            search_paths=[
                "mdb:metadataScope/mdb:MD_MetadataScope/mdb:resourceScope/mcc:MD_ScopeCode/@codeListValue",
                "mdb:metadataScope/mdb:MD_MetadataScope/mdb:resourceScope/mcc:MD_ScopeCode/text()",
            ],
            multiplicity="*",
        ),
        ISOResponsibleParty(
            name="metadata-point-of-contact",
            search_paths=[
                "mdb:contact/cit:CI_Responsibility",
                "mdb:identificationInfo/*[contains(local-name(), 'Identification')]/mri:citation/cit:CI_Citation/cit:citedResponsibleParty/cit:CI_Responsibility[cit:role/cit:CI_RoleCode/@codeListValue ='pointOfContact']",
                "mdb:identificationInfo/*[contains(local-name(), 'Identification')]/mri:citation/cit:CI_Citation/cit:citedResponsibleParty/cit:CI_Responsibility[cit:role/cit:CI_RoleCode/text() ='pointOfContact']",
                "mdb:identificationInfo/*[contains(local-name(), 'Identification')]/mri:resourceMaintenance/mmi:MD_MaintenanceInformation/mmi:contact/cit:CI_Responsibility",
            ],
            multiplicity="1..*",
        ),
        # 19115-3
        ISOResponsibleParty(
            name="cited-responsible-party",
            search_paths=[
                "mdb:identificationInfo/*[contains(local-name(), 'Identification')]/mri:citation/cit:CI_Citation/cit:citedResponsibleParty/cit:CI_Responsibility",
            ],
            multiplicity="1..*",
        ),
        ISOReferenceDate(
            # All creation, publication, revision, etc. dates relevant to the metadata
            name="metadata-reference-date",
            search_paths=[
                "mdb:dateInfo/cit:CI_Date",
            ],
            multiplicity="1..*",
        ),

        ISOElement(
            name="metadata-date",
            # The date the metadata was most recently created, published, revised, etc.
            search_paths=[
                "gmd:dateStamp/gco:DateTime/text()",
                "gmd:dateStamp/gco:Date/text()",
                # 19115-3
                "mdb:dateInfo/cit:CI_Date/cit:date/gco:Date/text() | mdb:dateInfo/cit:CI_Date/cit:date/gco:DateTime/text()",
            ],
            multiplicity="1..*",
            # TODO check why changed. A: multiple dates associated with the
            # metadata, we want the most recent so need to capture all of them
            # and filter later. In ISO19139 this was a single entry.
            # multiplicity="1",
        ),
        ISOElement(
            name="spatial-reference-system",
            search_paths=[
                "mdb:referenceSystemInfo/mrs:MD_ReferenceSystem/mrs:referenceSystemIdentifier/mcc:MD_Identifier/mcc:code/gco:CharacterString/text()",
            ],
            multiplicity="0..1",
        ),
        ISOLocalised(
            name="title",
            search_paths=[
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:citation/cit:CI_Citation/cit:title",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:citation/cit:CI_Citation/cit:title",
            ],
            multiplicity="1",
        ),
        ISOLocalised(
            name="alternate-title",
            search_paths=[
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:citation/cit:CI_Citation/cit:alternateTitle",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:citation/cit:CI_Citation/cit:alternateTitle",
            ],
            multiplicity="*",
        ),
        ISOReferenceDate(
            name="dataset-reference-date",
            search_paths=[
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:citation/cit:CI_Citation/cit:date/cit:CI_Date"
            ],
            multiplicity="1..*",
        ),
        ISOElement(
            name="unique-resource-identifier",
            search_paths=[
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:citation/cit:CI_Citation/cit:identifier/mcc:MD_Identifier/mcc:code/gco:CharacterString/text()",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:citation/cit:CI_Citation/cit:identifier/mcc:MD_Identifier/mcc:code/gco:CharacterString/text()",
            ],
            multiplicity="0..1",
        ),
        # 19115-3
        ISOIdentifier(
            # this would commonly be a DOI
            name="unique-resource-identifier-full",
            search_paths=[
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:citation/cit:CI_Citation/cit:identifier/mcc:MD_Identifier",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:citation/cit:CI_Citation/cit:identifier/mcc:MD_Identifier",
            ],
            multiplicity="0..1",
        ),

        ISOElement(
            name="presentation-form",
            search_paths=[
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:citation/cit:CI_Citation/cit:presentationForm/cit:CI_PresentationFormCode/text()",
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:citation/cit:CI_Citation/cit:presentationForm/cit:CI_PresentationFormCode/@codeListValue",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:citation/cit:CI_Citation/cit:presentationForm/cit:CI_PresentationFormCode/text()",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:citation/cit:CI_Citation/cit:presentationForm/cit:CI_PresentationFormCode/@codeListValue",

            ],
            multiplicity="*",
        ),
        ISOLocalised(
            name="abstract",
            search_paths=[
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:abstract",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:abstract",
            ],
            multiplicity="1",
        ),
        ISOElement(
            name="purpose",
            search_paths=[
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:purpose/gco:CharacterString/text()",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:purpose/gco:CharacterString/text()",
            ],
            multiplicity="0..1",
        ),
        ISOResponsibleParty(
            name="responsible-organisation",
            search_paths=[
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:citation/cit:CI_Citation/cit:citedResponsibleParty/cit:CI_Responsibility[cit:role/cit:CI_RoleCode/@codeListValue ='pointOfContact']",
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:citation/cit:CI_Citation/cit:citedResponsibleParty/cit:CI_Responsibility[cit:role/cit:CI_RoleCode/text() ='pointOfContact']",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:citation/cit:CI_Citation/cit:citedResponsibleParty/cit:CI_Responsibility[cit:role/cit:CI_RoleCode/@codeListValue ='pointOfContact']",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:citation/cit:CI_Citation/cit:citedResponsibleParty/cit:CI_Responsibility[cit:role/cit:CI_RoleCode/text() ='pointOfContact']",
                "mdb:contact/cit:CI_ResponsibleParty",
            ],
            multiplicity="1..*",
        ),
        ISOElement(
            name="frequency-of-update",
            search_paths=[
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:resourceMaintenance/mmi:MD_MaintenanceInformation/mmi:maintenanceAndUpdateFrequency/mmi:MD_MaintenanceFrequencyCode/@codeListValue",
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:resourceMaintenance/mmi:MD_MaintenanceInformation/mmi:maintenanceAndUpdateFrequency/mmi:MD_MaintenanceFrequencyCode/text()",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:resourceMaintenance/mmi:MD_MaintenanceInformation/mmi:maintenanceAndUpdateFrequency/mmi:MD_MaintenanceFrequencyCode/@codeListValue",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:resourceMaintenance/mmi:MD_MaintenanceInformation/mmi:maintenanceAndUpdateFrequency/mmi:MD_MaintenanceFrequencyCode/text()",
            ],
            multiplicity="0..1",
        ),
        ISOElement(
            name="maintenance-note",
            search_paths=[
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:resourceMaintenance/mmi:MD_MaintenanceInformation/mmi:maintenanceNote/gco:CharacterString/text()",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:resourceMaintenance/mmi:MD_MaintenanceInformation/mmi:maintenanceNote/gco:CharacterString/text()",
            ],
            multiplicity="0..1",
        ),
        ISOElement(
            name="progress",
            search_paths=[
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:status/mcc:MD_ProgressCode/@codeListValue",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:status/mcc:MD_ProgressCode/@codeListValue",
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:status/mcc:MD_ProgressCode/text()",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:status/mcc:MD_ProgressCode/text()",
            ],
            multiplicity="*",
        ),
        ISOKeyword(
            name="keywords",
            search_paths=[
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:descriptiveKeywords/mri:MD_Keywords",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:descriptiveKeywords/mri:MD_Keywords",
            ],
            multiplicity="*"
        ),
        # TODO: Is the inspire theme keywords still needed? consider updating infer_tags to use 'keywords'
        ISOElement(
            name="keyword-inspire-theme",
            search_paths=[
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:descriptiveKeywords/mri:MD_Keywords/mri:keyword/gco:CharacterString/text()",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:descriptiveKeywords/mri:MD_Keywords/mri:keyword/gco:CharacterString/text()",
            ],
            multiplicity="*",
        ),
        # Deprecated: kept for backwards compatibilty
        # TODO: Still need keyword-controlled-other? seems like a duplicate
        ISOElement(
            name="keyword-controlled-other",
            search_paths=[
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:descriptiveKeywords/mri:MD_Keywords/mri:keyword/gco:CharacterString/text()",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:descriptiveKeywords/mri:MD_Keywords/mri:keyword/gco:CharacterString/text()",
            ],
            multiplicity="*",
        ),
        ISOUsage(
            name="usage",
            search_paths=[
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:resourceSpecificUsage/mri:MD_Usage",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:resourceSpecificUsage/mri:MD_Usage",
            ],
            multiplicity="*"
        ),
        ISOElement(
            name="limitations-on-public-access",
            search_paths=[
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:resourceConstraints/mco:MD_LegalConstraints/mco:otherConstraints/gco:CharacterString/text()",
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:resourceConstraints/mco:MD_LegalConstraints/mco:otherConstraints/gcx:Anchor/text()",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:resourceConstraints/mco:MD_LegalConstraints/mco:otherConstraints/gco:CharacterString/text()",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:resourceConstraints/mco:MD_LegalConstraints/mco:otherConstraints/gcx:Anchor/text()",
            ],
            multiplicity="*",
        ),
        ISOElement(
            name="access-constraints",
            search_paths=[
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:resourceConstraints/mco:MD_LegalConstraints/mco:accessConstraints/mco:MD_RestrictionCode/@codeListValue",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:resourceConstraints/mco:MD_LegalConstraints/mco:accessConstraints/mco:MD_RestrictionCode/@codeListValue",
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:resourceConstraints/mco:MD_LegalConstraints/mco:accessConstraints/mco:MD_RestrictionCode/text()",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:resourceConstraints/mco:MD_LegalConstraints/mco:accessConstraints/mco:MD_RestrictionCode/text()",
            ],
            multiplicity="*",
        ),

        ISOElement(
            name="use-constraints",
            search_paths=[
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:resourceConstraints/mco:MD_Constraints/mco:useLimitation/gco:CharacterString/text()",
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:resourceConstraints/mco:MD_LegalConstraints/mco:useLimitation/gco:CharacterString/text()",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:resourceConstraints/mco:MD_Constraints/mco:useLimitation/gco:CharacterString/text()",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:resourceConstraints/mco:MD_LegalConstraints/mco:useLimitation/gco:CharacterString/text()",
            ],
            multiplicity="*",
        ),
        # TODO: not sure use-constraints-code is needed.
        ISOElement(
            name="use-constraints-code",
            search_paths=[
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:resourceConstraints/mco:MD_LegalConstraints/mco:useConstraints/mco:MD_RestrictionCode/@codeListValue",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:resourceConstraints/mco:MD_LegalConstraints/mco:useConstraints/mco:MD_RestrictionCode/text()",
            ],
            multiplicity="*",
        ),
        ISOElement(
            # used to get license_id
            name="legal-constraints-reference-code",
            search_paths=[
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:resourceConstraints/mco:MD_LegalConstraints/mco:reference/cit:CI_Citation/cit:identifier/mcc:MD_Identifier/mcc:code/gco:CharacterString/text()",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:resourceConstraints/mco:MD_LegalConstraints/mco:reference/cit:CI_Citation/cit:identifier/mcc:MD_Identifier/mcc:code/gco:CharacterString/text()",
            ],
            multiplicity="*",
        ),
        ISOAggregationInfo(
            name="aggregation-info",
            search_paths=[
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:associatedResource/mri:MD_AssociatedResource",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:associatedResource/mri:MD_AssociatedResource",
            ],
            multiplicity="*",
        ),
        ISOElement(
            name="spatial-data-service-type",
            search_paths=[
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:serviceType/gco:ScopedName/text()",
            ],
            multiplicity="0..1",
        ),
        ISOElement(
            name="spatial-resolution",
            search_paths=[
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:spatialResolution/mri:MD_Resolution/mri:distance/mri:Distance/text()",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:spatialResolution/mri:MD_Resolution/mri:distance/gco:Distance/text()",
            ],
            multiplicity="0..1",
        ),
        ISOElement(
            name="spatial-resolution-units",
            search_paths=[
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:spatialResolution/mri:MD_Resolution/mri:distance/mri:Distance/@uom",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:spatialResolution/mri:MD_Resolution/mri:distance/gco:Distance/@uom",
            ],
            multiplicity="0..1",
        ),
        ISOElement(
            name="equivalent-scale",
            search_paths=[
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:spatialResolution/mri:MD_Resolution/mri:equivalentScale/mri:MD_RepresentativeFraction/mri:denominator/gco:Integer/text()",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:spatialResolution/mri:MD_Resolution/mri:equivalentScale/mri:MD_RepresentativeFraction/mri:denominator/gco:Integer/text()",
            ],
            multiplicity="*",
        ),
        ISOElement(
            name="dataset-language",
            search_paths=[
                "gmd:identificationInfo/gmd:MD_DataIdentification/gmd:language/gmd:LanguageCode/@codeListValue",
                "gmd:identificationInfo/srv:SV_ServiceIdentification/gmd:language/gmd:LanguageCode/@codeListValue",
                "gmd:identificationInfo/gmd:MD_DataIdentification/gmd:language/gmd:LanguageCode/text()",
                "gmd:identificationInfo/srv:SV_ServiceIdentification/gmd:language/gmd:LanguageCode/text()",
            ],
            multiplicity="*",
        ),
        ISOElement(
            name="topic-category",
            search_paths=[
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:topicCategory/mri:MD_TopicCategoryCode/text()",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:topicCategory/mri:MD_TopicCategoryCode/text()",
            ],
            multiplicity="*",
        ),
        ISOElement(
            name="extent-controlled",
            search_paths=[
            ],
            multiplicity="*",
        ),
        ISOIdentifier(
            name="extent-free-text",
            search_paths=[
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:extent/gex:EX_Extent/gex:geographicElement/gex:EX_GeographicDescription/gex:geographicIdentifier/mcc:MD_Identifier",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:extent/gex:EX_Extent/gex:geographicElement/gex:EX_GeographicDescription/gex:geographicIdentifier/mcc:MD_Identifier",
            ],
            multiplicity="*",
        ),
        ISOBoundingBox(
            name="bbox",
            search_paths=[
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:extent/gex:EX_Extent/gex:geographicElement/gex:EX_GeographicBoundingBox",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:extent/gex:EX_Extent/gex:geographicElement/gex:EX_GeographicBoundingBox",
            ],
            multiplicity="*",
        ),
        # note that gex:polygon does not have to contain a polygon, it could be a point or some other gm object
        ISOElement(
            name="spatial",
            search_paths=[
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:extent/gex:EX_Extent/gex:geographicElement/gex:EX_BoundingPolygon/gex:polygon/node()",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:extent/gex:EX_Extent/gex:geographicElement/gex:EX_BoundingPolygon/gex:polygon/node()",
            ],
            multiplicity="*",
        ),

        # temporal-extent-begin and temporal-extent-end are both captured by temporal-extent but are kept for backword compatability
        ISOElement(
            name="temporal-extent-begin",
            search_paths=[
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:extent/gex:EX_Extent/gex:temporalElement/gex:EX_TemporalExtent/gex:extent/gml:TimePeriod/gml:beginPosition/text()",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:extent/gex:EX_Extent/gex:temporalElement/gex:EX_TemporalExtent/gex:extent/gml:TimePeriod/gml:beginPosition/text()",
            ],
            multiplicity="*",
        ),
        ISOElement(
            name="temporal-extent-end",
            search_paths=[
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:extent/gex:EX_Extent/gex:temporalElement/gex:EX_TemporalExtent/gex:extent/gml:TimePeriod/gml:endPosition/text()",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:extent/gex:EX_Extent/gex:temporalElement/gex:EX_TemporalExtent/gex:extent/gml:TimePeriod/gml:endPosition/text()",
            ],
            multiplicity="*",
        ),
        # Treating temporal extent begin and end as nested object of temporal extent fits better with the subfield concept of scheming
        ISOTemporalExtent(
            name="temporal-extent",
            search_paths=[
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:extent/gex:EX_Extent/gex:temporalElement/gex:EX_TemporalExtent/gex:extent/gml:TimePeriod",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:extent/gex:EX_Extent/gex:temporalElement/gex:EX_TemporalExtent/gex:extent/gml:TimePeriod",
            ],
            multiplicity="*",
        ),
        ISOVerticalExtent(
            name="vertical-extent",
            search_paths=[
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:extent/gex:EX_Extent/gex:verticalElement/gex:EX_VerticalExtent",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:extent/gex:EX_Extent/gex:verticalElement/gex:EX_VerticalExtent",
            ],
            multiplicity="*",
        ),
        # crs is needed so we know if up or down is positive in vertical extent
        ISOElement(
            name="vertical-extent-crs",
            search_paths=[
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:extent/gex:EX_Extent/gex:verticalElement/gex:EX_VerticalExtent/gex:verticalCRSId/mrs:MD_ReferenceSystem/mrs:referenceSystemIdentifier/mcc:MD_Identifier/mcc:code/gco:CharacterString/text()",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:extent/gex:EX_Extent/gex:verticalElement/gex:EX_VerticalExtent/gex:verticalCRSId/mrs:MD_ReferenceSystem/mrs:referenceSystemIdentifier/mcc:MD_Identifier/mcc:code/gco:CharacterString/text()",
            ],
            multiplicity="*",
        ),

        ISOCoupledResources(
            name="coupled-resource",
            search_paths=[
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:operatesOn",
            ],
            multiplicity="*",
        ),
        ISOElement(
            name="additional-information-source",
            search_paths=[
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:supplementalInformation/gco:CharacterString/text()",
            ],
            multiplicity="0..1",
        ),
        ISODataFormat(
            name="data-format",
            search_paths=[
                "mdb:distributionInfo/mrd:MD_Distribution/mrd:distributionFormat/mrd:MD_Format",
            ],
            multiplicity="*",
        ),
        ISOResponsibleParty(
            name="distributor",
            search_paths=[
                "mdb:distributionInfo/mrd:MD_Distribution/mrd:distributor/mrd:MD_Distributor/mrd:distributorContact/cit:CI_Responsibility",
            ],
            multiplicity="*",
        ),
        ISOResourceLocator(
            name="resource-locator",
            search_paths=[
                "mdb:distributionInfo/mrd:MD_Distribution/mrd:transferOptions/mrd:MD_DigitalTransferOptions/mrd:onLine/cit:CI_OnlineResource",
                "mdb:distributionInfo/mrd:MD_Distribution/mrd:distributor/mrd:MD_Distributor/mrd:distributorTransferOptions/mrd:MD_DigitalTransferOptions/mrd:onLine/cit:CI_OnlineResource",
            ],
            multiplicity="*",
        ),
        # not sure if resource-locator-identification works but updating xpath anyway
        ISOResourceLocator(
            name="resource-locator-identification",
            search_paths=[
                "mdb:identificationInfo//cit:CI_OnlineResource",
            ],
            multiplicity="*",
        ),
        # these three conformity fields could be combined into one element
        ISOElement(
            name="conformity-specification",
            search_paths=[
                "mdb:dataQualityInfo/mdq:DQ_DataQuality/mdq:report/mdq:DQ_Element/mdq:result/mdq:DQ_ConformanceResult/mdq:specification",
            ],
            multiplicity="0..1",
        ),
        ISOElement(
            name="conformity-pass",
            search_paths=[
                "mdb:dataQualityInfo/mdq:DQ_DataQuality/mdq:report/mdq:DQ_Element/mdq:result/mdq:DQ_ConformanceResult/mdq:pass/gco:Boolean/text()",
            ],
            multiplicity="0..1",
        ),
        ISOElement(
            name="conformity-explanation",
            search_paths=[
                "mdb:dataQualityInfo/mdq:DQ_DataQuality/mdq:report/mdq:DQ_Element/mdq:result/mdq:DQ_ConformanceResult/mdq:explanation/gco:CharacterString/text()",
            ],
            multiplicity="0..1",
        ),
        ISOLineage(
            name="lineage",
            search_paths=[
                "mdb:resourceLineage/mrl:LI_Lineage"
            ],
            multiplicity="*",
        ),
        ISOBrowseGraphic(
            name="browse-graphic",
            search_paths=[
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:graphicOverview/mcc:MD_BrowseGraphic",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:graphicOverview/mcc:MD_BrowseGraphic",
            ],
            multiplicity="*",
        ),
        # 19115-3
        ISOResponsibleParty(
            name="author",
            search_paths=[
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:citation/cit:CI_Citation/cit:citedResponsibleParty/cit:CI_Responsibility[cit:role/cit:CI_RoleCode/@codeListValue ='author']",
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:citation/cit:CI_Citation/cit:citedResponsibleParty/cit:CI_Responsibility[cit:role/cit:CI_RoleCode/@codeListValue ='originator']",
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:citation/cit:CI_Citation/cit:citedResponsibleParty/cit:CI_Responsibility[cit:role/cit:CI_RoleCode/@codeListValue ='owner']",
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:citation/cit:CI_Citation/cit:citedResponsibleParty/cit:CI_Responsibility[cit:role/cit:CI_RoleCode/text() ='author']",
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:citation/cit:CI_Citation/cit:citedResponsibleParty/cit:CI_Responsibility[cit:role/cit:CI_RoleCode/text() ='originator']",
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:citation/cit:CI_Citation/cit:citedResponsibleParty/cit:CI_Responsibility[cit:role/cit:CI_RoleCode/text() ='owner']",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:citation/cit:CI_Citation/cit:citedResponsibleParty/cit:CI_Responsibility[cit:role/cit:CI_RoleCode/@codeListValue ='author']",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:citation/cit:CI_Citation/cit:citedResponsibleParty/cit:CI_Responsibility[cit:role/cit:CI_RoleCode/@codeListValue ='originator']",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:citation/cit:CI_Citation/cit:citedResponsibleParty/cit:CI_Responsibility[cit:role/cit:CI_RoleCode/@codeListValue ='owner']",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:citation/cit:CI_Citation/cit:citedResponsibleParty/cit:CI_Responsibility[cit:role/cit:CI_RoleCode/text() ='author']",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:citation/cit:CI_Citation/cit:citedResponsibleParty/cit:CI_Responsibility[cit:role/cit:CI_RoleCode/text() ='originator']",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:citation/cit:CI_Citation/cit:citedResponsibleParty/cit:CI_Responsibility[cit:role/cit:CI_RoleCode/text() ='owner']",
            ],
            multiplicity="1..*",
        ),
        ISOCitation(
            name="citation",
            search_paths=[
                "mdb:identificationInfo/mri:MD_DataIdentification/mri:citation/cit:CI_Citation",
                "mdb:identificationInfo/srv:SV_ServiceIdentification/srv:citation/cit:CI_Citation",
            ],
            multiplicity="1..*",
        ),
    ]

    def infer_values(self, values):
        # Todo: Infer name.
        self.infer_date_released(values)
        self.infer_date_updated(values)
        self.infer_date_created(values)
        self.infer_url(values)
        # Todo: Infer resources.
        self.infer_tags(values)
        self.infer_publisher(values)
        self.infer_contact(values)
        self.infer_contact_email(values)

        import ckan.plugins.toolkit as toolkit
        schemas = toolkit.h.scheming_dataset_schemas()
        schema_field_names = []
        if schemas:
            for key, value in schemas.items():
                for field in value['dataset_fields']:
                    schema_field_names.append(field['field_name'])

        self.clean_metadata_reference_date(values)
        self.clean_dataset_reference_date(values)
        self.infer_metadata_date(values)

        if 'spatial' in schema_field_names:
            self.infer_spatial(values)

        if 'metadata-language' in schema_field_names:
            self.infer_metadata_language(values)

        if 'keywords' in schema_field_names:
            self.infer_keywords(values)

        self.infer_multilingual(values)
        self.infer_guid(values)

        if ('temporal-extent' in schema_field_names or
            'vertical-extent' in schema_field_names):
            self.infer_temporal_vertical_extent(values)

        if 'citation' in schema_field_names:
            self.infer_citation(values)
        # self.drop_empty_objects(values)

        return values

    # TODO make citation field more generic and configurable so others can use it
    def infer_citation(self, values):
        import ckan.lib.munge as munge
        from ckan.lib.helpers import url_for
        from copy import copy

        if 'citation' not in values or not values['citation']:
            return
        value = values['citation'][0]
        if len(value['issued']):
            dates = value['issued']
            if isinstance(dates[0], str):
                dates.sort(reverse=True)
            else:  # it's an object
                dates = sorted(dates, key=lambda k: k['value'], reverse=True)
            issued_date = str(dates[0]['value'])
            value['issued'] = [{"date-parts": [issued_date[:4], issued_date[5:7], issued_date[8:10]]}]
        value['id'] = calculate_identifier(value['id'])

        # remove duplicate entries
        author_list = [
            {"individual-name": x['individual-name'],
             "organisation-name": x['organisation-name'],
             } for x in value['author']]
        author_list = [i for n, i in enumerate(author_list) if i not in author_list[n + 1:]]

        # clear author list
        value['author'] = []

        for author in author_list:
            ind = author.get('individual-name')
            org = author.get('organisation-name')
            if ind:
                name_list = ind.split()
                value['author'].append({
                    "given": ' '.join(name_list[0:-1]),
                    "family": name_list[-1]
                })
            else:
                value['author'].append({"literal": org})

        defaultLangKey = cleanLangKey(values.get('metadata-language', 'en'))
        value['title'] = local_to_dict(value['title'], defaultLangKey)
        value['abstract'] = local_to_dict(value['abstract'], defaultLangKey)

        identifier = values.get('unique-resource-identifier-full', {})
        if identifier:
            doi = calculate_identifier(identifier)
            doi = re.sub(r'^http.*doi\.org/', '', doi, flags=re.IGNORECASE)  # strip https://doi.org/ and the like
            if doi and re.match(r'^10.\d{4,9}\/[-._;()/:A-Z0-9]+$', doi, re.IGNORECASE):
                value['DOI'] = doi
        # TODO: could we have more then one doi?
        field = {}
        for lang in ['fr', 'en']:
            field[lang] = copy(value)
            title = field[lang]['title']
            field[lang]['title'] = title.get(lang)
            abstract = field[lang]['abstract']
            field[lang]['abstract'] = abstract.get(lang)
            field[lang]['language'] = lang
            field[lang]['URL'] = url_for(
                controller='dataset',
                action='read',
                id=munge.munge_name(values.get('guid', '')),
                local=lang,
                qualified=True
            )
            field[lang] = json.dumps([field[lang]])
            # the dump converts utf-8 escape sequences to unicode escape
            # sequences so we have to convert back again
            # if(field[lang] and re.search(r'\\u[0-9a-fA-F]{4}', field[lang])):
            #     field[lang] = field[lang].decode("raw_unicode_escape")
            # double escape any double quotes that are already escaped
            field[lang] = field[lang].replace('\"', '\\"')
        values['citation'] = json.dumps(field)

    def clean_metadata_reference_date(self, values):
        dates = []
        for date in values['metadata-reference-date']:
            date['value'] = iso_date_time_to_utc(date['value'])
            dates.append(date)
        if dates:
            dates.sort(key=lambda x: x['value'])  # sort list of objects by value attribute
            values['metadata-reference-date'] = dates

    def clean_dataset_reference_date(self, values):
        dates = []
        for date in values['dataset-reference-date']:
            try:
                date['value'] = iso_date_time_to_utc(date['value'])[:10]
            except Exception as e:
                date['value'] = date['value'][:10]
                log.warn('Problem converting dataset-reference-date to utc format. Defaulting to %s instead', date['value'])

            dates.append(date)
        if dates:
            dates.sort(key=lambda x: x['value'])  # sort list of objects by value attribute
            values['dataset-reference-date'] = dates

    def infer_metadata_date(self, values):
        dates = values.get('metadata-date', [])

        # use newest date in list
        if len(dates):
            dates.sort(reverse=True)
            values['metadata-date'] = dates[0]

    def infer_spatial(self, values):
        # it may be possible to remove the dependincy on ogr by using shapely to
        # to parse gml. some good ideas here:
        # https://github.com/mlaloux/My-Python-GIS_StackExchange-answers/blob/master/Using%20Python%20to%20parse%20an%20XML%20containing%20GML%20tags.md
        geom = None
        for xmlGeom in values.get('spatial', []):
            # convert bytes to str
            try:
                xmlGeom = xmlGeom.decode()
            except (UnicodeDecodeError, AttributeError):
                pass

            if isinstance(xmlGeom, list):
                for n, x in enumerate(xmlGeom):
                    try:
                        xmlGeom[n] = x.decode()
                    except (UnicodeDecodeError, AttributeError):
                        pass

            if isinstance(xmlGeom, list):
                if len(xmlGeom) == 1:
                    xmlGeom = xmlGeom[0]

            from osgeo import ogr
            try:
                geom = ogr.CreateGeometryFromGML(xmlGeom)
            except Exception:
                try:
                    geom = ogr.CreateGeometryFromWkt(xmlGeom)
                except Exception:
                    try:
                        geom = ogr.CreateGeometryFromJson(xmlGeom)
                    except Exception:
                        log.error('Spatial field is not GML, WKT, or GeoJSON. Can not convert spatial field.')
                        pass
                        return
        if geom:
            values['spatial'] = geom.ExportToJson()
            if not values.get('bbox'):
                extent = geom.GetEnvelope()
                if extent:
                    values['bbox'].append({'west': '', 'east': '', 'north': '', 'south': ''})
                    values['bbox'][0]['west'], values['bbox'][0]['east'], values['bbox'][0]['north'], values['bbox'][0]['south'] = extent

    def infer_metadata_language(self, values):
        # ckan uses en / fr for language codes as apposed to eng / fra which
        # is common in the iso standard
        if values.get('metadata-language'):
            values['metadata-language'] = values['metadata-language'][:2].lower()

    def infer_keywords(self, values):
        keywords = values['keywords']

        defaultLangKey = cleanLangKey(values.get('metadata-language', 'en'))

        value = []
        if isinstance(keywords, list):
            for klist in keywords:
                ktype = klist.get('type')
                for item in klist.get('keywords', []):
                    LangDict = local_to_dict(item, defaultLangKey)
                    value.append({
                        'keyword': json.dumps(LangDict),
                        'type': ktype
                    })
        else:
            for item in keywords:
                LangDict = local_to_dict(item, defaultLangKey)
                value.append({
                    'keyword': json.dumps(LangDict),
                    'type': item.get('type')
                })
        values['keywords'] = value

    def infer_multilingual(self, values):
        for key in values:
            value = values[key]

            # second case used to gracefully fail if no secondary language is defined
            if (
                isinstance(value, dict) and
                (
                    ('default' in value and 'local' in value and len(value) == 2) or
                    ('default' in value and len(value) == 1)
                )
            ):
                defaultLangKey = cleanLangKey(values.get('metadata-language', 'en'))
                LangDict = local_to_dict(values[key], defaultLangKey)
                values[key] = json.dumps(LangDict)

    def infer_date_released(self, values):
        value = ''
        for date in values['dataset-reference-date']:
            if date['type'] == 'publication':
                value = date['value']
                break
        values['date-released'] = value

    def infer_date_updated(self, values):
        value = ''
        dates = []
        # Use last of several multiple revision dates.
        for date in values['dataset-reference-date']:
            if date['type'] == 'revision':
                dates.append(date['value'])

        if len(dates):
            if len(dates) > 1:
                dates.sort(reverse=True)
            value = dates[0]

        values['date-updated'] = value

    def infer_date_created(self, values):
        value = ''
        for date in values['dataset-reference-date']:
            if date['type'] == 'creation':
                value = date['value']
                break
        values['date-created'] = value

    def infer_url(self, values):
        value = ''
        for locator in values['resource-locator']:
            if locator['function'] == 'information':
                value = locator['url']
                break
        values['url'] = value

    # TODO: handle multiligual keywords. possibly by creating tags_[language] keys
    def infer_tags(self, values):
        tags = []
        for key in ['keyword-inspire-theme', 'keyword-controlled-other']:
            for item in values[key]:
                if item not in tags:
                    tags.append(item)
        values['tags'] = tags

    def infer_publisher(self, values):
        value = ''
        for responsible_party in values['responsible-organisation']:
            if responsible_party['role'] == 'publisher':
                value = responsible_party['organisation-name']
            if value:
                break
        values['publisher'] = value

    def infer_contact(self, values):
        value = ''
        for responsible_party in values['responsible-organisation']:
            value = responsible_party['organisation-name']
            if value:
                break
        values['contact'] = value

    def infer_contact_email(self, values):
        value = ''
        for responsible_party in values['responsible-organisation']:
            if isinstance(responsible_party, dict) and \
               isinstance(responsible_party.get('contact-info'), dict) and \
               'email' in responsible_party['contact-info']:
                value = responsible_party['contact-info']['email']
                if value:
                    break
        values['contact-email'] = value

    def infer_temporal_vertical_extent(self, values):
        value = {}
        te = values.get('temporal-extent', [])
        if te:
            blist = [x.get('begin') for x in te]
            elist = [x.get('end') for x in te]
            try:
                value['begin'] = self.iso_date_time_to_utc(min(blist))[:10]
                if max(elist):  # end is blank for datasets with ongoing collection
                    value['end'] = self.iso_date_time_to_utc(max(elist))[:10]
            except Exception as e:
                value['begin'] = min(blist)[:10]
                if max(elist):
                    value['end'] = max(elist)[:10]
                log.warn(('Problem converting temporal-extent dates to utc format. '
                         'Defaulting to %s and %s instead', value.get('begin', ''), value.get('end', '')))

            values['temporal-extent'] = value
            if value.get('begin'):
                values['temporal-extent-begin'] = value['begin']
            if value.get('end'):
                values['temporal-extent-end'] = value['end']

        value = {}
        te = values.get('vertical-extent', [])
        if te:
            minlist = [x.get('min') for x in te]
            maxlist = [x.get('max') for x in te]
            value['min'] = min(minlist)
            value['max'] = max(maxlist)
            values['vertical-extent'] = value

    def infer_guid(self, values):
        identifier = values.get('guid', {})
        guid = calculate_identifier(identifier)
        if guid:
            values['guid'] = guid

    def drop_empty_objects(self, values):
        to_drop = []
        for key, value in values.items():
            if value == {} or value == []:
                to_drop.append(key)
        for key in to_drop:
            del values[key]


def iso_date_time_to_utc(value):
    value = value.replace("Z", "+0000")
    post_remove = 99
    if re.search(r'[+-]\d{4}', value):
        post_remove = -5
        timedelta = datetime.timedelta(hours=int(value[-5:][1:3]), minutes=int(value[-5:][-2:])) * (-1 if value[-5:][0] == '+' else 1)
    else:
        timedelta = datetime.timedelta(hours=0, minutes=0)
    try:
        utc_dt = datetime.datetime.strptime(value, '%Y-%m-%d')  # date alone is valid
    except ValueError:
        try:
            utc_dt = datetime.datetime.strptime(value[:post_remove], '%Y-%m-%dT%H:%M:%S') + timedelta
        except Exception as e:
            try:
                utc_dt = datetime.datetime.strptime(value[:post_remove], '%Y-%m-%dT%H:%M:%S.%f') + timedelta
            except Exception as e:
                log.debug('Could not convert datetime value %s to UTC: %s', value, e)
                raise
    return utc_dt.strftime('%Y-%m-%d %H:%M:%S')


def calculate_identifier(identifier):
    if isinstance(identifier, str):
        return identifier
    code = identifier.get('code')
    codeSpace = identifier.get('code-space')
    authority = identifier.get('authority')
    version = identifier.get('version')
    guid = None
    if code:
        id_list = [authority, codeSpace, code, version]
        guid = '_'.join(x.strip() for x in id_list if x.strip())
    return guid


def cleanLangKey(key):
    key = re.sub("[^a-zA-Z]+", "", key)
    key = key[:2]
    return key


def local_to_dict(item, defaultLangKey):
    # XML parser seems to generate unicode strings containing utf-8 escape
    # characters even though the file is utf-8. To fix must encode unicode
    # to latin1 then treat as regular utf-8 string. Seems this is not
    # true for all files so trying latin1 first and then utf-8 if it does
    # not encode.
    out = {}

    default = item.get('default').strip()
    # decode double escaped unicode chars
    if(default and re.search(r'\\\\u[0-9a-fA-F]{4}', default)):
        if isinstance(default, str):  # encode to get bytestring as decode only works on bytes
            default = default.encode().decode('unicode-escape')
        else:  # we have bytes
            default = default.decode('unicode-escape')

    if len(default) > 1:
        out.update({defaultLangKey: default})

    local = item.get('local')
    if isinstance(local, dict):
        langKey = cleanLangKey(local.get('language_code'))

        LangValue = item.get('local').get('value')
        LangValue = LangValue.strip()
        # decode double escaped unicode chars
        if(LangValue and re.search(r'\\\\u[0-9a-fA-F]{4}', LangValue)):
            if isinstance(LangValue, str):  # encode to get bytestring as decode only works on bytes
                LangValue = LangValue.encode().decode('unicode-escape')
            else:  # we have bytes
                LangValue = LangValue.decode('unicode-escape')

        if len(LangValue) > 1:
            out.update({langKey: LangValue})

    return out
